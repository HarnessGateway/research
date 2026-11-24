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

Write the program that drives it. It takes one request, runs the harness with nobody there, and prints what
happened, in shapes that do not depend on the harness:

```
in     {"message": "…", "session": "…"}
out    {"type": "session", "id": "…"}       the harness's own id for the conversation: give it back to carry on
       {"type": "step", "text": "…"}        something it did
       {"type": "text", "text": "…"}        something it said
       {"type": "error", "text": "…"}       why it failed
```

Inside, it is five functions, one for each primitive, and a sixth that reads the harness's own output:

```python
def as_input(message): ...         # input: the message, in the form the harness takes it
def context(session): ...          # context: what it should know, and the conversation to carry on from
def model_interface(): ...         # model interface: endpoint, model, and reasoning
def output(): ...                  # output: what it may act with, and every step as a line the program reads
def control_flow(): ...            # control flow: run once with nobody there, bounded, and exit
def handle(line): ...              # one line the harness printed, as the events above
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

Its program, [agent-claude-code.py](agent-claude-code.py), is that one-liner as five functions:

```python
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

Its program, [agent-codex.py](agent-codex.py), is that one-liner as five functions:

```python
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

Its program, [agent-opencode.py](agent-opencode.py), is that one-liner as five functions:

```python
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
```

## One agent, any harness

Each of the three programs runs by itself, and they cannot be told apart from outside:

```sh
echo '{"message": "Create notes.txt containing the word PELICAN."}' | python3 agent-codex.py
```

```json
{"type": "session", "id": "01a20b24-…"}
{"type": "step", "text": "edit /…/notes.txt"}
{"type": "text", "text": "Created `notes.txt` containing `PELICAN`."}
```

Put `agent-claude-code.py` or `agent-opencode.py` in that command and the request and the events are the same.
That is the unified JSON. So an agent that can change its harness needs one more field, and nothing else:

```json
{"harness": "codex", "session": "…", "message": "…"}
```

[agent.py](agent.py) is that agent. It has a chat console, and for each message it starts the program the
request names. A fourth harness is a fourth file.

For the change to go unseen, the session cannot belong to a harness. It is three things the agent keeps:

| | |
|---|---|
| **Mind** | The home folder. Each harness keeps its own memory there, side by side, and is carried on by its own id |
| **Work** | The working folder. Every harness shares it |
| **What was said** | Kept by the agent. A harness that was not the one answering is given the turns it missed, with the next message |

What the agent needs is in one folder, [agent/](agent): who it is, `AGENTS.md`, and its page.

```sh
python3 agent.py          # then open http://127.0.0.1:8500/
```

I told Claude Code my name and had it write a file. Codex, asked next, knew my name and added a line. OpenCode
showed the file, and asked who wrote the second line, said it had. The person sees one agent, and only chooses
what is behind it.

Run this way, the agent acts without asking, as you, on your machine.

## A sandbox

The last change is to where a program is started, which is one function in `agent.py`. With `--sandbox`, each
turn is the same program in a container that is thrown away:

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

That is the whole of it: a chat console, any harness behind the agent, and every turn sandboxed. The questions
never change. Only the implementations do.
