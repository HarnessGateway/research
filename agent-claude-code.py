#!/usr/bin/env python3
"""agent-claude-code.py: Claude Code, driven by a program. One request in, what it did out, as lines of JSON.

    echo '{"message": "Create notes.txt containing the word PELICAN."}' | python3 agent-claude-code.py

It works in the folder it is started in, and acts without asking.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

NAME, PACKAGE = "claude-code", "@anthropic-ai/claude-code@2.1.325"  # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(__file__).resolve().parent / "agent/data/tools" / f"{NAME}-{sys.platform}"


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(thread):                                     # context: AGENTS.md is read from the working folder unasked.
    return ["--resume", thread] if thread else []        # This is the conversation so far


def model_interface():                                   # model interface: the model is a flag, the endpoint and key
    return ["--model", MODEL], {                         # are in the environment
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": os.environ["DEEPSEEK_API_KEY"]}


def output():                                            # output: act without asking, and print every step as JSON
    return ["--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose"]


def control_flow():                                      # control flow: one request, at most 50 turns, then exit
    return ["-p", "--max-turns", "50"]


def command(thread, message):                            # the one-liner, from its five parts
    model, env = model_interface()
    return [TOOLS / "node_modules/.bin/claude", *control_flow(), *context(thread), *model, *output(),
            *as_input(message)], env


def handle(line):                                        # output: one line it printed, as events
    if line.get("subtype") == "init":
        yield {"type": "thread", "id": line["session_id"]}
    if line.get("type") == "assistant":
        for block in line["message"]["content"]:
            if block["type"] == "text":
                yield {"type": "text", "text": block["text"]}
            if block["type"] == "tool_use":
                yield {"type": "step", "text": block["input"].get("command") or block["input"].get("file_path")
                       or block["name"]}
    if line.get("type") == "result" and line.get("is_error"):
        yield {"type": "error", "text": str(line.get("result") or line.get("subtype"))}


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
