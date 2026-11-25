#!/usr/bin/env python3
"""OpenAIResponses-experiment-codex.py: Codex, driven by OpenAI Responses requests and nothing else.

    DEEPSEEK_API_KEY=… python3 OpenAIResponses-experiment-codex.py

It installs Codex, then answers every OpenAIResponses-turn-<n>.json beside it, in order, as one session: a
Responses request in, a Responses response out, with the events of its stream when the request asks for one. What
came back is kept under agent/data/experiment/codex/. It acts without asking, there: run it in a container.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME, PACKAGE = "codex", "@openai/codex@0.172.0"         # its latest stable version, pinned
TOOLS = HERE / "agent/data/tools" / f"{NAME}-{sys.platform}"
SESSION = HERE / "agent/data/experiment" / NAME
MIND, WORK = SESSION / "mind", SESSION / "work"         # the session: the harness's home, and its working folder
KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ENDPOINTS = {"deepseek": "https://api.deepseek.com/v1"}           # OpenAI Responses is the one API it speaks
HONOURED = {"input", "instructions", "reasoning", "text", "tools"}  # the fields of a request it is given


class Unsupported(Exception):
    """The request asks for what this harness cannot be given. The message names it."""


def install():
    subprocess.run(["npm", "install", "--prefix", TOOLS, "--no-audit", "--no-fund", "--loglevel=error", PACKAGE],
                   check=True, stdout=sys.stderr)


def as_input(request, kept):                             # input: the words on standard input, each image a file
    words, images, told = given(request, kept)
    return words, [f"--image={path}" for path in images], told


def context(request, told, thread):                      # context: its own thread to carry on from. A thread
    said = "\n\n".join(part for part in [request.get("instructions"), *told] if part)       # keeps the instructions
    return (["resume", thread] if thread else []), (     # it began with, so this response's go with its message
        f"Your instructions for this message, in place of any you were given before:\n{said}\n\n" if said else "")


def model_interface(request):                            # model interface: a provider and a model, in its config
    provider, model = request["model"].split("/", 3)[2:]
    thinking = request.get("reasoning") or {}
    return [f"model = {json.dumps(model)}", 'model_provider = "experiment"',
            *([f"model_reasoning_effort = {json.dumps(thinking['effort'])}"] if thinking.get("effort") else []),
            f"model_reasoning_summary = {json.dumps(thinking.get('summary') or 'none')}"], [
            "[model_providers.experiment]", 'name = "experiment"', f"base_url = {json.dumps(ENDPOINTS[provider])}",
            'env_key = "DEEPSEEK_API_KEY"', 'wire_api = "responses"']


def output(request):                                     # output: every step as a line of JSON, an answer that fits
    args, servers = ["--json"], []                       # a schema, and the caller's own tools
    shape = (request.get("text") or {}).get("format") or {}
    if shape.get("type") == "json_schema":
        (SESSION / "schema.json").write_text(json.dumps(shape["schema"]))
        args += ["--output-schema", SESSION / "schema.json"]
    elif shape.get("type") not in (None, "text"):
        raise Unsupported(f"text.format of type {shape['type']}")
    if any(tool["type"] != "function" for tool in request.get("tools") or []):
        raise Unsupported("a tool that is not a function")
    if callers(request):                                 # offered by a tool server: this program, run as one
        servers = ["[mcp_servers.caller]", f"command = {json.dumps(sys.executable)}",
                   f"args = {json.dumps([__file__, '--caller-tools', json.dumps(callers(request))])}"]
    return args, servers


def control_flow():                                      # control flow: one turn, nobody there, acting unasked
    return ["--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox"]


def command(request, state, kept):                       # the command, from its five parts. Its settings are one
    words, images, told = as_input(request, kept)        # file, written anew for every turn
    resume, said = context(request, told, state["thread"])
    model, provider = model_interface(request)
    args, servers = output(request)
    (MIND / ".codex").mkdir(parents=True, exist_ok=True)
    (MIND / ".codex/config.toml").write_text("\n".join(
        [*model, 'approval_policy = "never"', 'sandbox_mode = "danger-full-access"', *provider, *servers]) + "\n")
    return [TOOLS / "node_modules/.bin/codex", "exec", *resume, "-", *control_flow(), *args, *images], {
        "CODEX_HOME": str(MIND / ".codex"), "DEEPSEEK_API_KEY": KEY}, said + words


def handle(line, state):                                 # output: one line it printed, as Responses output items
    kind, item = line.get("type"), line.get("item") or {}
    what = item.get("type")
    if kind == "thread.started":
        state["thread"] = line["thread_id"]
    elif kind == "item.started" and what == "mcp_tool_call" and item.get("server") == "caller":
        state["stop"] = True                             # a tool only the caller can run: the turn ends on the call
        yield asked(item["id"], item["tool"], item.get("arguments") or {})
    elif kind == "item.completed" and what == "agent_message" and item.get("text"):
        yield message(item["text"])
    elif kind == "item.completed" and what == "reasoning" and item.get("text"):
        yield reasoning(item["text"])
    elif kind == "item.completed" and what == "command_execution":
        yield from ran(item["id"], item["command"], item.get("aggregated_output") or "", item.get("exit_code") or 0)
    elif kind == "item.completed" and what == "file_change":
        for number, change in enumerate(item.get("changes") or []):
            yield from changed(f"{item['id']}:{number}", change["path"], "", change.get("kind") == "add")
    elif kind == "turn.completed":
        count = line.get("usage") or {}
        state["usage"] = [count.get("input_tokens", 0), count.get("cached_input_tokens", 0), count.get("output_tokens", 0)]
    elif kind == "turn.failed":
        state["error"] = (line.get("error") or {}).get("message")


# What every one of these programs shares: Responses in, Responses out, and nothing of the harness's own.

PLATFORM = {"model", "stream", "store", "previous_response_id", "metadata"}        # acted on here, not by the harness


def message(text):                                       # what the agent said, as an output item
    return {"type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


def reasoning(text):                                     # what it thought
    return {"type": "reasoning", "summary": [{"type": "summary_text", "text": text}]}


def ran(call_id, command, printed, code):                # a command it ran itself, and what came of it
    yield {"type": "shell_call", "call_id": call_id, "status": "completed", "action": {"commands": [command]}}
    yield {"type": "shell_call_output", "call_id": call_id, "status": "completed",
           "output": [{"stdout": printed, "stderr": "", "outcome": {"type": "exit", "exit_code": code}}]}


def changed(call_id, path, diff, made):                  # a file it created or changed itself
    yield {"type": "apply_patch_call", "call_id": call_id, "status": "completed",
           "operation": {"type": "create_file" if made else "update_file", "path": path, "diff": diff}}
    yield {"type": "apply_patch_call_output", "call_id": call_id, "status": "completed"}


def used(call_id, name, given, result):                  # any other tool of its own
    yield {"type": "custom_tool_call", "call_id": call_id, "name": name, "input": json.dumps(given)}
    yield {"type": "custom_tool_call_output", "call_id": call_id, "status": "completed", "output": str(result)}


def asked(call_id, name, given):                         # a tool only the caller can run: the turn ends on it
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(given),
            "status": "completed"}


def callers(request):
    """The request's tools that only its caller can run, as a tool server lists them."""
    return [{"name": tool["name"], "description": tool.get("description") or "",
             "inputSchema": tool.get("parameters") or {"type": "object"}}
            for tool in request.get("tools") or [] if tool["type"] == "function"]


