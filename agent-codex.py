#!/usr/bin/env python3
"""agent-codex.py: Codex, driven by a program. One request in, what it did out, as lines of JSON.

    echo '{"message": "Create notes.txt containing the word PELICAN."}' | python3 agent-codex.py

It works in the folder it is started in, and acts without asking.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

NAME, PACKAGE = "codex", "@openai/codex@0.172.0"         # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(__file__).resolve().parent / "agent/data/tools" / f"{NAME}-{sys.platform}"
PROVIDER = ('model_providers.deepseek={name="DeepSeek",base_url="https://api.deepseek.com/v1",'
            'env_key="DEEPSEEK_API_KEY",wire_api="responses"}')


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(thread):                                     # context: AGENTS.md is read from the working folder unasked.
    return ["resume", thread] if thread else []          # This is the conversation so far


def model_interface():                                   # model interface: the provider is a setting, the model a
    return ["-c", "model_provider=deepseek", "-c", PROVIDER, "-m", MODEL], {}      # flag, the key a variable it names


def output():                                            # output: act without asking, and print every step as JSON
    return ["--dangerously-bypass-approvals-and-sandbox", "--json"]


def control_flow():                                      # control flow: one request, then exit. It has no bound
    return ["exec"]


def command(thread, message):                            # the one-liner, from its five parts
    model, env = model_interface()
    return [TOOLS / "node_modules/.bin/codex", *control_flow(), *context(thread), "--skip-git-repo-check", *model,
            *output(), *as_input(message)], env


def handle(line):                                        # output: one line it printed, as events
    item = line.get("item") or {}
    if line["type"] == "thread.started":
        yield {"type": "thread", "id": line["thread_id"]}
    if line["type"] == "item.completed" and item["type"] == "agent_message":
        yield {"type": "text", "text": item["text"]}
    if line["type"] == "item.completed" and item["type"] == "command_execution":
        yield {"type": "step", "text": item["command"]}
    if line["type"] == "item.completed" and item["type"] == "file_change":
        yield {"type": "step", "text": ", ".join(change["path"] for change in item["changes"])}
    if line["type"] == "turn.failed":
        yield {"type": "error", "text": line["error"]["message"]}


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
