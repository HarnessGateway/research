#!/usr/bin/env python3
"""The core: the OpenAI Responses API in front of harness packages, each run in a container.

    python3 core.py [--image node:22] [--port 8600]

POST /v1/responses with a `model` of harness/provider/model. The harness is a folder of ../packages holding
`install` and `run`; the provider is an entry of PROVIDERS, below. Each request is one turn: the package's `run`,
given the request as a file, in a container that is thrown away, on a session's two folders that are kept. A
request with `previous_response_id` runs on the same two folders, so the work carries on, whatever harness it
names. Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES, DATA, IMAGE = HERE.parent / "packages", HERE / "data", "node:22"
# Where models are served: the base URL of each API a provider speaks, and the variable that holds its key.
PROVIDERS = {"deepseek": {"key_env": "DEEPSEEK_API_KEY", "apis": {
    "anthropic": "https://api.deepseek.com/anthropic", "openai-responses": "https://api.deepseek.com/v1",
    "openai-chat": "https://api.deepseek.com/v1"}}}
# The container of stage 3: every turn runs in this, plus the folders and the variables of what runs in it.
SANDBOX = ["docker", "run", "--rm", "--init", "--cpus=2", "--memory=4g", "--pids-limit=512", "--read-only",
           "--tmpfs=/tmp:rw,exec,size=1g", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10000:10000"]
ENDINGS = {"response.completed": "completed", "response.incomplete": "incomplete", "response.failed": "failed"}
# Text a harness prints in pieces, by the line that carries it: the item it is gathered into, and where.
TEXT = {"response.output_text.delta": ({"type": "message", "role": "assistant", "status": "completed"}, "content",
                                       {"type": "output_text", "annotations": []}),
        "response.reasoning_summary_text.delta": ({"type": "reasoning"}, "summary", {"type": "summary_text"})}


class Refused(Exception):
    """A request that cannot run. The message says what was wrong with it."""

    def __init__(self, message, status=400, param=None):
        super().__init__(message)
        self.status, self.param = status, param


def sandbox(program, folders, variables):
    """Run one of a package's programs in a container that sees only these folders, each at /<its name>."""
    read_only = {"turn"} | ({"harness"} if program == "run" else set())
    env = {"HOME": "/mind" if "mind" in folders else "/tmp", "npm_config_cache": "/tmp/npm",  # noqa: S108
           **{f"HG_{name.upper()}": f"/{name}" for name in folders}, **variables}
    command = [*SANDBOX, f"--workdir=/{'work' if program == 'run' else 'harness'}",
               *(f"--volume={path}:/{name}{':ro' if name in read_only else ''}" for name, path in folders.items()),
               *(f"--env={name}" for name in env), IMAGE, f"/harness/{program}"]     # values go by the environment,
    return subprocess.run(command, env={**os.environ, **env}, stdout=subprocess.PIPE,  # noqa: S603  not the command
                          stderr=None if program == "run" else subprocess.STDOUT, text=True, errors="replace")


def installed(harness):
    """The package, installed for this image: a copy of its folder that its `install` has run in, once."""
    folder = DATA / "installs" / f"{harness}-{re.sub(r'[^a-z0-9]', '_', IMAGE)}"
    if not (folder / ".installed").exists():
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(PACKAGES / harness, folder)
        subprocess.run(["chmod", "-R", "a+rwX", str(folder)], check=True)   # noqa: S603, S607  the sandbox's user writes here
        ran = sandbox("install", {"harness": folder}, {})
        if ran.returncode != 0:
            raise Refused(f"install failed:\n{ran.stdout[-2000:]}", status=500)
        (folder / ".installed").touch()
    return folder


def gather(lines):
    """What a run printed, as the items of the response's output and the line it ended with. A whole item is
    given an id; pieces of text are gathered into the message, or the reasoning, they belong to; an item that
    was printed as it began and again as it ended is taken as it ended."""
    items, ending, flowing = [], None, None
    for text in lines:
        line = json.loads(text) if text.strip() else {"type": ""}
        kind = line["type"]
        if kind in ENDINGS:
            return items, line                         # whatever follows the last event is ignored
        if kind in TEXT:
            shape, field, part = TEXT[kind]
            if flowing != kind:
                items.append({"id": f"item_{uuid.uuid4().hex}", **shape, field: [{**part, "text": ""}]})
            items[-1][field][0]["text"] += line["delta"]
        elif kind == "response.output_item.done":
            items.append(line["item"])
        elif kind and not kind.startswith("response."):
            items.append({"id": f"item_{uuid.uuid4().hex}", **line})
        flowing = kind
    return items, ending