def serve_callers(tools):
    """A tool server for the caller's tools, on standard input and output. It runs none of them: a call is
    answered at once, saying it is with the caller, and the program driving the harness ends the turn on it."""
    for line in sys.stdin:
        asked_for = json.loads(line)
        method, answer = asked_for.get("method"), {}
        if method == "initialize":
            answer = {"protocolVersion": asked_for["params"].get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "caller", "version": "1"}}
        elif method == "tools/list":
            answer = {"tools": tools}
        elif method == "tools/call":
            answer = {"content": [{"type": "text", "text": "This call is with the caller, who runs this tool. "
                                   "Its result comes with the caller's next message."}]}
        if "id" in asked_for:
            print(json.dumps({"jsonrpc": "2.0", "id": asked_for["id"], "result": answer}), flush=True)


def given(request, kept):
    """The request's input, taken apart for any harness: the words, the images (each as a file), and what a
    developer or the system said. A file sent inside the request is put in the working folder."""
    words, images, told = [], [], []
    items = request["input"]
    for item in [{"role": "user", "content": items}] if isinstance(items, str) else items:
        kind, role, content = item.get("type", "message"), item.get("role"), item.get("content")
        parts = [{"type": "input_text", "text": content}] if isinstance(content, str) else content or []
        if kind == "function_call_output":
            name = kept["calls"].get(item["call_id"], "")
            words.append(f"The caller ran its tool {name} for your call, and it returned:\n{item['output']}")
        elif kind == "message" and role in ("developer", "system"):
            told += [part["text"] for part in parts]
        elif kind == "message" and role == "assistant":
            words += [f"Earlier, you said: {part['text']}" for part in parts]
        elif kind == "message" and role == "user":
            for part in parts:
                if part["type"] == "input_text":
                    words.append(part["text"])
                elif part["type"] == "input_image" and (part.get("image_url") or "").startswith("data:"):
                    media, _, data = part["image_url"][5:].partition(";base64,")
                    path = Path(tempfile.mkdtemp()) / f"image-{len(images) + 1}.{media.rpartition('/')[2]}"
                    path.write_bytes(base64.b64decode(data))
                    images.append(path)
                elif part["type"] == "input_file" and part.get("file_data"):
                    path = WORK / Path(part.get("filename") or "file").name
                    path.write_bytes(base64.b64decode(part["file_data"].rpartition(",")[2]))
                    words.append(f"A file given with this message is in your working folder: {path.name}")
                else:
                    raise Unsupported(f"an input part of type {part['type']}, given that way")
        else:
            raise Unsupported(f"an input item of type {kind}")
    return "\n\n".join(words), images, told


