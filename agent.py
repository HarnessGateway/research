#!/usr/bin/env python3
"""agent.py: a chat agent that can change the harness behind it. One console, a harness to pick for each message.

    python3 agent.py                    # on this machine
    python3 agent.py --sandbox          # every turn in a container that is thrown away

A turn is one request: {"harness": "codex", "session": "…", "message": "…"}. The harness names a program beside
this file, agent-<harness>.py, and every such program takes the same request and prints the same events. So the
agent starts whichever one is named, and keeps what must outlive any of them: the session.

What the agent needs is in the folder agent/: who it is, its page, and what it keeps. Standard library only.
"""
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {path.stem.removeprefix("agent-"): path for path in sorted(HERE.glob("agent-*.py"))}    # harness: program
SANDBOX = "--sandbox" in sys.argv
DATA = HERE / "agent" / "data" / ("sandbox" if SANDBOX else "host")
KEY = "DEEPSEEK_API_KEY"                                 # the provider's key: all of this machine a sandbox is given
BOX = ["docker", "run", "--rm", "-i", "--init", "--cpus=2", "--memory=4g", "--pids-limit=512", "--read-only",
       "--tmpfs=/tmp:rw,exec,size=1g", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10000:10000"]
running = {}                                             # by session: the program, while a turn is in progress


def start(program, mind, work, log):
    """Start a harness program on a session's two folders. Here, that is this machine. With --sandbox it is a
    container that sees the program, those folders, and the harnesses installed for it, and nothing else."""
    pipes = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": log}
    if not SANDBOX:
        return subprocess.Popen([sys.executable, program], cwd=work,
                                env={**os.environ, "HOME": str(mind), "TOOLS": str(DATA / "tools")}, **pipes)
    seen = {program: f"/{program.name}:ro", work: "/work", mind: "/mind", DATA / "tools": "/tools"}
    return subprocess.Popen([*BOX, *(f"--volume={path}:{where}" for path, where in seen.items()), "--workdir=/work",
                             "--env=HOME=/mind", "--env=TOOLS=/tools", "--env=npm_config_cache=/tmp/npm",
                             f"--env={KEY}", "node:22", "python3", f"/{program.name}"], **pipes)


def turn(harness, session, message):
    """One turn of a session on one harness, as the events the page shows. A session belongs to no harness: it is
    a mind (the home folder, where each harness keeps its own memory), a work folder they share, and what was
    said. A harness that was not the one answering is told what it missed, so the person never sees the change."""
    folder = DATA / "sessions" / session
    mind, work, record = folder / "mind", folder / "work", folder / "session.json"
    if not folder.exists():
        for each in (mind, work, DATA / "tools"):
            each.mkdir(parents=True, exist_ok=True)
            each.chmod(0o777)                            # the sandbox's user is not this one
        shutil.copy(HERE / "agent" / "AGENTS.md", work)  # who the agent is: every harness reads it unasked
    kept = json.loads(record.read_text()) if record.exists() else {"title": message[:60], "turns": [], "ids": {}}
    mine = kept["ids"].setdefault(harness, {"id": None, "seen": 0})
    missed = "".join(f"{each['role']}: {each['text']}\n\n" for each in kept["turns"][mine["seen"]:])
    asked = message if not missed else ("Here is what was said in this conversation since you last replied. Carry on "
                                        f"from it as the assistant.\n\n{missed}user: {message}")
    said, steps = [], []
    with open(folder / "log.txt", "ab") as log:
        program = running[session] = start(PROGRAMS[harness], mind, work, log)
        program.stdin.write(json.dumps({"message": asked, "session": mine["id"]}).encode())
        program.stdin.close()
        for event in map(json.loads, program.stdout):
            if event["type"] == "session":
                mine["id"] = event["id"]                 # the harness's own id for it: how it is continued
                continue
            (said if event["type"] == "text" else steps).append(event["text"])
            yield event
        ok = program.wait() == 0
    del running[session]
    kept["turns"] += [{"role": "user", "text": message},
                      {"role": "assistant", "text": "\n\n".join(said), "steps": steps, "harness": harness}]
    mine["seen"] = len(kept["turns"])
    record.write_text(json.dumps(kept))
    yield {"type": "done", "ok": ok}


class Console(BaseHTTPRequestHandler):
    def do_GET(self):
        record = DATA / "sessions" / self.path.rpartition("/")[2] / "session.json"
        if self.path == "/":
            self.reply("text/html; charset=utf-8", (HERE / "agent" / "console.html").read_bytes())
        elif self.path == "/sessions":
            records = sorted((DATA / "sessions").glob("*/session.json"), key=os.path.getmtime, reverse=True)
            self.reply("application/json", json.dumps({"harnesses": list(PROGRAMS), "sessions": [
                {"id": each.parent.name, "title": json.loads(each.read_text())["title"]}
                for each in records]}).encode())
        elif re.fullmatch(r"/sessions/[0-9a-f]{32}", self.path) and record.exists():
            self.reply("application/json", record.read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):                                   # taken only as application/json, which another site's page
        if self.headers.get("Content-Type") != "application/json":             # cannot send unasked
            return self.send_error(400, "send application/json")
        asked = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        session = asked.get("session") or uuid.uuid4().hex
        if not re.fullmatch(r"[0-9a-f]{32}", session):
            return self.send_error(400, "that is not a session")
        if self.path == "/stop":                         # stopped from outside: the session is kept
            if session in running:
                running[session].send_signal(signal.SIGTERM)
            return self.reply("application/json", b"{}")
        if asked.get("harness") not in PROGRAMS or not asked.get("message"):
            return self.send_error(400, "a turn is a harness, a session, and a message")
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        events, here = turn(asked["harness"], session, asked["message"]), True
        for event in itertools.chain([{"type": "session", "id": session}], events):
            try:
                if here:
                    self.wfile.write(json.dumps(event).encode() + b"\n")
                    self.wfile.flush()
            except BrokenPipeError:                      # the page went away: the turn is stopped, and still kept
                here = False
                running[session].send_signal(signal.SIGTERM)

    def reply(self, kind, data):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    (DATA / "sessions").mkdir(parents=True, exist_ok=True)
    where = "in a sandbox" if SANDBOX else "on this machine"
    print(f"the console is on http://127.0.0.1:8500/: {', '.join(PROGRAMS)}, {where}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8500), Console).serve_forever()
