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

The goal is to judge it as the backend of an agent in production. The help and the documentation are both
incomplete, so only what you have run is known.

### 7. Author the program

Write the program that drives it. I like to call it a harness package: its goal is to install and run a
harness CLI. JSON in, code, JSON out: it reads one request, runs the harness with nobody there, and prints what
the harness printed, one JSON object a line.

```json
{"message": "…", "thread": "…"}
```

`message` is what the person said. `thread` is the harness's own id for a conversation, from an earlier turn:
with it, the harness carries on from there.

Inside, it is five functions, one for each primitive. Together they turn the request into the harness's
command:

```python
def as_input(message): ...         # input: the message, in the form the harness takes it
def context(thread): ...           # context: what it should know, and the conversation to carry on from
def model_interface(): ...         # model interface: endpoint, model, and reasoning
def output(): ...                  # output: what it may act with, and every step as a line of JSON
def control_flow(): ...            # control flow: run once with nobody there, bounded, and exit
```

## Worked examples

The framework, applied to three harnesses. Each ends in the one command that runs it with nobody there, and
the program that command becomes: its JSON in, its code, and its JSON out. The provider is DeepSeek throughout,
because one key serves the three APIs these harnesses speak.

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
list swallows the prompt after it, hence the `--`.

Its program, [agent-claude-code.py](agent-claude-code.py), makes that command of a request.

**JSON in**

```json
{"message": "Create notes.txt containing the word PELICAN."}
```

**Code**

```python
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
```

**JSON out**, as Claude Code prints it, shortened

```
{"type":"system","subtype":"init","session_id":"38921473-…","tools":[…]}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"/…/notes.txt","content":"PELICAN\n"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","content":"File created successfully at: /…/notes.txt"}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"Created `/…/notes.txt` containing `PELICAN`."}]}}
{"type":"result","subtype":"success","is_error":false,"usage":{…}}
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
container is the sandbox. A project's hooks do not run until the project is trusted.

Its program, [agent-codex.py](agent-codex.py), makes that command of a request.

**JSON in**

```json
{"message": "Create notes.txt containing the word PELICAN."}
```

**Code**

```python
NAME, PACKAGE = "codex", "@openai/codex@0.171.0"         # its latest stable version, pinned
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
```

**JSON out**, as Codex prints it, shortened

```
{"type":"thread.started","thread_id":"01a20b4f-…"}
{"type":"item.completed","item":{"type":"command_execution","command":"/usr/bin/bash -lc \"printf 'PELICAN\\n' > notes.txt && cat notes.txt\"","exit_code":0}}
{"type":"item.completed","item":{"type":"agent_message","text":"Created `notes.txt` containing `PELICAN`."}}
{"type":"turn.completed","usage":{…}}
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

Its program, [agent-opencode.py](agent-opencode.py), makes that command of a request.

**JSON in**

```json
{"message": "Create notes.txt containing the word PELICAN."}
```

**Code**

```python
NAME, PACKAGE = "opencode", "opencode-ai@1.19.6"         # its latest stable version, pinned
MODEL = "deepseek-flash"
TOOLS = Path(__file__).resolve().parent / "agent/data/tools" / f"{NAME}-{sys.platform}"


def as_input(message):                                   # input: the message, as the prompt argument
    return ["--", message]


def context(thread):                                     # context: AGENTS.md is read from the working folder unasked.
    return ["--session", thread] if thread else []       # This is the conversation so far


def model_interface():                                   # model interface: a provider it knows by name, with the
    return ["-m", f"deepseek/{MODEL}"], {}               # model. It finds the key in the environment itself


def output():                                            # output: act without asking, and print every step as JSON
    return ["--auto", "--format", "json"]


def control_flow():                                      # control flow: one request, then exit. A bound is a setting
    return ["run"]


def command(thread, message):                            # the one-liner, from its five parts. PWD, because that is
    model, env = model_interface()                       # where it takes its working folder from
    return [TOOLS / "node_modules/.bin/opencode", *control_flow(), *context(thread), *model, *output(),
            *as_input(message)], {**env, "PWD": os.getcwd()}
```

**JSON out**, as OpenCode prints it, shortened