def respond(request, number, kept):
    """One Responses request, answered by the harness: the response object, and the events of its stream."""
    response = {
        "id": f"resp_turn_{number}", "object": "response", "created_at": int(time.time()), "status": "in_progress",
        "model": request["model"], "output": [], "usage": None, "error": None, "incomplete_details": None,
        "instructions": request.get("instructions"), "metadata": request.get("metadata") or {},
        "previous_response_id": request.get("previous_response_id"), "reasoning": request.get("reasoning"),
        "store": request.get("store", True), "text": request.get("text") or {"format": {"type": "text"}},
        "tools": request.get("tools") or [], "tool_choice": request.get("tool_choice", "auto"),
        "parallel_tool_calls": request.get("parallel_tool_calls", True)}
    events = []

    def event(kind, **more):
        events.append({"type": kind, "sequence_number": len(events), **more})

    def add(item):                                       # one output item: in its place, and as a stream carries it
        item, index = {"id": f"item_{number}_{len(response['output']) + 1}", **item}, len(response["output"])
        response["output"].append(item)
        event("response.output_item.added", output_index=index, item=item)
        if item["type"] == "message":
            at = {"item_id": item["id"], "output_index": index, "content_index": 0}
            event("response.output_text.delta", **at, delta=item["content"][0]["text"], logprobs=[])
            event("response.output_text.done", **at, text=item["content"][0]["text"], logprobs=[])
        event("response.output_item.done", output_index=index, item=item)

    event("response.created", response=json.loads(json.dumps(response)))
    state = {"thread": kept["threads"].get(request.get("previous_response_id")), "usage": [0, 0, 0], "error": None,
             "stop": False, "pending": {}, "callers": {tool["name"] for tool in callers(request)}}
    try:
        for name in sorted(set(request) - HONOURED - PLATFORM):
            if request[name] is not None:
                raise Unsupported(f"the request's {name}")
        argv, env, fed = command(request, state, kept)
        with open(SESSION / f"turn-{number}.log", "w") as log:
            cli = subprocess.Popen([str(part) for part in argv], cwd=WORK, text=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, env={**os.environ, "HOME": str(MIND), **env})
            cli.stdin.write(fed)
            cli.stdin.close()
            for printed in cli.stdout:
                log.write(printed)                       # everything the harness printed, as it printed it
                if printed.startswith("{"):
                    for item in handle(json.loads(printed), state):
                        if item["type"] == "function_call":                  # the caller's: named for this response
                            call_id = f"call_turn_{number}_{len(kept['calls']) + 1}"
                            kept["calls"][call_id], item = item["name"], {**item, "call_id": call_id}
                        add(item)
                if state["stop"]:                        # the turn ended on a call to the caller: stop the harness
                    cli.terminate()
                    break
            code = cli.wait()
        if state["error"] or (code != 0 and not state["stop"]):
            raise RuntimeError(state["error"] or f"{NAME} exited with code {code}: see turn-{number}.log")
        response["status"] = "completed"
    except Unsupported as what:
        response["status"] = "failed"
        response["error"] = {"code": "server_error", "message": f"{NAME} cannot be given {what}. Leave it out, "
                                                                 "or name another harness."}
    except RuntimeError as what:
        response["status"], response["error"] = "failed", {"code": "server_error", "message": str(what)[:2000]}
    kept["threads"][response["id"]] = state["thread"]
    took, cached, gave = state["usage"]
    if took or gave:
        response["usage"] = {"input_tokens": took, "input_tokens_details": {"cached_tokens": cached, "cache_write_tokens": 0},
                             "output_tokens": gave, "output_tokens_details": {"reasoning_tokens": 0},
                             "total_tokens": took + gave}
    event(f"response.{response['status']}", response=response)
    return response, events


