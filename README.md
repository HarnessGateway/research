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

Write the program that drives it. It takes a request and does five things, one for each primitive:

```python
def as_input(request): ...         # input: the request, in the form the harness takes it
def context(session): ...          # context: instructions, skills, and the session to continue
def model_interface(): ...         # model interface: endpoint, model, and reasoning
def output(): ...                  # output: what it may act with, and every step as a line the program reads
def turn(request, session): ...    # control flow: start it with nobody there, feed it, read it, and stop it
```

What makes it this agent and not another lives beside the program, as files: its instructions, its skills, and
its settings.

## Worked examples

The framework, applied to three harnesses. Each ends in the one command that runs it with nobody there.
The provider is DeepSeek throughout, because one key serves the three APIs these harnesses speak.

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

## The three agents

Each one-liner, slotted into the program of step 7: [agent-claude-code.py](agent-claude-code.py),
[agent-codex.py](agent-codex.py), and [agent-opencode.py](agent-opencode.py). Each is under 60 lines. This is
Codex's:

```python
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
```

One more function, `handle`, turns each line the harness prints into what the console shows: words, a step, or
an error.

Everything that is the same for every harness exists once, in [console.py](console.py): installing it at its
pinned version, starting it, stopping it, keeping sessions, and serving the chat page,
[console.html](console.html).

```sh
python3 agent-codex.py          # then open http://127.0.0.1:8500/
```

Run this way, the agent acts without asking, as you, on your machine.

## One request for any harness

Three programs with the same five functions are one interface. A turn is one request, whatever runs it:

```json
{"harness": "codex", "session": "…", "message": "…"}
```

What comes back is the same too, one event a line: `session`, `step`, `text`, `error`, `done`.

To change harness in the middle of a conversation, the session cannot belong to a harness. It is three things
the console keeps:

| | |
|---|---|
| **Mind** | The home folder. Each harness keeps its own memory there, side by side, and is continued by its own id |
| **Work** | The working folder. Every harness shares it |
| **What was said** | Kept by the console. A harness that was not the one answering is given the turns it missed, with the next message |

```sh
python3 agent.py          # one console, a harness to pick for each message
```

I told Claude Code my name and had it write a file. Codex, asked next, knew my name and what was in the file.
OpenCode added a line to it. Asked who had added that line, Claude Code said it had. The person sees one agent,
and only chooses what is behind it.

## A sandbox

The last change is to where a harness is started, which is one function in `console.py`. With `--sandbox`,
every harness is installed and run in a container that is thrown away:

```sh
docker run --rm -i --init --cpus=2 --memory=4g --pids-limit=512 --read-only --tmpfs=/tmp:rw,exec,size=1g \
  --cap-drop=ALL --security-opt=no-new-privileges --user=10000:10000 \
  --volume=<session>/work:/work --volume=<session>/mind:/mind --volume=<tools>:/tools \
  --workdir=/work --env=HOME=/mind node:22 <the one-liner>
```

It is not root, it cannot change the image it runs in, it is capped, and it sees the session's two folders and
its own tools. Nothing else changed: not the request, not the three programs, not the page.

```sh
python3 agent.py --sandbox
```

In a browser, in one conversation: Claude Code wrote a haiku into a file, Codex recalled my name and added a
second, and OpenCode showed the file and counted two. I stopped Claude Code in the middle of a command, and
Codex, asked next, knew what had been going on.

That is the whole of it: a chat console, any harness behind the agent, and every turn sandboxed. The questions
never change. Only the implementations do.
