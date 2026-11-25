#!/usr/bin/env python3
"""OpenAIResponses-experiment-pi.py: Pi, driven by OpenAI Responses requests and nothing else.

    DEEPSEEK_API_KEY=… python3 OpenAIResponses-experiment-pi.py

It installs Pi, then answers every OpenAIResponses-turn-<n>.json beside it, in order, as one session: a
Responses request in, a Responses response out, with the events of its stream when the request asks for one. What
came back is kept under agent/data/experiment/pi/. It acts without asking, there: run it in a container.
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
NAME, PACKAGE = "pi", "@mariozechner/pi-coding-agent@0.73.1"       # the version this ran on; Pi is now @earendil-works/pi-coding-agent
TOOLS = HERE / "agent/data/tools" / f"{NAME}-{sys.platform}"
SESSION = HERE / "agent/data/experiment" / NAME
MIND, WORK = SESSION / "mind", SESSION / "work"         # the session: the harness's home, and its working folder
KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ENDPOINTS = {"deepseek": "https://api.deepseek.com/anthropic"}    # reached as an Anthropic Messages provider
HONOURED = {"input", "instructions", "reasoning", "tools"}        # the fields of a request it is given
CONFIG = MIND / ".pi/agent"                              # its own settings, and its record of a session


class Unsupported(Exception):
    """The request asks for what this harness cannot be given. The message names it."""


def install():
    subprocess.run(["npm", "install", "--prefix", TOOLS, "--no-audit", "--no-fund", "--loglevel=error", PACKAGE],
                   check=True, stdout=sys.stderr)


def as_input(request, kept):                             # input: the words on standard input, each image a file
    words, images, told = given(request, kept)
    return words, [f"@{path}" for path in images], told


def context(request, told, thread):                      # context: this response's instructions, in a file it
    said = "\n\n".join(part for part in [request.get("instructions"), *told] if part)      # appends to its own
    CONFIG.mkdir(parents=True, exist_ok=True)                                               # prompt, and its session
    (CONFIG / "APPEND_SYSTEM.md").write_text(said)
    return ["--session", thread] if thread else []


def model_interface(request):                            # model interface: a provider and a model, in its settings
    provider, model = request["model"].split("/", 3)[2:]
    effort = (request.get("reasoning") or {}).get("effort")
    (CONFIG / "models.json").write_text(json.dumps({"providers": {"experiment": {
        "baseUrl": ENDPOINTS[provider], "api": "anthropic-messages", "apiKey": "DEEPSEEK_API_KEY", "models": [{
            "id": model, "name": model, "reasoning": True, "input": ["text", "image"], "contextWindow": 200000,
            "maxTokens": 8192}]}}}))
    return ["--provider", "experiment", "--model", model, *(["--thinking", effort] if effort else [])], {
        "PI_OFFLINE": "1", "PI_TELEMETRY": "0", "PI_CODING_AGENT_DIR": str(CONFIG), "DEEPSEEK_API_KEY": KEY}


def output(request):                                     # output: every step as a line of JSON, and the caller's
    args = ["--mode", "json", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-context-files"]
    if any(tool["type"] != "function" for tool in request.get("tools") or []):             # own tools
        raise Unsupported("a tool that is not a function")
    if callers(request):                                 # it has no tool-server client: they are an extension, each
        (SESSION / "caller-tools.js").write_text(        # of which ends its work when it is called
            "export default function (pi) {\n  for (const t of " + json.dumps(callers(request)) + ") pi.registerTool({\n"
            "    name: t.name, label: t.name, description: t.description, parameters: t.inputSchema,\n"
            "    async execute() { return { content: [{ type: \"text\", text: \"This call is with the caller.\" }], "
            "terminate: true }; } });\n}\n")
        args += ["--extension", SESSION / "caller-tools.js"]
    return args


def control_flow():                                      # control flow: one turn, nobody there, acting unasked
    return ["--print"]


def command(request, state, kept):                       # the command, from its five parts
    words, images, told = as_input(request, kept)
    resume = context(request, told, state["thread"])
    model, env = model_interface(request)
    return [TOOLS / "node_modules/.bin/pi", *model, *resume, *output(request), *control_flow(), *images], env, words


def handle(line, state):                                 # output: one line it printed, as Responses output items
    kind, said = line.get("type"), line.get("message") or {}
    if kind == "session":
        state["thread"] = line["id"]
    elif kind == "message_update" and (line.get("assistantMessageEvent") or {}).get("type") == "toolcall_end":
        call = line["assistantMessageEvent"].get("toolCall") or {}
        state["pending"][call["id"]] = (call["name"], call.get("arguments") or {})
    elif kind == "tool_execution_end" and line.get("toolCallId") in state["pending"]:
        call_id, (name, sent) = line["toolCallId"], state["pending"].pop(line["toolCallId"])
        result = line.get("result")
        text = "\n".join(each.get("text", "") for each in result.get("content") or []) if isinstance(result, dict) else str(result)
        if name in state["callers"]:                     # the caller's: it was said when the message ended
            pass
        elif name == "bash":
            yield from ran(call_id, sent.get("command", ""), text, int(bool(line.get("isError"))))
        elif name in ("write", "edit"):
            diff = "".join(f"+{each}\n" for each in sent.get("content", "").splitlines()) if name == "write" \
                else f"-{sent.get('oldText', '')}\n+{sent.get('newText', '')}\n"
            yield from changed(call_id, sent.get("path", ""), diff, name == "write")
        else:
            yield from used(call_id, name, sent, text)
    elif kind == "message_end" and said.get("role") == "assistant":
        for block in said.get("content") or []:
            if block.get("type") == "thinking" and block.get("thinking"):
                yield reasoning(block["thinking"])
            elif block.get("type") == "text" and block.get("text", "").strip():
                yield message(block["text"])
        for call_id, (name, sent) in state["pending"].items():       # a tool only the caller can run comes last
            if name in state["callers"]:
                yield asked(call_id, name, sent)
        count = said.get("usage") or {}                  # one model call's tokens
        state["usage"][0] += count.get("input", 0) + count.get("cacheRead", 0) + count.get("cacheWrite", 0)
        state["usage"][1] += count.get("cacheRead", 0)
        state["usage"][2] += count.get("output", 0)
        state["error"] = said.get("errorMessage") or state["error"]


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
