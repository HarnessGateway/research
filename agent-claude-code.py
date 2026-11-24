#!/usr/bin/env python3
"""agent-claude-code.py: a chat agent with Claude Code as its harness.

    python3 agent-claude-code.py          # then open http://127.0.0.1:8500/
"""
import os

NAME, PACKAGE = "claude-code", "@anthropic-ai/claude-code@2.1.325"       # its latest stable version, pinned
MODEL = "deepseek-flash"


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(session):                                    # context: AGENTS.md is read from the working folder unasked.
    return ["--resume", session] if session else []      # This is the conversation so far


def model_interface():                                   # model interface: the model is a flag, the endpoint and key
    return ["--model", MODEL], {                         # are in the environment
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": os.environ["DEEPSEEK_API_KEY"]}


def output():                                            # output: act without asking, and print every step as JSON
    return ["--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose"]


def control_flow():                                      # control flow: one request, at most 50 turns, then exit
    return ["-p", "--max-turns", "50"]


def command(tools, session, message):                    # the one-liner, from its five parts
    model, env = model_interface()
    return [f"{tools}/claude", *control_flow(), *context(session), *model, *output(), *as_input(message)], env


def handle(line):                                        # output: one line it printed, as what the console shows
    if line.get("subtype") == "init":
        yield {"type": "harness_session", "id": line["session_id"]}
    if line.get("type") == "assistant":
        for block in line["message"]["content"]:
            if block["type"] == "text":
                yield {"type": "text", "text": block["text"]}
            if block["type"] == "tool_use":
                given = block["input"]
                yield {"type": "step", "text": f"$ {given['command']}" if "command" in given
                       else f"{block['name']} {given.get('file_path', '')}"}
    if line.get("type") == "result" and line.get("is_error"):
        yield {"type": "error", "text": str(line.get("result") or line.get("subtype"))}


if __name__ == "__main__":
    import sys

    import console
    console.serve([sys.modules[__name__]])