def respond(body):
    """One request, start to end: its turn, run in a sandbox, as an OpenAI response object."""
    if not isinstance(body, dict) or not isinstance(body.get("model"), str) or body.get("input") is None:
        raise Refused("a request is a JSON object with model and input")
    harness, _, rest = body["model"].partition("/")
    provider, _, model = rest.partition("/")
    if not re.fullmatch(r"[a-z0-9-]+", harness) or not (PACKAGES / harness / "run").is_file():
        raise Refused(f"there is no harness named {harness!r}: model is harness/provider/model", param="model")
    if not model or (provider != "none" and provider not in PROVIDERS):
        raise Refused(f"there is no provider named {provider!r}: model is harness/provider/model", param="model")
    previous, named = None, str(body.get("previous_response_id"))
    if body.get("previous_response_id") is not None:
        if not re.fullmatch(r"resp_[0-9a-f]{32}", named) or not (DATA / "turns" / named / "response.json").is_file():
            raise Refused("previous_response_id names no response", param="previous_response_id")
        previous = json.loads((DATA / "turns" / named / "response.json").read_text())
    session = previous["metadata"]["hg_session"] if previous else f"sess_{uuid.uuid4().hex}"
    turn, created = f"resp_{uuid.uuid4().hex}", int(time.time())
    folders = {"mind": DATA / "sessions" / session / "mind", "work": DATA / "sessions" / session / "work",
               "turn": DATA / "turns" / turn}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
        folder.chmod(0o777)                            # the sandbox's user is not this one
    (folders["turn"] / "request.json").write_text(json.dumps(body))
    (folders["turn"] / "previous.json").write_text(json.dumps(previous))
    apis = PROVIDERS.get(provider, {}).get("apis", {})
    variables = {"HG_STATE": f"/mind/.harnessgateway/{harness}", "HG_HARNESS_NAME": harness, "HG_SESSION": session,
                 "HG_RESPONSE": turn, "HG_PROVIDER": provider if apis else "", "HG_MODEL": model if apis else "",
                 "HG_PROVIDER_KEY": os.environ.get(PROVIDERS.get(provider, {}).get("key_env", ""), ""),
                 **{"HG_PROVIDER_" + api.upper().replace("-", "_"): url for api, url in apis.items()}}
    ran = sandbox("run", {**folders, "harness": installed(harness)}, variables)
    output, ending = gather(ran.stdout.splitlines())
    said = (ending or {"response": {"error": {
        "message": f"the harness exited with code {ran.returncode} without reporting a result"}}}).get("response") or {}
    status, usage = ENDINGS[ending["type"]] if ending else "failed", said.get("usage")
    if usage:                                          # the two counts a harness gives, their total, and the details
        usage = {**usage, "total_tokens": usage["input_tokens"] + usage["output_tokens"],
                 "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0,
                                          **usage.get("input_tokens_details", {})},
                 "output_tokens_details": {"reasoning_tokens": 0, **usage.get("output_tokens_details", {})}}
    response = {"id": turn, "object": "response", "created_at": created, "status": status, "model": body["model"],
                "output": output, "usage": usage, "incomplete_details": said.get("incomplete_details"),
                "error": {"code": "server_error", "message": said["error"]["message"]} if status == "failed" else None,
                "metadata": {**(body.get("metadata") or {}), "hg_session": session},
                "parallel_tool_calls": body.get("parallel_tool_calls", True),
                "tool_choice": body.get("tool_choice", "auto"), "tools": body.get("tools", []),
                **{name: body[name] for name in ("instructions", "previous_response_id") if name in body}}
    (folders["turn"] / "response.json").write_text(json.dumps(response))
    return response


class Api(BaseHTTPRequestHandler):
    def do_POST(self):                                 # POST /v1/responses: answered when the turn has ended
        try:
            if self.path != "/v1/responses":
                raise Refused(f"there is nothing at {self.path}", status=404)
            if self.headers.get("Content-Type", "").partition(";")[0].strip() != "application/json":
                raise Refused("send the request as application/json")     # which another site's page cannot do unasked
            status, answer = 200, respond(json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0))))
        except (Refused, ValueError) as refusal:       # ValueError: a body, or a printed line, that is not JSON
            status = getattr(refusal, "status", 400)
            answer = {"error": {"message": str(refusal), "type": "invalid_request_error",
                                "param": getattr(refusal, "param", None), "code": None}}
        data = json.dumps(answer).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--image", default=IMAGE, help="the image every sandbox is a container of")
    parser.add_argument("--port", type=int, default=8600)
    args = parser.parse_args()
    IMAGE = args.image
    print(f"the core on http://127.0.0.1:{args.port}/v1: harnesses run in {IMAGE}, one request at a time")
    HTTPServer(("127.0.0.1", args.port), Api).serve_forever()