```
{"type":"step_start","sessionID":"ses_df4b03de…","part":{…}}
{"type":"tool_use","sessionID":"ses_df4b03de…","part":{"tool":"write","state":{"input":{"filePath":"/…/notes.txt","content":"PELICAN\n"}}}}
{"type":"text","sessionID":"ses_df4b03de…","part":{"text":"Done."}}
```

## One agent, any harness

The three programs take the same JSON in, because I wrote it. Their JSON out is three different things: look
at the three above. Nothing put in front of them could read all three. For one agent to use any of them, the
programs have to print the same thing.

### One schema

Four events are enough to say what a harness did, one JSON object a line:

```json
{"type": "thread", "id": "…"}
{"type": "text", "text": "…"}
{"type": "step", "text": "…"}
{"type": "error", "text": "…"}
```

Each harness already says all four, in its own words. With the request, that is the whole schema, and this is
how each harness meets it:

| | Is | Claude Code | Codex | OpenCode |
|---|---|---|---|---|
| `message`, in | What the person said | The prompt argument | The prompt argument | The prompt argument |
| `thread`, in | Where to carry on from | `--resume <id>` | `exec resume <id>` | `--session <id>` |
| `thread`, out | The harness's own id for the conversation | `session_id` on its first line | `thread_id` on its `thread.started` line | `sessionID` on every line |
| `text`, out | Something it said | A `text` block of an `assistant` line | An `agent_message` item | A `text` line |
| `step`, out | Something it did | A `tool_use` block of an `assistant` line | A `command_execution` or `file_change` item | A `tool_use` line |
| `error`, out | Why it failed | A `result` line with `is_error` | A `turn.failed` line | An `error` line |

The five functions already do the two rows going in. The rows coming out are a sixth function for each
program, `handle`: one line its harness printed, as events.

Claude Code's:

```python
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
```

Codex's:

```python
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
```

OpenCode's:

```python
def handle(line):                                        # output: one line it printed, as events
    part = line.get("part") or {}
    if line["type"] == "step_start":                     # its id is on every line: once a step is enough
        yield {"type": "thread", "id": line["sessionID"]}
    if line["type"] == "text":
        yield {"type": "text", "text": part["text"]}
    if line["type"] == "tool_use":
        given = part["state"].get("input") or {}
        yield {"type": "step", "text": given.get("command") or given.get("filePath") or part["tool"]}
    if line["type"] == "error":
        yield {"type": "error", "text": line["error"].get("data", {}).get("message") or line["error"].get("name")}
```

