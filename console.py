#!/usr/bin/env python3
"""console.py: the chat console, and everything about driving a harness that is the same for every harness.

A harness is a module with NAME, PACKAGE, command(tools, session, message) and handle(line): one of the
agent-<harness>.py files. This file installs it, keeps sessions, runs a turn, and serves the page. A turn is one
request, the same for every harness:

    {"harness": "codex", "session": "…", "message": "…"}

With --sandbox, every harness is installed and run in a container that is thrown away. Standard library only.
"""
import importlib.util
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
SANDBOX = "--sandbox" in sys.argv
DATA = HERE / "data" / ("sandbox" if SANDBOX else "host")
BOX = ["docker", "run", "--rm", "-i", "--init", "--cpus=2", "--memory=4g", "--pids-limit=512", "--read-only",
       "--tmpfs=/tmp:rw,exec,size=1g", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10000:10000"]
harnesses, running = {}, {}                              # by name; and by session, while a turn is in progress


def load(name):
    """The harness module in agent-<name>.py."""
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"agent-{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def start(argv, env, folders, **pipes):
    """Start a program where harnesses run, on these folders. The first folder is its working folder. Here, that
    is this machine. With --sandbox it is a container that sees those folders, each at /<its name>, and no more."""
    if not SANDBOX:                                      # PWD too: one harness takes its working folder from it
        here = str(next(iter(folders.values())))
        return subprocess.Popen(argv, cwd=here, env={**os.environ, **env, "PWD": here}, **pipes)
    seen = [f"--volume={path}:/{name}" for name, path in folders.items()]
    return subprocess.Popen([*BOX, *seen, f"--workdir=/{next(iter(folders))}", *(f"--env={name}" for name in env),
                             "node:22", *argv], env={**os.environ, **env}, **pipes)       # values go by the environment


def at(name, path):
    """A folder, as a program started by start() sees it."""
    return f"/{name}" if SANDBOX else str(path)


def installed(harness):
    """Where this harness's programs are, as it sees them. It is installed once, at its pinned version."""
    tools = DATA / "tools"
    if not (tools / harness.NAME / ".installed").exists():
        tools.mkdir(parents=True, exist_ok=True)
        tools.chmod(0o777)                               # the sandbox's user is not this one
        npm = ["npm", "install", "--prefix", f"{at('tools', tools)}/{harness.NAME}", "--no-audit", "--no-fund",
               "--loglevel=error", harness.PACKAGE]
        if start(npm, {"HOME": "/tmp", "npm_config_cache": "/tmp/npm"} if SANDBOX else {}, {"tools": tools}).wait():
            raise RuntimeError(f"could not install {harness.PACKAGE}")
        (tools / harness.NAME / ".installed").touch()
    return f"{at('tools', tools)}/{harness.NAME}/node_modules/.bin"


def turn(harness, session, message):
    """One turn of a session on one harness, as the events the page shows. A session belongs to no harness: it is
    a mind (the home folder, where each harness keeps its own memory), a work folder they share, and what was
    said. A harness that was not the one answering is told what it missed, so the person never sees the change."""
    folder = DATA / "sessions" / session
    mind, work, record = folder / "mind", folder / "work", folder / "session.json"
    if not folder.exists():
        for each in (mind, work):
            each.mkdir(parents=True)
            each.chmod(0o777)
        shutil.copy(HERE / "agent" / "AGENTS.md", work)  # who the agent is: every harness reads it unasked
    kept = json.loads(record.read_text()) if record.exists() else {"title": message[:60], "turns": [], "ids": {}}
    mine = kept["ids"].setdefault(harness.NAME, {"id": None, "seen": 0})
    missed = "".join(f"{each['role']}: {each['text']}\n\n" for each in kept["turns"][mine["seen"]:])
    asked = message if not missed else ("Here is what was said in this conversation since you last replied. Carry on "
                                        f"from it as the assistant.\n\n{missed}user: {message}")
    argv, env = harness.command(installed(harness), mine["id"], asked)
    with open(folder / "log.txt", "ab") as log:
        process = running[session] = start(argv, {**env, "HOME": at("mind", mind)},
                                           {"work": work, "mind": mind, "tools": DATA / "tools"},
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log)
        said, steps = [], []
        for printed in process.stdout:
            try:
                events = list(harness.handle(json.loads(printed)))
            except ValueError:
                continue                                 # not a line of JSON
            for event in events:
                if event["type"] == "harness_session":
                    mine["id"] = event["id"]             # its own id for the session: how it is continued
                    continue
                (said if event["type"] == "text" else steps).append(event["text"])
                yield event
        ok = process.wait() == 0
    del running[session]
    kept["turns"] += [{"role": "user", "text": message},
                      {"role": "assistant", "text": "\n\n".join(said), "steps": steps, "harness": harness.NAME}]
    mine["seen"] = len(kept["turns"])
    record.write_text(json.dumps(kept))
    yield {"type": "done", "ok": ok}


class Console(BaseHTTPRequestHandler):
    def do_GET(self):
        record = DATA / "sessions" / self.path.rpartition("/")[2] / "session.json"
        if self.path == "/":
            self.reply("text/html; charset=utf-8", (HERE / "console.html").read_bytes())
        elif self.path == "/sessions":
            records = sorted((DATA / "sessions").glob("*/session.json"), key=os.path.getmtime, reverse=True)
            self.reply("application/json", json.dumps({"harnesses": list(harnesses), "sessions": [
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
        if asked.get("harness") not in harnesses or not asked.get("message"):
            return self.send_error(400, "a turn is a harness, a session, and a message")
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        events, here = turn(harnesses[asked["harness"]], session, asked["message"]), True
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


def serve(modules):
    """The console, with these harnesses behind it."""
    harnesses.update({module.NAME: module for module in modules})
    (DATA / "sessions").mkdir(parents=True, exist_ok=True)
    where = "in a sandbox" if SANDBOX else "on this machine"
    print(f"the console is on http://127.0.0.1:8500/: {', '.join(harnesses)}, {where}")
    ThreadingHTTPServer(("127.0.0.1", 8500), Console).serve_forever()
