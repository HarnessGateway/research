#!/usr/bin/env python3
"""agent-codex.py: a chat agent with Codex as its harness.

    python3 agent-codex.py          # then open http://127.0.0.1:8500/
"""
import os

NAME, PACKAGE = "codex", "@openai/codex@0.171.0"         # its latest stable version, pinned
MODEL = "deepseek-flash"
PROVIDER = ('model_providers.deepseek={name="DeepSeek",base_url="https://api.deepseek.com/v1",'
            'env_key="DEEPSEEK_API_KEY",wire_api="responses"}')


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(session):                                    # context: AGENTS.md is read from the working folder unasked.
    return ["resume", session] if session else []        # This is the conversation so far


def model_interface():                                   # model interface: the provider is a setting, the model a
    return ["-c", "model_provider=deepseek", "-c", PROVIDER, "-m", MODEL], {       # flag, the key a variable
        "DEEPSEEK_API_KEY": os.environ["DEEPSEEK_API_KEY"]}


def output():                                            # output: act without asking, and print every step as JSON
    return ["--dangerously-bypass-approvals-and-sandbox", "--json"]


def control_flow():                                      # control flow: one request, then exit. It has no bound
    return ["exec"]


def command(tools, session, message):                    # the one-liner, from its five parts
    model, env = model_interface()
    return [f"{tools}/codex", *control_flow(), *context(session), "--skip-git-repo-check", *model, *output(),
            *as_input(message)], env


def handle(line):                                        # output: one line it printed, as what the console shows
    item = line.get("item") or {}
    if line["type"] == "thread.started":
        yield {"type": "harness_session", "id": line["thread_id"]}
    if line["type"] == "item.completed" and item["type"] == "agent_message":
        yield {"type": "text", "text": item["text"]}
    if line["type"] == "item.completed" and item["type"] == "command_execution":
        yield {"type": "step", "text": f"$ {item['command']}"}
    if line["type"] == "item.completed" and item["type"] == "file_change":
        yield {"type": "step", "text": "edit " + ", ".join(change["path"] for change in item["changes"])}
    if line["type"] == "turn.failed":
        yield {"type": "error", "text": line["error"]["message"]}


if __name__ == "__main__":
    import sys

    import console
    console.serve([sys.modules[__name__]])
