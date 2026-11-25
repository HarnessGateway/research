#!/usr/bin/env python3
"""OpenAIResponses-experiment-claude-code.py: Claude Code, driven by OpenAI Responses requests and nothing else.

    DEEPSEEK_API_KEY=… python3 OpenAIResponses-experiment-claude-code.py

It installs Claude Code, then answers every OpenAIResponses-turn-<n>.json beside it, in order, as one session: a
Responses request in, a Responses response out, with the events of its stream when the request asks for one. What
came back is kept under agent/data/experiment/claude-code/. It acts without asking, there: run it in a container.
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
NAME, PACKAGE = "claude-code", "@anthropic-ai/claude-code@2.1.325"  # its latest stable version, pinned
TOOLS = HERE / "agent/data/tools" / f"{NAME}-{sys.platform}"
SESSION = HERE / "agent/data/experiment" / NAME
MIND, WORK = SESSION / "mind", SESSION / "work"         # the session: the harness's home, and its working folder
KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ENDPOINTS = {"deepseek": "https://api.deepseek.com/anthropic"}     # the one API it speaks, by provider
HONOURED = {"input", "instructions", "reasoning", "text", "tools"}  # the fields of a request it is given


class Unsupported(Exception):
    """The request asks for what this harness cannot be given. The message names it."""


def install():
    subprocess.run(["npm", "install", "--prefix", TOOLS, "--no-audit", "--no-fund", "--loglevel=error", PACKAGE],
                   check=True, stdout=sys.stderr)


def as_input(request, kept):                             # input: one message on standard input, words and images
    words, images, told = given(request, kept)
    blocks = [{"type": "text", "text": words}, *(
        {"type": "image", "source": {"type": "base64", "media_type": f"image/{path.suffix[1:]}",
                                     "data": base64.b64encode(path.read_bytes()).decode()}} for path in images)]
    return json.dumps({"type": "user", "message": {"role": "user", "content": blocks}}) + "\n", told


def context(request, told, thread):                      # context: this response's instructions, written anew, and
    known = SESSION / "instructions.md"                  # its own session to carry on from
    known.write_text("\n\n".join(part for part in [request.get("instructions"), *told] if part))
    return ["--append-system-prompt-file", known, "--system-prompt-snapshot", "off",
            *(["--resume", thread] if thread else [])]


def model_interface(request):                            # model interface: endpoint, key, and model as variables,
    provider, model = request["model"].split("/", 3)[2:]                # and how hard it thinks as a flag
    effort = (request.get("reasoning") or {}).get("effort")
    return (["--effort", effort] if effort else []), {
        "ANTHROPIC_BASE_URL": ENDPOINTS[provider], "ANTHROPIC_AUTH_TOKEN": KEY, "ANTHROPIC_MODEL": model,
        "ANTHROPIC_SMALL_FAST_MODEL": model, "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1"}


def output(request, state):                              # output: every step as a line of JSON, an answer that fits
    args = ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]   # a schema, and the
    shape = (request.get("text") or {}).get("format") or {}                                # caller's own tools
    if shape.get("type") == "json_schema":
        args, state["schema"] = [*args, "--json-schema", json.dumps(shape["schema"])], True
    elif shape.get("type") not in (None, "text"):
        raise Unsupported(f"text.format of type {shape['type']}")
    if any(tool["type"] != "function" for tool in request.get("tools") or []):
        raise Unsupported("a tool that is not a function")
    if callers(request):                                 # offered by a tool server: this program, run as one
        args += ["--mcp-config", json.dumps({"mcpServers": {"caller": {
            "type": "stdio", "command": sys.executable, "args": [__file__, "--caller-tools", json.dumps(callers(request))]}}})]
    return args


def control_flow():                                      # control flow: one turn, nobody there, acting unasked
    return ["-p", "--input-format", "stream-json", "--dangerously-skip-permissions"]


def command(request, state, kept):                       # the command, from its five parts
    fed, told = as_input(request, kept)
    thinking, env = model_interface(request)
    return [TOOLS / "node_modules/.bin/claude", *control_flow(), *context(request, told, state["thread"]), *thinking,
            *output(request, state)], env, fed


def handle(line, state):                                 # output: one line it printed, as Responses output items
    kind = line.get("type")
    if kind == "system" and line.get("subtype") == "init":
        state["thread"] = line["session_id"]
    elif kind == "stream_event" and line["event"].get("type") == "message_delta":      # one model call's tokens
        count = line["event"].get("usage") or {}
        cached = count.get("cache_read_input_tokens", 0)
        state["usage"][0] += count.get("input_tokens", 0) + cached + count.get("cache_creation_input_tokens", 0)
        state["usage"][1] += cached
        state["usage"][2] += count.get("output_tokens", 0)
        state["stop"] = bool(state.get("handed"))        # counted: a turn that ended on the caller's tool stops here
    elif kind == "assistant" and not line.get("parent_tool_use_id"):
        for block in line["message"]["content"]:
            if block["type"] == "text" and block["text"].strip() and not state.get("schema"):
                yield message(block["text"])
            elif block["type"] == "thinking" and block.get("thinking"):
                yield reasoning(block["thinking"])
            elif block["type"] == "tool_use" and block["name"].startswith("mcp__caller__"):
                state["handed"] = True
                yield asked(block["id"], block["name"][len("mcp__caller__"):], block.get("input") or {})
            elif block["type"] == "tool_use" and block["name"] != "StructuredOutput":
                state["pending"][block["id"]] = (block["name"], block.get("input") or {})
    elif kind == "user":
        for block in line["message"]["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block["tool_use_id"] in state["pending"]:
                call_id, (name, sent) = block["tool_use_id"], state["pending"].pop(block["tool_use_id"])
                text = block["content"] if isinstance(block["content"], str) else "\n".join(
                    each.get("text", "") for each in block["content"] or [])
                if name == "Bash":
                    yield from ran(call_id, sent.get("command", ""), text, int(bool(block.get("is_error"))))
                elif name in ("Write", "Edit"):
                    diff = "".join(f"+{each}\n" for each in sent.get("content", "").splitlines()) if name == "Write" \
                        else f"-{sent.get('old_string', '')}\n+{sent.get('new_string', '')}\n"
                    yield from changed(call_id, sent.get("file_path", ""), diff, name == "Write")
                else:
                    yield from used(call_id, name, sent, text)
    elif kind == "result":
        if line.get("is_error"):
            state["error"] = str(line.get("result") or line.get("subtype"))
        elif line.get("structured_output") is not None:  # with a schema, the answer is what fits it
            yield message(json.dumps(line["structured_output"]))


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
