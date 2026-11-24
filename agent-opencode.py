#!/usr/bin/env python3
"""agent-opencode.py: a chat agent with OpenCode as its harness.

    python3 agent-opencode.py          # then open http://127.0.0.1:8500/
"""
import os

NAME, PACKAGE = "opencode", "opencode-ai@1.19.6"         # its latest stable version, pinned
MODEL = "deepseek-flash"


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(session):                                    # context: AGENTS.md is read from the working folder unasked.
    return ["--session", session] if session else []     # This is the conversation so far


def model_interface():                                   # model interface: a provider it knows by name, with the
    return ["-m", f"deepseek/{MODEL}"], {                # model, and the key in a variable
        "DEEPSEEK_API_KEY": os.environ["DEEPSEEK_API_KEY"]}


def output():                                            # output: act without asking, and print every step as JSON
    return ["--auto", "--format", "json"]


def control_flow():                                      # control flow: one request, then exit. A bound is a setting
    return ["run"]


def command(tools, session, message):                    # the one-liner, from its five parts
    model, env = model_interface()
    return [f"{tools}/opencode", *control_flow(), *context(session), *model, *output(), *as_input(message)], env


def handle(line):                                        # output: one line it printed, as what the console shows
    part = line.get("part") or {}
    if line.get("sessionID"):
        yield {"type": "harness_session", "id": line["sessionID"]}
    if line["type"] == "text":
        yield {"type": "text", "text": part["text"]}
    if line["type"] == "tool_use":
        given = part["state"].get("input") or {}
        yield {"type": "step", "text": f"$ {given['command']}" if "command" in given
               else f"{part['tool']} {given.get('filePath', '')}"}
    if line["type"] == "error":
        yield {"type": "error", "text": line["error"].get("data", {}).get("message") or line["error"].get("name")}


if __name__ == "__main__":
    import sys

    import console
    console.serve([sys.modules[__name__]])
