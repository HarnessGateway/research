# Building Agents Using Harness CLIs

I am [Chase Dovey](https://cdovey.dev/), a builder. I build agents and harnesses. This is how I build an agent
from a model and any harness CLI, the same way every time.

## What an agent is

An agent observes, thinks, and acts, then repeats. It has two primitives:

- **Model**, the mind. It predicts the next token from the tokens before it, like an intelligent autocomplete.
- **Harness**, the body. It observes and acts, through
  [five primitives of its own](https://github.com/averagejoeslab/harness-engineering): input, context, model
  interface, output, and control flow.

My favorite build is actually a harness called [quark](https://github.com/averagejoeslab/quark). It is high
powered yet lightweight, and it provides a terminal agent experience in 81 lines.

But every harness has the same five primitives, and often one that already exists serves an agent better than
one I would write. That is what makes the work repeatable.

## The framework

A harness CLI is a harness you run from a terminal: you give it a request, and it works until it is done. Claude
Code, Codex, and OpenCode are three of many. Used that way it is a tool. This framework makes it the backend of
an agent: a program starts it, feeds it, reads it, and stops it, with nobody at the keyboard.

Seven steps, in order. You need a terminal, a key for a model provider, and a folder you can afford to lose,
because a harness run with nobody there acts without asking.

### 1. Find the latest stable version

Look it up where the harness is published: its package registry or its releases. Take the latest stable one,
not a preview, beta, or nightly. Write the exact version down. Everything you learn is true of that version.

### 2. Install it

Install that exact version into a folder, by its makers' own method, with nothing global. Run it once to print
its version, and check it is the one you chose.

### 3. Read its help

Run its help at the top level, then for every command and subcommand. Keep the output: it is the installed
version describing itself.

### 4. Read its documentation

Read it for what the help leaves out. Note every place the two disagree.

### 5. Learn how to drive its primitives

Answer one question for each. Record every answer as the exact flag, variable, or file, and where you found it:
help, docs, or test.

| Primitive | Ask | Examples |
|---|---|---|
| **Input** | How do I send it a request? | A prompt as an argument, or piped in. Messages as JSON lines, for images and files |
| **Context** | How do I get it context that makes the request useful? | Instructions. A memory file it reads unasked. Skills. A session to continue from |
| **Model interface** | How do I configure its requests to the model? | Endpoint and key. Model name. Reasoning level. Streaming and temperature, where exposed |
| **Output** | How do I handle what comes out? | The reply as text. Every step as a line of JSON. An answer that fits a schema. The tools it may use |
| **Control flow** | How do I control its loop? | Run once and exit. A limit on turns or spend. A hook that can refuse an action. A signal that stops it |

### 6. Test it

Run the harness on what you learned. Use each answer the way a program would, and watch how it behaves. Then
test the edge cases: what it does when something is missing, wrong, refused, or stopped.

The goal is to judge it as the backend of an agent in production: persistence, safety and security,
observability, resilience, performance, and evaluation. The help and the documentation are both incomplete, so
only what you have run is known.

### 7. Author the program

Write the program that drives it. It reads one request, runs the harness with nobody there, and prints what
happened. The request and the events are the same whatever the harness is, which is what lets one program stand
in for another later.

**The request** is one JSON object, on standard input:

| Field | Is |
|---|---|
| `message` | What the person said |
| `session` | The harness's own id for the conversation, from an earlier turn. Left out, a new one begins |

**The events** are one JSON object a line, on standard output:

| Event | Is |
|---|---|
| `{"type": "session", "id": "…"}` | The harness's own id for this conversation. Give it back to carry on |
| `{"type": "step", "text": "…"}` | Something it did: a command, a file it changed |
| `{"type": "text", "text": "…"}` | Something it said |
| `{"type": "error", "text": "…"}` | Why it failed |

A program has three parts. Five functions build the harness's command from the request, one for each
primitive. `handle` turns each line the harness prints into events. Those six are different for every harness:

```python
def as_input(message): ...         # input: the message, in the form the harness takes it
def context(session): ...          # context: what it should know, and the conversation to carry on from
def model_interface(): ...         # model interface: endpoint, model, and reasoning
def output(): ...                  # output: what it may act with, and every step as a line the program reads
def control_flow(): ...            # control flow: run once with nobody there, bounded, and exit
def handle(line): ...              # one line the harness printed, as the events above
```

The third part is the same for every harness. It installs the harness once, runs the command, and prints the
events:

```python
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    if not (TOOLS / ".installed").exists():              # installed once, at its pinned version
        subprocess.run(["npm", "install", "--prefix", TOOLS, "--no-audit", "--no-fund", "--loglevel=error", PACKAGE],
                       check=True, stdout=sys.stderr)
        (TOOLS / ".installed").touch()
    request = json.load(sys.stdin)
    argv, env = command(request.get("session"), request["message"])
    harness = subprocess.Popen(argv, env={**os.environ, **env}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    signal.signal(signal.SIGTERM, lambda *_: harness.terminate())      # stopped from outside: it is passed on
    told = False                                         # its session id is printed once
    for printed in harness.stdout:
        try:
            events = list(handle(json.loads(printed)))
        except ValueError:
            continue                                     # not a line of JSON
        for event in events:
            if event["type"] != "session" or not told:
                print(json.dumps(event), flush=True)
            told = told or event["type"] == "session"
    sys.exit(harness.wait())
```

## Worked examples

The framework, applied to three harnesses. Each ends in the one command that runs it with nobody there, and
the program that command becomes. The provider is DeepSeek throughout, because one key serves the three APIs
these harnesses speak.

The agent is the same in all three: a general chat agent. It is one file, `AGENTS.md`, because every one of
them reads that file from its working folder unasked:

```markdown
You are a helpful assistant in a chat.

- Answer plainly and briefly. Lead with the answer.
- You have a working folder. Use it when asked to make, change, or run something, and say what you did.
- Do not say which program or model you run on. You are the assistant.
```

### Claude Code 2.1.325

Its registry marks a `stable` version, 2.1.325, that is older than its `latest`, 2.1.331. Latest is not stable.

| Primitive | How it is driven |
|---|---|
| **Input** | The prompt as an argument, or on standard input. `--input-format stream-json` for messages |
| **Context** | Reads `CLAUDE.md` from the working folder, or `AGENTS.md` when there is none. `--append-system-prompt`. Skills in `.claude/skills`. `--resume <id>` |
| **Model interface** | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `--model`, `--effort` |
| **Output** | `--output-format stream-json --verbose`. `--json-schema`. Headless it refuses to write unless allowed: `--allowedTools`, `--permission-mode`, or `--dangerously-skip-permissions` |
| **Control flow** | `-p`. `--max-turns`, `--max-budget-usd`. Hooks in its settings: one that exits 2 refuses an action. `SIGTERM` stops it, and the session is kept |

```sh
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic ANTHROPIC_AUTH_TOKEN=$DEEPSEEK_API_KEY \
  claude -p --max-turns 50 --model deepseek-flash --dangerously-skip-permissions \
  --output-format stream-json --verbose -- "Create notes.txt containing the word PELICAN."
```

Testing found: `--max-turns` is in the documentation and not in the help, and it works. A flag that takes a
list swallows the prompt after it, hence the `--`. A continued session ignores new instructions until
`--system-prompt-snapshot off`.

Its program, [agent-claude-code.py](agent-claude-code.py). The five functions put the request into its command, and
`handle` puts its output into the events. With the last block of step 7, this is the whole program:

```python
NAME, PACKAGE = "claude-code", "@anthropic-ai/claude-code@2.1.325"  # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(os.environ.get("TOOLS") or Path(__file__).resolve().parent / "agent" / "data" / "host" / "tools") / NAME


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


def command(session, message):                           # the one-liner, from its five parts
    model, env = model_interface()
    return [TOOLS / "node_modules/.bin/claude", *control_flow(), *context(session), *model, *output(),
            *as_input(message)], env


def handle(line):                                        # output: one line it printed, as the events of the request
    if line.get("subtype") == "init":
        yield {"type": "session", "id": line["session_id"]}
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
```

### Codex 0.171.0

| Primitive | How it is driven |
|---|---|
| **Input** | The prompt as an argument, or `-` to read it from standard input. `-i` attaches images |
| **Context** | Reads `AGENTS.md` from the working folder. `-c developer_instructions=…`. Skills in `.agents/skills`. `exec resume <id>` |
| **Model interface** | A provider defined with `-c model_providers.<id>={…}`, chosen with `-c model_provider=`, and `-m`. It speaks one API, OpenAI Responses |
| **Output** | `--json`. `--output-schema <file>`. Headless it runs in a read-only sandbox and refuses to write: `--sandbox workspace-write`, or `--dangerously-bypass-approvals-and-sandbox` |
| **Control flow** | `exec`. No bound on turns or spend. Hooks in `hooks.json`: one that exits 2 refuses an action. `SIGTERM` stops it, and the session is kept |

```sh
codex exec --skip-git-repo-check -c model_provider=deepseek \
  -c 'model_providers.deepseek={name="DeepSeek",base_url="https://api.deepseek.com/v1",env_key="DEEPSEEK_API_KEY",wire_api="responses"}' \
  -m deepseek-flash --dangerously-bypass-approvals-and-sandbox --json -- "Create notes.txt containing the word PELICAN."
```

Testing found: its own sandbox cannot start inside a container, so there it must be bypassed and the
container is the sandbox. Instructions given on a continued session are dropped without a word. A project's
hooks do not run until the project is trusted.

Its program, [agent-codex.py](agent-codex.py). The five functions put the request into its command, and
`handle` puts its output into the events. With the last block of step 7, this is the whole program:

```python
NAME, PACKAGE = "codex", "@openai/codex@0.171.0"         # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(os.environ.get("TOOLS") or Path(__file__).resolve().parent / "agent" / "data" / "host" / "tools") / NAME
PROVIDER = ('model_providers.deepseek={name="DeepSeek",base_url="https://api.deepseek.com/v1",'
            'env_key="DEEPSEEK_API_KEY",wire_api="responses"}')


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(session):                                    # context: AGENTS.md is read from the working folder unasked.
    return ["resume", session] if session else []        # This is the conversation so far


def model_interface():                                   # model interface: the provider is a setting, the model a
    return ["-c", "model_provider=deepseek", "-c", PROVIDER, "-m", MODEL], {}      # flag, the key a variable it names


def output():                                            # output: act without asking, and print every step as JSON
    return ["--dangerously-bypass-approvals-and-sandbox", "--json"]


def control_flow():                                      # control flow: one request, then exit. It has no bound
    return ["exec"]


def command(session, message):                           # the one-liner, from its five parts
    model, env = model_interface()
    return [TOOLS / "node_modules/.bin/codex", *control_flow(), *context(session), "--skip-git-repo-check", *model,
            *output(), *as_input(message)], env


def handle(line):                                        # output: one line it printed, as the events of the request
    item = line.get("item") or {}
    if line["type"] == "thread.started":
        yield {"type": "session", "id": line["thread_id"]}
    if line["type"] == "item.completed" and item["type"] == "agent_message":
        yield {"type": "text", "text": item["text"]}
    if line["type"] == "item.completed" and item["type"] == "command_execution":
        yield {"type": "step", "text": f"$ {item['command']}"}
    if line["type"] == "item.completed" and item["type"] == "file_change":
        yield {"type": "step", "text": "edit " + ", ".join(change["path"] for change in item["changes"])}
    if line["type"] == "turn.failed":
        yield {"type": "error", "text": line["error"]["message"]}
```

### OpenCode 1.19.6

| Primitive | How it is driven |
|---|---|
| **Input** | The prompt as an argument, on standard input, or both joined. `-f` attaches files |
| **Context** | Reads `AGENTS.md` from the working folder. `instructions` in its config. Skills in `.opencode/skills`. `--session <id>` |
| **Model interface** | `-m provider/model`: a provider it knows by name, or one defined in its config. `--variant` for reasoning |
| **Output** | `--format json`. No schema for the answer. Headless it acts inside its working folder and refuses outside it: `--auto` allows the rest, and `permission` in its config denies |
| **Control flow** | `run`. `steps` in its config bounds the loop. Plugins: one that throws before a tool runs refuses the action. `SIGTERM` stops it, and the session is kept |

```sh
opencode run -m deepseek/deepseek-flash --auto --format json -- "Create notes.txt containing the word PELICAN."
```

Testing found: it takes its working folder from `$PWD`, not from where it is started. Its documentation site
leads with a newer major version than the one that installs. A model name it does not know crashes it with
`e.split is not a function`.

Its program, [agent-opencode.py](agent-opencode.py). The five functions put the request into its command, and
`handle` puts its output into the events. With the last block of step 7, this is the whole program:

```python
NAME, PACKAGE = "opencode", "opencode-ai@1.19.6"         # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(os.environ.get("TOOLS") or Path(__file__).resolve().parent / "agent" / "data" / "host" / "tools") / NAME


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(session):                                    # context: AGENTS.md is read from the working folder unasked.
    return ["--session", session] if session else []     # This is the conversation so far


def model_interface():                                   # model interface: a provider it knows by name, with the
    return ["-m", f"deepseek/{MODEL}"], {}               # model. It finds the key in the environment itself


def output():                                            # output: act without asking, and print every step as JSON
    return ["--auto", "--format", "json"]


def control_flow():                                      # control flow: one request, then exit. A bound is a setting
    return ["run"]


def command(session, message):                           # the one-liner, from its five parts. PWD, because that is
    model, env = model_interface()                       # where it takes its working folder from
    return [TOOLS / "node_modules/.bin/opencode", *control_flow(), *context(session), *model, *output(),
            *as_input(message)], {**env, "PWD": os.getcwd()}


def handle(line):                                        # output: one line it printed, as the events of the request
    part = line.get("part") or {}
    if line.get("sessionID"):
        yield {"type": "session", "id": line["sessionID"]}
    if line["type"] == "text":
        yield {"type": "text", "text": part["text"]}
    if line["type"] == "tool_use":
        given = part["state"].get("input") or {}
        yield {"type": "step", "text": f"$ {given['command']}" if "command" in given
               else f"{part['tool']} {given.get('filePath', '')}"}
    if line["type"] == "error":
        yield {"type": "error", "text": line["error"].get("data", {}).get("message") or line["error"].get("name")}
```

## One agent, any harness

Each of the three programs runs by itself, and from outside they cannot be told apart:

```sh
echo '{"message": "Create notes.txt containing the word PELICAN."}' | python3 agent-codex.py
```

```json
{"type": "session", "id": "01a20b24-…"}
{"type": "step", "text": "edit /…/notes.txt"}
{"type": "text", "text": "Created `notes.txt` containing `PELICAN`."}
```

Put `agent-claude-code.py` or `agent-opencode.py` in that command, and the request and the events are the same.

### One schema

That sameness is the unified JSON. One request goes in and four kinds of event come out, and each harness meets
them in its own way. The five functions do the first two rows, and `handle` does the rest:

| | Claude Code | Codex | OpenCode |
|---|---|---|---|
| `message`, in | The prompt argument | The prompt argument | The prompt argument |
| `session`, in | `--resume <id>` | `exec resume <id>` | `--session <id>` |
| `session`, out | `session_id` on its first line | `thread_id` on its `thread.started` line | `sessionID` on every line |
| `text`, out | A `text` block of an `assistant` line | An `agent_message` item | A `text` line |
| `step`, out | A `tool_use` block of an `assistant` line | A `command_execution` or `file_change` item | A `tool_use` line |
| `error`, out | A `result` line with `is_error` | A `turn.failed` line | An `error` line |

### The agent

An agent that can change its harness needs one more field in the request, and nothing else:

```json
{"harness": "codex", "session": "…", "message": "…"}
```

Here `session` is the agent's: one conversation, whatever harnesses answer in it. The events are the same four,
with `done` at the end.

For the change to go unseen, that session cannot belong to a harness. It is three things the agent keeps:

| | |
|---|---|
| **Mind** | The home folder. Each harness keeps its own memory there, side by side, and is carried on by its own id |
| **Work** | The working folder. Every harness shares it |
| **What was said** | Kept by the agent. A harness that was not the one answering is given the turns it missed, with the next message |

[agent.py](agent.py) is that agent, whole. It has a chat console, and for each message it starts the program
the request names. A fourth harness is a fourth file:

```python
#!/usr/bin/env python3
"""agent.py: a chat agent that can change the harness behind it. One console, a harness to pick for each message.

    python3 agent.py                    # on this machine
    python3 agent.py --sandbox          # every turn in a container that is thrown away

A turn is one request: {"harness": "codex", "session": "…", "message": "…"}. The harness names a program beside
this file, agent-<harness>.py, and every such program takes the same request and prints the same events. So the
agent starts whichever one is named, and keeps what must outlive any of them: the session.

What the agent needs is in the folder agent/: who it is, its page, and what it keeps. Standard library only.
"""
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {path.stem.removeprefix("agent-"): path for path in sorted(HERE.glob("agent-*.py"))}    # harness: program
SANDBOX = "--sandbox" in sys.argv
DATA = HERE / "agent" / "data" / ("sandbox" if SANDBOX else "host")
KEY = "DEEPSEEK_API_KEY"                                 # the provider's key: all of this machine a sandbox is given
BOX = ["docker", "run", "--rm", "-i", "--init", "--cpus=2", "--memory=4g", "--pids-limit=512", "--read-only",
       "--tmpfs=/tmp:rw,exec,size=1g", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10000:10000"]
running = {}                                             # by session: the program, while a turn is in progress


def start(program, mind, work, log):
    """Start a harness program on a session's two folders. Here, that is this machine. With --sandbox it is a
    container that sees the program, those folders, and the harnesses installed for it, and nothing else."""
    pipes = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": log}
    if not SANDBOX:
        return subprocess.Popen([sys.executable, program], cwd=work,
                                env={**os.environ, "HOME": str(mind), "TOOLS": str(DATA / "tools")}, **pipes)
    seen = {program: f"/{program.name}:ro", work: "/work", mind: "/mind", DATA / "tools": "/tools"}
    return subprocess.Popen([*BOX, *(f"--volume={path}:{where}" for path, where in seen.items()), "--workdir=/work",
                             "--env=HOME=/mind", "--env=TOOLS=/tools", "--env=npm_config_cache=/tmp/npm",
                             f"--env={KEY}", "node:22", "python3", f"/{program.name}"], **pipes)


def turn(harness, session, message):
    """One turn of a session on one harness, as the events the page shows. A session belongs to no harness: it is
    a mind (the home folder, where each harness keeps its own memory), a work folder they share, and what was
    said. A harness that was not the one answering is told what it missed, so the person never sees the change."""
    folder = DATA / "sessions" / session
    mind, work, record = folder / "mind", folder / "work", folder / "session.json"
    if not folder.exists():
        for each in (mind, work, DATA / "tools"):
            each.mkdir(parents=True, exist_ok=True)
            each.chmod(0o777)                            # the sandbox's user is not this one
        shutil.copy(HERE / "agent" / "AGENTS.md", work)  # who the agent is: every harness reads it unasked
    kept = json.loads(record.read_text()) if record.exists() else {"title": message[:60], "turns": [], "ids": {}}
    mine = kept["ids"].setdefault(harness, {"id": None, "seen": 0})
    missed = "".join(f"{each['role']}: {each['text']}\n\n" for each in kept["turns"][mine["seen"]:])
    asked = message if not missed else ("Here is what was said in this conversation since you last replied. Carry on "
                                        f"from it as the assistant.\n\n{missed}user: {message}")
    said, steps = [], []
    with open(folder / "log.txt", "ab") as log:
        program = running[session] = start(PROGRAMS[harness], mind, work, log)
        program.stdin.write(json.dumps({"message": asked, "session": mine["id"]}).encode())
        program.stdin.close()
        for event in map(json.loads, program.stdout):
            if event["type"] == "session":
                mine["id"] = event["id"]                 # the harness's own id for it: how it is continued
                continue
            (said if event["type"] == "text" else steps).append(event["text"])
            yield event
        ok = program.wait() == 0
    del running[session]
    kept["turns"] += [{"role": "user", "text": message},
                      {"role": "assistant", "text": "\n\n".join(said), "steps": steps, "harness": harness}]
    mine["seen"] = len(kept["turns"])
    record.write_text(json.dumps(kept))
    yield {"type": "done", "ok": ok}


class Console(BaseHTTPRequestHandler):
    def do_GET(self):
        record = DATA / "sessions" / self.path.rpartition("/")[2] / "session.json"
        if self.path == "/":
            self.reply("text/html; charset=utf-8", (HERE / "agent" / "console.html").read_bytes())
        elif self.path == "/sessions":
            records = sorted((DATA / "sessions").glob("*/session.json"), key=os.path.getmtime, reverse=True)
            self.reply("application/json", json.dumps({"harnesses": list(PROGRAMS), "sessions": [
                {"id": each.parent.name, "title": json.loads(each.read_text())["title"]}
                for each in records]}).encode())
        elif re.fullmatch(r"/sessions/[0-9a-f]{32}", self.path) and record.exists():
            self.reply("application/json", record.read_bytes())
        else:
            self.send_error(404)

    def do_POST(self):                                   # taken only as application/json, which another site's page
        if self.headers.get("Content-Type") != "application/json":             # cannot send unasked
            return self.send_error(400, "send application/json")
        asked = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        session = asked.get("session") or uuid.uuid4().hex
        if not re.fullmatch(r"[0-9a-f]{32}", session):
            return self.send_error(400, "that is not a session")
        if self.path == "/stop":                         # stopped from outside: the session is kept
            if session in running:
                running[session].send_signal(signal.SIGTERM)
            return self.reply("application/json", b"{}")
        if asked.get("harness") not in PROGRAMS or not asked.get("message"):
            return self.send_error(400, "a turn is a harness, a session, and a message")
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        events, here = turn(asked["harness"], session, asked["message"]), True
        for event in itertools.chain([{"type": "session", "id": session}], events):
            try:
                if here:
                    self.wfile.write(json.dumps(event).encode() + b"\n")
                    self.wfile.flush()
            except BrokenPipeError:                      # the page went away: the turn is stopped, and still kept
                here = False
                running[session].send_signal(signal.SIGTERM)

    def reply(self, kind, data):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    (DATA / "sessions").mkdir(parents=True, exist_ok=True)
    where = "in a sandbox" if SANDBOX else "on this machine"
    print(f"the console is on http://127.0.0.1:8500/: {', '.join(PROGRAMS)}, {where}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8500), Console).serve_forever()
```

What the agent needs is in one folder, [agent/](agent): who it is, the `AGENTS.md` above, and its page,
`console.html`, which sends the request and draws the events:

<details>
<summary>agent/console.html</summary>

```html
<!doctype html>
<!-- The chat console: one page. It sends a turn (a harness, a session, a message) and draws the events that come back. -->
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent</title>
<style>
  :root { --bg: #fff; --side: #f9f9f9; --ink: #0d0d0d; --muted: #6b6b6b; --line: #e5e5e5; --bubble: #f4f4f4; --bad: #c0362c; color-scheme: light dark; }
  @media (prefers-color-scheme: dark) { :root { --bg: #212121; --side: #171717; --ink: #ececec; --muted: #a0a0a0; --line: #303030; --bubble: #2f2f2f; --bad: #ff8d83; } }
  * { box-sizing: border-box; }
  body { margin: 0; height: 100vh; display: flex; background: var(--bg); color: var(--ink); font: 15px/1.6 system-ui, sans-serif; }
  aside { width: 260px; background: var(--side); padding: 12px; overflow: auto; flex-shrink: 0; }
  aside button, aside a { display: block; width: 100%; padding: 8px 10px; border: 0; border-radius: 8px; background: none; color: inherit; font: inherit; text-align: left; text-decoration: none; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  aside button:hover, aside a:hover, aside a.open { background: var(--line); } aside button { font-weight: 600; margin-bottom: 8px; }
  main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  #thread { flex: 1; overflow: auto; padding: 24px 16px; } #thread > * { max-width: 760px; margin: 0 auto 18px; }
  .user { background: var(--bubble); padding: 10px 16px; border-radius: 18px; width: fit-content; max-width: 560px; margin-right: max(0px, calc((100% - 760px) / 2)) !important; margin-left: auto !important; white-space: pre-wrap; }
  .text { white-space: pre-wrap; word-break: break-word; } .bad { color: var(--bad); } .hello { color: var(--muted); text-align: center; margin-top: 30vh !important; font-size: 22px; }
  details { color: var(--muted); font-size: 13px; margin-bottom: 6px; } summary { cursor: pointer; } details div { font: 12px/1.6 ui-monospace, monospace; word-break: break-all; padding-left: 14px; }
  form { max-width: 760px; width: calc(100% - 32px); margin: 0 auto 20px; border: 1px solid var(--line); border-radius: 24px; padding: 10px 12px; display: flex; gap: 8px; align-items: flex-end; box-shadow: 0 2px 8px rgba(0, 0, 0, .06); }
  textarea { flex: 1; border: 0; outline: 0; resize: none; background: none; color: inherit; font: inherit; height: 28px; max-height: 200px; padding: 2px 6px; }
  select, form button { font: inherit; color: inherit; background: var(--bubble); border: 0; border-radius: 16px; padding: 6px 12px; cursor: pointer; }
  form button { background: var(--ink); color: var(--bg); font-weight: 600; }
</style>
<aside><button id="new">New chat</button><div id="sessions"></div></aside>
<main>
  <div id="thread"></div>
  <form id="form">
    <textarea id="message" placeholder="Ask anything" autofocus></textarea>
    <select id="harness" title="The harness behind the agent"></select>
    <button id="send">Send</button>
  </form>
</main>
<script>
"use strict";
const $ = id => document.getElementById(id);
// Every node is made here, and what the agent said is only ever text: none of it becomes markup.
const el = (tag, cls, text) => { const node = document.createElement(tag); node.className = cls || ""; node.textContent = text || ""; return node; };
const post = (path, body) => fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
let session = null, busy = false;                     // the session on screen, and whether a turn is in progress

function reply() {                                    // an empty reply, and how to add to it
  const steps = el("details"), summary = el("summary"), box = el("div");
  steps.append(summary); steps.hidden = true; box.append(steps); $("thread").append(box);
  return {
    step(text) { steps.hidden = false; steps.append(el("div", "", text)); const count = steps.children.length - 1; summary.textContent = `Worked: ${count} step${count > 1 ? "s" : ""}`; },
    text(text, cls) { box.append(el("div", cls || "text", text)); box.scrollIntoView({ block: "end" }); },
  };
}

async function list() {                               // the sessions, and the harnesses to pick from
  const all = await (await fetch("/sessions")).json();
  if (!$("harness").options.length) $("harness").append(...all.harnesses.map(name => el("option", "", name)));
  $("sessions").replaceChildren(...all.sessions.map(each => {
    const link = el("a", each.id === session ? "open" : "", each.title);
    link.onclick = () => show(each.id);
    return link;
  }));
}

async function show(id) {                             // a session, as it was kept
  session = id;
  $("thread").replaceChildren();
  if (!id) $("thread").append(el("div", "hello", "What can I help with?"));
  for (const turn of id ? (await (await fetch(`/sessions/${id}`)).json()).turns : []) {
    if (turn.role === "user") { $("thread").append(el("div", "user", turn.text)); continue; }
    const drawn = reply();
    turn.steps.forEach(drawn.step);
    drawn.text(turn.text);
  }
  list();
  $("message").focus();
}

$("form").onsubmit = async event => {
  event.preventDefault();
  if (busy) return post("/stop", { session });        // while a turn runs, the button stops it
  const message = $("message").value.trim();
  if (!message) return;
  if (!session) $("thread").replaceChildren();
  $("thread").append(el("div", "user", message));
  $("message").value = ""; busy = true; $("send").textContent = "Stop";
  const drawn = reply(), decoder = new TextDecoder();
  const reader = (await post("/turn", { harness: $("harness").value, session, message })).body.getReader();
  for (let buffer = "";;) {                           // each event is drawn as it arrives
    const { done, value } = await reader.read();
    if (done) break;
    const lines = (buffer + decoder.decode(value, { stream: true })).split("\n");
    buffer = lines.pop();
    for (const each of lines.filter(Boolean).map(JSON.parse)) {
      if (each.type === "session") session = each.id;
      if (each.type === "step") drawn.step(each.text);
      if (each.type === "text") drawn.text(each.text);
      if (each.type === "error") drawn.text(each.text, "text bad");
      if (each.type === "done" && !each.ok) drawn.text("The turn did not finish.", "text bad");
    }
  }
  busy = false; $("send").textContent = "Send";
  list();
  $("message").focus();
};
$("message").onkeydown = event => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("form").requestSubmit(); } };
$("new").onclick = () => show(null);
show(null);
</script>
</html>
```

</details>

```sh
python3 agent.py          # then open http://127.0.0.1:8500/
```

I told Claude Code my name and had it write a file. Codex, asked next, knew my name and added a line. OpenCode
showed the file, and asked who wrote the second line, said it had. The person sees one agent, and only chooses
what is behind it.

Run this way, the agent acts without asking, as you, on your machine.

## A sandbox

The last change is to where a program is started, which is the function `start` in `agent.py`. With
`--sandbox`, each turn is the same program in a container that is thrown away:

```sh
docker run --rm -i --init --cpus=2 --memory=4g --pids-limit=512 --read-only --tmpfs=/tmp:rw,exec,size=1g \
  --cap-drop=ALL --security-opt=no-new-privileges --user=10000:10000 \
  --volume=agent-codex.py:/agent-codex.py:ro --volume=<session>/work:/work --volume=<session>/mind:/mind \
  --volume=<tools>:/tools --workdir=/work --env=HOME=/mind --env=DEEPSEEK_API_KEY node:22 python3 /agent-codex.py
```

It is not root, it cannot change the image it runs in, it is capped, and it sees the program, the session's two
folders, and the harnesses installed for it. Of this machine's environment it is given one thing, the
provider's key. Nothing else changed: not the request, not the three programs, not the page.

```sh
python3 agent.py --sandbox
```

In a browser, in one conversation: Claude Code wrote a haiku into a file, Codex recalled my name and added a
second, and OpenCode showed the file and counted two. I stopped Claude Code in the middle of a command, and
Codex, asked next, knew what had been going on.

## Where this goes

A chat console, any harness behind the agent, and every turn sandboxed. Each piece has a name on the platform I
built from it, [HarnessGateway](https://github.com/HarnessGateway/harnessgateway):

| Here | There |
|---|---|
| `agent-<harness>.py` | A harness package: two programs, `install` and `run` |
| `agent.py` | The core: it takes the request, starts the package in a sandbox, and keeps the session |
| The request and the events | The OpenAI Responses API, unmodified |
| `harness` | `model`, written as `harness/provider/model` |
| The agent's `session` | `previous_response_id` |

The JSON here is mine, and small: a step is a line of text, and nothing but this page speaks it. Writing it, I
was inventing a request, an output format, and a way to name a session. OpenAI Responses already has all three,
with an item for everything an agent does, and every client speaks it. That is the one step from this
repository to the platform.

The questions never change. Only the implementations do.