if __name__ == "__main__":
    if sys.argv[1:2] == ["--caller-tools"]:               # this program, as the tool server for the caller's tools
        sys.exit(serve_callers(json.loads(sys.argv[2])))
    if not (TOOLS / ".installed").exists():              # installed once, at its pinned version
        TOOLS.mkdir(parents=True, exist_ok=True)
        install()
        (TOOLS / ".installed").touch()
    shutil.rmtree(SESSION, ignore_errors=True)           # a new session every run: its mind, and its work
    for folder in (MIND, WORK):
        folder.mkdir(parents=True)
    kept = {"threads": {}, "calls": {}}                  # what a server keeps between requests
    for path in sorted(HERE.glob("OpenAIResponses-turn-*.json"), key=lambda path: int(path.stem.rpartition("-")[2])):
        number, request = int(path.stem.rpartition("-")[2]), json.loads(path.read_text())
        response, events = respond(request, number, kept)
        (SESSION / f"turn-{number}.response.json").write_text(json.dumps(response, indent=2) + "\n")
        if request.get("stream"):
            (SESSION / f"turn-{number}.events.jsonl").write_text("".join(json.dumps(each) + "\n" for each in events))
        said = [part["text"] for item in response["output"] if item["type"] == "message" for part in item["content"]]
        print(json.dumps({"turn": number, "status": response["status"], "items": [item["type"] for item in response["output"]],
                          "said": said[-1][:300] if said else None, "error": (response["error"] or {}).get("message"),
                          "usage": response["usage"] and [response["usage"]["input_tokens"], response["usage"]["output_tokens"]]}),
              flush=True)
