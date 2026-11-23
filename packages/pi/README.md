# Pi harness package

Pi, the coding agent CLI made by Earendil Works, from the npm package
`@earendil-works/pi-coding-agent`. This package pins **1.6.0**.

```
install   npm install of the pinned package into $HG_HARNESS/tools
run       one Responses turn: starts Pi headless and prints Responses output
```

Both are executable; `run` is Python 3, standard library only.

## The nine answers

### 1. How is it installed?

npm, which is its makers' own method:

```sh
npm install --prefix "$HG_HARNESS/tools" @earendil-works/pi-coding-agent@1.6.0
```

The package's `bin` is `pi` → `dist/bundle/cli.js`, plain JavaScript with no build or native step.
The machine needs **Node.js >= 22.19.0** (`engines` in the package's `package.json`; tested on
v22.23.5). `install` runs npm with `--ignore-scripts` (nothing in the package needs a post-install
script) and checks `pi --version` equals `1.6.0`.

*Source: `package.json` (`bin`, `engines`), `npm view`, and a test install under `/tmp`.*

### 2. How does it run one turn with no person?

`-p` / `--print` makes it process a prompt and exit. `--mode json` selects the machine interface.
The prompt is the positional `[messages...]` argument or **piped stdin**. When stdin or stdout is
not a terminal and no mode is chosen, Pi selects print mode itself.

`run` writes the prompt to stdin and closes it, so a prompt that begins with `-` needs no escaping
and there is no argv size limit. (Piped stdin is read to EOF; a reader that never closes stdin
leaves Pi waiting — closing it is part of the turn.)

*Source: `pi --help`, `docs/cli.md`, `docs/cli-integration.md`; tested with a positional prompt, a
piped prompt, and an unclosed pipe (which hangs — hence the close).*

### 3. What does it print that a program can read?

`--mode json` writes strict JSONL on stdout, one event per line:

| Record | Meaning |
|---|---|
| `session` | Session header: `{type, version, id, timestamp, cwd}`. The id is Pi's own session id. |
| `message_update` | `assistantMessageEvent` of type `text_delta` / `thinking_delta` (and `toolcall_*`), with a cumulative `usage` |
| `message_end` | The authoritative message; assistant messages carry `stopReason`, `errorMessage`, `usage` (`input`, `output`, `cacheRead`, `cacheWrite`, `totalTokens`) |
| `tool_execution_start` | `{toolCallId, toolName, args}` |
| `tool_execution_end` | `{toolCallId, toolName, result, isError, durationMs}` |
| `agent_settled` | Pi has no further automatic work; the run is over (`aborted`) |

Stdout is reserved for JSONL; diagnostics go to stderr. `docs/json.md` requires splitting only on
LF (not Unicode line separators); reading the stream line by line in Python does that.

*Source: `docs/json.md`; tested — the event sequence above is what a real run printed.*

### 4. How is it told its provider?

A custom provider in **`<agent-dir>/models.json`** (`<agent-dir>` = `$HOME/.pi/agent` by default,
or `$PI_CODING_AGENT_DIR`):

```json
{"providers": {"hg": {
  "baseUrl": "https://…", "api": "anthropic-messages", "apiKey": "…",
  "models": [{"id": "…", "name": "…", "reasoning": false, "input": ["text"],
              "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
              "contextWindow": 128000, "maxTokens": 8192}]}}}
```

Selected with `--provider hg --model <id>`. The `api` values Pi implements that the harness's
provider variables name are:

| Provider variable | Pi `api` | Pi's name for it |
|---|---|---|
| `HG_PROVIDER_ANTHROPIC` | `anthropic-messages` | Anthropic Messages |
| `HG_PROVIDER_OPENAI_RESPONSES` | `openai-responses` | OpenAI Responses |
| `HG_PROVIDER_OPENAI_CHAT` | `openai-completions` | OpenAI Chat Completions |
| `HG_PROVIDER_GEMINI` | `google-generative-ai` | Google Generative AI |

(Pi also speaks Azure Responses, Mistral Conversations, Bedrock Converse, and Vertex; the harness
names none of these.) `run` writes `models.json` each turn with the chosen base URL, the model, and
`"apiKey": "$HG_PROVIDER_KEY"` — a name Pi resolves from the environment at request time, so the key
is never written to disk. It prefers the APIs in the order of the table above. Credential precedence
in Pi is `--api-key` > `auth.json` > `models.json apiKey` > provider environment variables; the
`models.json` reference is resolved from `HG_PROVIDER_KEY` and wins over anything else ambient.

*Source: `pi --help`, `docs/models.md`, `docs/models-configuration.md`, `pi-ai/dist/types.d.ts`
(`KnownApi`); tested against this session's provider with `anthropic-messages` and
`openai-completions`.*

### 5. How is it given instructions?

`--append-system-prompt <text|path>` appends text (or the contents of an existing file) to Pi's
default coding-assistant system prompt; it is repeatable. `--system-prompt <text|path>` replaces
the default prompt entirely. `run` writes `instructions` to `$HG_STATE/instructions.md` and passes
that path, appending rather than replacing so Pi's tool guidance survives.

The system prompt is rebuilt for every invocation, so the request's instructions reach a
**continued** session too — verified on a second turn that obeyed a new instruction.

