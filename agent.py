#!/usr/bin/env python3
"""agent.py: a chat agent that can change the harness behind it. One page, a harness to pick for each message.

    python3 agent.py                    # on this machine
    python3 agent.py --sandbox          # every turn in a container that is thrown away

A turn is one request: {"harness": "codex", "session": "…", "message": "…"}. The harness names a program beside
this file, agent-<harness>.py. The agent runs it, and keeps what must outlive any harness: the session.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {path.stem.removeprefix("agent-"): path for path in sorted(HERE.glob("agent-*.py"))}    # harness: program
DATA = HERE / "agent" / "data"
BOX = ["docker", "run", "--rm", "-i", "--init", "--cpus=2", "--memory=4g", "--pids-limit=512", "--read-only",
       "--tmpfs=/tmp:rw,exec,size=1g", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10000:10000"]


def run(program, mind, work, request):
    """Run a harness program on a session's two folders, and give back the events it printed. Here, that is
    this machine. With --sandbox it is a container that sees the program, its tools, and those two folders."""
    command, env, cwd = [sys.executable, program], {**os.environ, "HOME": str(mind)}, work
    if "--sandbox" in sys.argv:
        seen = {program: f"/app/{program.name}:ro", DATA / "tools": "/app/agent/data/tools", work: "/work",
                mind: "/mind"}
        command = [*BOX, *(f"--volume={path}:{where}" for path, where in seen.items()), "--workdir=/work",
                   "--env=HOME=/mind", "--env=npm_config_cache=/tmp/npm", "--env=DEEPSEEK_API_KEY", "node:22",
                   "python3", f"/app/{program.name}"]
        env, cwd = os.environ, None
    printed = subprocess.run(command, cwd=cwd, env=env, input=json.dumps(request), stdout=subprocess.PIPE, text=True)
    return [json.loads(line) for line in printed.stdout.splitlines()]


def turn(harness, session, message):
    """One turn of a session on one harness. A session belongs to no harness: it is a mind (the home folder,
    where each harness keeps its own memory), a work folder they share, and what was said. A harness that was
    not the one answering is told what it missed, so the person never sees the change."""
    folder = DATA / "sessions" / session
    mind, work, record = folder / "mind", folder / "work", folder / "session.json"
    if not folder.exists():
        for each in (mind, work, DATA / "tools"):
            each.mkdir(parents=True, exist_ok=True)
            each.chmod(0o777)                            # the sandbox's user is not this one
        shutil.copy(HERE / "agent" / "AGENTS.md", work)  # who the agent is: every harness reads it unasked
    kept = json.loads(record.read_text()) if record.exists() else {"turns": [], "threads": {}}
    mine = kept["threads"].setdefault(harness, {"id": None, "seen": 0})
    missed = "".join(f"{each['role']}: {each['text']}\n\n" for each in kept["turns"][mine["seen"]:])
    asked = message if not missed else ("Here is what was said in this conversation since you last replied. Carry on "
                                        f"from it as the assistant.\n\n{missed}user: {message}")
    events = run(PROGRAMS[harness], mind, work, {"message": asked, "thread": mine["id"]})
    mine["id"] = next((event["id"] for event in events if event["type"] == "thread"), mine["id"])
    events = [event for event in events if event["type"] != "thread"]        # the thread is the harness's, kept here
    said = "\n\n".join(event["text"] for event in events if event["type"] == "text")
    kept["turns"] += [{"role": "user", "text": message}, {"role": "assistant", "text": said}]
    mine["seen"] = len(kept["turns"])
    record.write_text(json.dumps(kept))
    return events


class Console(BaseHTTPRequestHandler):
    def do_GET(self):
        options = "".join(f"<option>{name}" for name in PROGRAMS)
        self.reply("text/html; charset=utf-8",
                   (HERE / "agent" / "console.html").read_text().replace("<!--harnesses-->", options))

    def do_POST(self):                                   # taken only as application/json, which another site's page
        if self.headers.get("Content-Type") != "application/json":             # cannot send unasked
            return self.send_error(400, "send application/json")
        asked = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if (asked.get("harness") not in PROGRAMS or not asked.get("message")
                or not re.fullmatch(r"[0-9a-f]{32}", str(asked.get("session")))):
            return self.send_error(400, "a turn is a harness, a session, and a message")
        events = turn(asked["harness"], asked["session"], asked["message"])
        self.reply("application/x-ndjson", "".join(json.dumps(event) + "\n" for event in events))

    def reply(self, kind, text):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(text.encode())))
        self.end_headers()
        self.wfile.write(text.encode())


if __name__ == "__main__":
    print(f"the agent is on http://127.0.0.1:8500/, with {', '.join(PROGRAMS)} behind it", flush=True)
    HTTPServer(("127.0.0.1", 8500), Console).serve_forever()