And every program ends with the same block. It installs the harness once, runs the command, and prints what
`handle` makes of each line:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

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
```

Now each program runs by itself, and from outside the three cannot be told apart:

```sh
echo '{"message": "Create notes.txt containing the word PELICAN."}' | python3 agent-codex.py
```

```json
{"type": "thread", "id": "01a20b3c-…"}
{"type": "step", "text": "/usr/bin/bash -lc \"printf 'PELICAN\\\\n' > notes.txt && cat notes.txt\""}
{"type": "text", "text": "Created `notes.txt` containing `PELICAN`."}
```

### The agent

An agent that can change its harness needs one more field, and a session of its own.

**JSON in**

```json
{"harness": "codex", "session": "…", "message": "Create notes.txt containing the word PELICAN."}
```

A thread belongs to one harness. A session belongs to none, so that the harness can change unseen. It is three
things the agent keeps:

| | |
|---|---|
| **Mind** | The home folder. Each harness keeps its own memory there, side by side, and is carried on by its own thread |
| **Work** | The working folder. Every harness shares it |
| **What was said** | Kept by the agent. A harness that was not the one answering is given the turns it missed, with the next message |

**Code**

[agent.py](agent.py), whole. For each message it runs the program the request names. A fourth harness is a
fourth file.

```python
#!/usr/bin/env python3
"""agent.py: a chat agent that can change the harness behind it. One page, a harness to pick for each message.

    python3 agent.py                    # on this machine
    python3 agent.py --sandbox          # every turn in a container that is thrown away

A turn is one request: {"harness": "codex", "session": "…", "message": "…"}. The harness names a program beside
this file, agent-<harness>.py. The agent runs it, and keeps what must outlive any harness: the session.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAMS = {path.stem.removeprefix("agent-"): path for path in sorted(HERE.glob("agent-*.py"))}    # harness: program
DATA = HERE / "agent" / "data"
BOX = ["docker", "run", "--rm", "-i", "--init", "--cpus=2", "--memory=4g", "--pids-limit=512", "--read-only",
       "--tmpfs=/tmp:rw,exec,size=1g", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=10000:10000"]


def run(program, mind, work, request):
    """Run a harness program on a session's two folders, and give back the events it printed. Here, that is
    this machine. With --sandbox it is a container that sees the program, its tools, and those two folders."""
    command, env, cwd = [sys.executable, program], {**os.environ, "HOME": str(mind)}, work
    if "--sandbox" in sys.argv:
        seen = {program: f"/app/{program.name}:ro", DATA / "tools": "/app/agent/data/tools", work: "/work",
                mind: "/mind"}
        command = [*BOX, *(f"--volume={path}:{where}" for path, where in seen.items()), "--workdir=/work",
                   "--env=HOME=/mind", "--env=npm_config_cache=/tmp/npm", "--env=DEEPSEEK_API_KEY", "node:22",
                   "python3", f"/app/{program.name}"]
        env, cwd = os.environ, None
    printed = subprocess.run(command, cwd=cwd, env=env, input=json.dumps(request), stdout=subprocess.PIPE, text=True)
    return [json.loads(line) for line in printed.stdout.splitlines()]


def turn(harness, session, message):
    """One turn of a session on one harness. A session belongs to no harness: it is a mind (the home folder,
    where each harness keeps its own memory), a work folder they share, and what was said. A harness that was
    not the one answering is told what it missed, so the person never sees the change."""
    folder = DATA / "sessions" / session
    mind, work, record = folder / "mind", folder / "work", folder / "session.json"
    if not folder.exists():
        for each in (mind, work, DATA / "tools"):
            each.mkdir(parents=True, exist_ok=True)
            each.chmod(0o777)                            # the sandbox's user is not this one
        shutil.copy(HERE / "agent" / "AGENTS.md", work)  # who the agent is: every harness reads it unasked
    kept = json.loads(record.read_text()) if record.exists() else {"turns": [], "threads": {}}
    mine = kept["threads"].setdefault(harness, {"id": None, "seen": 0})
    missed = "".join(f"{each['role']}: {each['text']}\n\n" for each in kept["turns"][mine["seen"]:])
    asked = message if not missed else ("Here is what was said in this conversation since you last replied. Carry on "
                                        f"from it as the assistant.\n\n{missed}user: {message}")
    events = run(PROGRAMS[harness], mind, work, {"message": asked, "thread": mine["id"]})
    mine["id"] = next((event["id"] for event in events if event["type"] == "thread"), mine["id"])
    events = [event for event in events if event["type"] != "thread"]        # the thread is the harness's, kept here
    said = "\n\n".join(event["text"] for event in events if event["type"] == "text")
    kept["turns"] += [{"role": "user", "text": message}, {"role": "assistant", "text": said}]
    mine["seen"] = len(kept["turns"])
    record.write_text(json.dumps(kept))
    return events


class Console(BaseHTTPRequestHandler):
    def do_GET(self):
        options = "".join(f"<option>{name}" for name in PROGRAMS)
        self.reply("text/html; charset=utf-8",
                   (HERE / "agent" / "console.html").read_text().replace("<!--harnesses-->", options))

    def do_POST(self):                                   # taken only as application/json, which another site's page
        if self.headers.get("Content-Type") != "application/json":             # cannot send unasked
            return self.send_error(400, "send application/json")
        asked = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if (asked.get("harness") not in PROGRAMS or not asked.get("message")
                or not re.fullmatch(r"[0-9a-f]{32}", str(asked.get("session")))):
            return self.send_error(400, "a turn is a harness, a session, and a message")
        events = turn(asked["harness"], asked["session"], asked["message"])
        self.reply("application/x-ndjson", "".join(json.dumps(event) + "\n" for event in events))

    def reply(self, kind, text):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(text.encode())))
        self.end_headers()
        self.wfile.write(text.encode())


if __name__ == "__main__":
    print(f"the agent is on http://127.0.0.1:8500/, with {', '.join(PROGRAMS)} behind it", flush=True)
    HTTPServer(("127.0.0.1", 8500), Console).serve_forever()
```

**JSON out**

```json
{"type": "step", "text": "/usr/bin/bash -lc \"printf 'PELICAN\\\\n' > notes.txt && cat notes.txt\""}
{"type": "text", "text": "Created `/work/notes.txt` containing `PELICAN`."}
```

The same events as any program's, without the thread: that is the harness's, and the agent keeps it.

Its page, [agent/console.html](agent/console.html), sends the request and prints the events:

```html
<!doctype html>
<meta charset="utf-8">
<title>Agent</title>
<pre id="log"></pre>
<form id="form"><select id="harness"><!--harnesses--></select> <input id="message" size="80" autofocus> <button>Send</button></form>
<script>
const $ = id => document.getElementById(id);
const session = crypto.randomUUID().replaceAll("-", "");        // one conversation. Reload the page for a new one
$("form").onsubmit = async event => {
  event.preventDefault();
  const turn = {harness: $("harness").value, session, message: $("message").value};
  $("log").append(`> ${turn.message}\n`);                       // as text: nothing the agent says becomes markup
  $("message").value = "";
  const reply = await fetch("/", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(turn)});
  for (const line of (await reply.text()).trim().split("\n")) {
    const event = JSON.parse(line);
    $("log").append(event.type === "step" ? `  - ${event.text}\n` : `${event.text}\n`);
  }
};
</script>
```

```sh
python3 agent.py          # then open http://127.0.0.1:8500/
```

I told Claude Code my name and had it write a file. Codex, asked next, knew my name and added a line. OpenCode
showed the file, and asked who wrote the second line, said it had. The person sees one agent, and only chooses
what is behind it.

Run this way, the agent acts without asking, as you, on your machine.

## A sandbox

The last change is to where a program is run, which is the function `run` in `agent.py`. With `--sandbox`, each
turn is the same program in a container that is thrown away:

```sh
docker run --rm -i --init --cpus=2 --memory=4g --pids-limit=512 --read-only --tmpfs=/tmp:rw,exec,size=1g \
  --cap-drop=ALL --security-opt=no-new-privileges --user=10000:10000 \
  --volume=agent-codex.py:/app/agent-codex.py:ro --volume=agent/data/tools:/app/agent/data/tools \
  --volume=<session>/work:/work --volume=<session>/mind:/mind --workdir=/work \
  --env=HOME=/mind --env=DEEPSEEK_API_KEY node:22 python3 /app/agent-codex.py
```

It is not root, it cannot change the image it runs in, it is capped, and it sees the program, its tools, and
the session's two folders. Of this machine's environment it is given one thing, the provider's key. Nothing
else changed: not the request, not the three programs, not the page.

```sh
python3 agent.py --sandbox
```

In a browser, in one conversation: Claude Code wrote a haiku into a file, Codex recalled my name and added a
second, and OpenCode showed the file and counted two.

## Where this goes

A chat page, any harness behind the agent, and every turn sandboxed. Each piece has a name on the platform I
built from it, [HarnessGateway](https://github.com/HarnessGateway/harnessgateway):

| Here | There |
|---|---|
| `agent-<harness>.py` | A harness package: two programs, `install` and `run` |
| `agent.py` | The core: it takes the request, runs the package in a sandbox, and keeps the session |
| The request and the events | The OpenAI Responses API, unmodified |
| `harness` | `model`, written as `harness/provider/model` |
| `session` | `previous_response_id` |
| `thread` | Kept inside the package, where the caller never sees it |

The JSON here is mine, and small: a step is a line of text, and nothing but this page speaks it. Writing it, I
was inventing a request, an output format, and a way to name a session. OpenAI Responses already has all three,
with an item for everything an agent does, and every client speaks it. That is the one step from this
repository to the platform.

The questions never change. Only the implementations do.