*Source: `pi --help`, `docs/cli.md`; tested with raw text and with a file path, and on a resumed
session.*

### 6. How does it continue a session?

Pi saves sessions automatically unless `--no-session`. Sessions live under
`<agent-dir>/sessions/<working-directory>/<timestamp>_<id>.jsonl`. `--session-id <id>` uses the
current directory's existing session with that id, **creating it otherwise** — so the same id is
both how a session is started and how it is resumed. `--continue` / `--resume` / `--session
<path|id>` are the interactive alternatives. The first JSONL record (`session`) reports the id.

`run` keeps Pi's id in `$HG_STATE/session`, regenerates one only when absent, writes it before the
first word (so a stopped first turn is still continued), and passes `--session-id` on every turn.

*Source: `pi --help`, `docs/sessions.md`, `docs/configuration.md`, `docs/json.md`; tested — turn 2
resumed turn 1's conversation and knew a word only present in the prior turn.*

### 7. How does it act without asking?

Pi does not ask for approval before tool calls: `docs/security.md` states that generated commands
and edits run with the process's own permissions, with no per-call prompt. There is no
`--dangerously-skip-permissions` analogue.

What remains is **project trust**, which decides whether a working folder's `.pi/` resources
(extensions, MCP servers, skills, `SYSTEM.md`, settings) load. Print/JSON/RPC modes cannot show the
prompt: with the default `defaultProjectTrust: "ask"`, trust-gated project resources are skipped.
`run` passes `--no-approve` so this is explicit and the same on every turn; context files such as
`AGENTS.md`/`CLAUDE.md` still load, which is Pi's documented behavior.

*Source: `pi --help` (`-a/--approve`, `-na/--no-approve`), `docs/security.md`, `docs/cli.md`;
exercised in a working folder.*

### 8. How is it kept off the network?

* `--offline` / `PI_OFFLINE=1` — disables automatic network activity, including model-catalog
  refreshes.
* `PI_SKIP_VERSION_CHECK=1` — disables the `pi.dev` latest-version request.
* `PI_TELEMETRY=0` — disables install/update telemetry and provider attribution headers.
* `--no-mcp` — built-in MCP support off: no MCP server connects.

`run` sets all four; the only network traffic left is the model request itself.

*Source: `docs/environment-variables.md`, `docs/cli.md`; used in every test run.*

### 9. What does it leave behind?

In `$HOME` (Pi's memory): `.pi/agent/models.json` (written by `run` each turn), `.pi/agent/auth.json`
(`{}` unless something logs in), `.pi/agent/models-store.json` (catalog cache), and
`.pi/agent/sessions/<mangled-working-directory>/<timestamp>_<session-id>.jsonl`.

In the working directory: only what the agent itself created or changed.

`$HG_STATE` holds this package's two small values: `session` (Pi's session id) and
`instructions.md` (the current turn's instructions file, rewritten or removed each turn).

*Source: a test run inspected on disk.*

## Provider APIs Pi speaks

Anthropic Messages (`anthropic-messages`), OpenAI Responses (`openai-responses`), OpenAI Chat
Completions (`openai-completions`), Google Generative AI (`google-generative-ai`). When the
provider speaks none of them, `run` ends the turn with `response.failed` and code `no_provider`
naming the four.

## What `run` honours from the request

| Request field | What `run` does with it |
|---|---|
| `input` | Becomes the prompt: a string as-is; a list, the `input_text` (or `text`) parts of its `user` messages, joined by blank lines, written to Pi's stdin |
| `instructions` | Appended to Pi's system prompt for this turn via `--append-system-prompt` (also on a continued session) |
| `reasoning.effort` | Declares the model reasoning-capable and passes `--thinking <effort>` |
| `max_output_tokens` | Sets the model's `maxTokens` in `models.json` |
| anything else | Left alone — Pi has no flag or setting for it here |

`previous.json` is not read: continuation is Pi's own session, named by the id in `$HG_STATE/session`.

## What each thing Pi does becomes

| Pi | Package output |
|---|---|
| `text_delta` in `message_update` | `response.output_text.delta` |
| `thinking_delta` in `message_update` | `response.reasoning_summary_text.delta` |
| tool `bash` | `shell_call` with `action.commands:[command]`, then `shell_call_output` with Pi's merged output and the command's real `exit_code` |
| tool `write` (new path) | `apply_patch_call` `create_file`, diff of added lines, then `apply_patch_call_output` |
| tool `write` (existing path) | `apply_patch_call` `update_file`, unified diff from the old to the new contents |
| tool `edit` | `apply_patch_call` `update_file`, unified diff built from its `oldText`/`newText` edits |
| any other tool (`read`, …) | `custom_tool_call` with `name` and `input`, then `custom_tool_call_output` with the text result |
| `agent_settled` (or EOF) | `response.completed` with summed usage, or `response.failed` if Pi reported an error or never finished |

Usage sums each assistant message's `input`, `output`, `cacheRead`, and `cacheWrite`;
`input_tokens_details.cached_tokens` is the cache-read total.

A stopped turn (`SIGTERM` to `run` and Pi) is taken and ignored by `run`, which keeps reading until
Pi exits; because the session id is saved up front and Pi saves the session itself, the next turn
continues.
