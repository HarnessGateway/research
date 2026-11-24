#!/usr/bin/env python3
"""agent-opencode.py: OpenCode, driven by a program. One request in, what it did out, as lines of JSON.

    echo '{"message": "Create notes.txt containing the word PELICAN."}' | python3 agent-opencode.py

It works in the folder it is started in, and acts without asking.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

NAME, PACKAGE = "opencode", "opencode-ai@1.19.6"         # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(__file__).resolve().parent / "agent/data/tools" / f"{NAME}-{sys.platform}"


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(thread):                                     # context: AGENTS.md is read from the working folder unasked.
    return ["--session", thread] if thread else []       # This is the conversation so far


def model_interface():                                   # model interface: a provider it knows by name, with the
    return ["-m", f"deepseek/{MODEL}"], {}               # model. It finds the key in the environment itself


def output():                                            # output: act without asking, and print every step as JSON
    return ["--auto", "--format", "json"]


def control_flow():                                      # control flow: one request, then exit. A bound is a setting
    return ["run"]


def command(thread, message):                            # the one-liner, from its five parts. PWD, because that is
    model, env = model_interface()                       # where it takes its working folder from
    return [TOOLS / "node_modules/.bin/opencode", *control_flow(), *context(thread), *model, *output(),
            *as_input(message)], {**env, "PWD": os.getcwd()}


def handle(line):                                        # output: one line it printed, as events
    part = line.get("part") or {}
    if line["type"] == "step_start":                     # its id is on every line: once a step is enough
        yield {"type": "thread", "id": line["sessionID"]}
    if line["type"] == "text":
        yield {"type": "text", "text": part["text"]}
    if line["type"] == "tool_use":
        given = part["state"].get("input") or {}
        yield {"type": "step", "text": given.get("command") or given.get("filePath") or part["tool"]}
    if line["type"] == "error":
        yield {"type": "error", "text": line["error"].get("data", {}).get("message") or line["error"].get("name")}


if __name__ == "__main__":
    if not (TOOLS / ".installed").exists():              # installed once, at its pinned version
        subprocess.run(["npm", "install", "--prefix", TOOLS, "--no-audit", "--no-fund", "--loglevel=error", PACKAGE],
                       check=True, stdout=sys.stderr)
        (TOOLS / ".installed").touch()
    request = json.load(sys.stdin)
    argv, env = command(request.get("thread"), request["message"])
    harness = subprocess.Popen(argv, env={**os.environ, **env}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    for printed in harness.stdout:
        if printed.startswith(b"{"):                     # a line of JSON
            for event in handle(json.loads(printed)):
                print(json.dumps(event), flush=True)
    sys.exit(harness.wait())
