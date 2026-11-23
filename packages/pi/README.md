# Pi coding agent harness package

`install` and `run` for **Pi**, the coding agent CLI from `@earendil-works/pi-coding-agent`.
Everything below is true of **Pi 1.6.0** (the version `install` pins), on Node >= 22.19.0.

## The nine answers

| | Question | Answer | Where it came from |
|---|---|---|---|
| 1 | How is it installed? | `npm install @earendil-works/pi-coding-agent@1.6.0`; the CLI is `dist/bundle/cli.js`, run by Node. Node >= 22.19.0 must already be on the machine. | `npm view` metadata, the package's `package.json` (`bin`, `engines`), and `install` itself |
| 2 | How does it run one turn with no person? | `pi -p` (`--print`, `--mode json` also runs once). The prompt is a trailing argument after `--`; `@path` arguments beside it attach files. Piped stdin is prepended to the first prompt, but a prompt argument is what this package uses. | `pi --help`; `docs/cli.md`; test |
| 3 | What does it print that a program can read? | `--mode json`: one JSON object per line on stdout. The first is `{"type":"session","id":…,"cwd":…}`, then `agent_start`, `turn_start`, `message_start`/`message_update`/`message_end`, `tool_execution_start`/`tool_execution_update`/`tool_execution_end`, `turn_end`, `agent_end`, `agent_settled`, plus `auto_retry_*` and `compaction_*`. Text and thinking arrive as `message_update.assistantMessageEvent` (`text_delta`, `thinking_delta`, `toolcall_delta`); token usage is on each assistant `message_end`/`turn_end`. | `docs/json.md`; test (`out7`, `out9`) |
| 4 | How is it told its provider? | A custom provider in `models.json` under the agent directory: `providers.<id>.baseUrl`, `api`, and `models`. The key is `--api-key` (or `apiKey` in `models.json`, with `$NAME` interpolation). The model is `--provider <id> --model <id>`. | `docs/models.md` (§ Configure a compatible endpoint), `docs/models-configuration.md`, `docs/providers.md`; test |
| 5 | How is it given instructions? | `--append-system-prompt <text>` (repeatable) adds to Pi's own coding-assistant prompt; `--system-prompt <text>` replaces it. The append flag is applied on every run, so it also reaches a resumed session. | `pi --help`; test (ZEBRA on a continued session) |
| 6 | How does it continue a session? | Sessions are JSONL files under the agent directory's `sessions/`, or under `--session-dir`. Each file is `<timestamp>_<uuid>.jsonl`; the uuid is the session id and is printed in the first `session` record. `--session-id <id>` uses that session (creating it if absent); `--continue`, `--resume` and `--session <id|path>` are the other forms. | `pi --help`; `docs/sessions.md`; `docs/json.md`; test |
| 7 | How does it act without asking? | It does not ask: Pi's tools run with the process's own permissions, and print/JSON/RPC modes cannot show the trust prompt. `--no-approve` makes an automated run ignore project-local protected resources (extensions, settings, trust-gated files); `--approve` trusts them. The sandbox is the boundary. | `docs/security.md`; `pi --help` |
| 8 | How is it kept off the network? | `--offline` (equivalently `PI_OFFLINE=1`) disables startup network activity, including model-catalog refresh. `PI_TELEMETRY=0` turns off telemetry and provider attribution headers. Updates only happen through an explicit `pi update`; `--no-approve` keeps project extensions from loading. | `pi --help`; `docs/cli.md`; `docs/environment-variables.md` |
| 9 | What does it leave behind? | In the agent directory (`PI_CODING_AGENT_DIR`): `auth.json`, `models-store.json`, `mcp.log` when a tool server logs, and (with this package) the `models.json` and `mcp.json` `run` writes. In the session directory: one JSONL session file per session, named `<timestamp>_<uuid>.jsonl`. In the working directory: the files the agent writes. | test (agent and session directories after the turns) |

## Provider APIs Pi speaks

Pi's provider layer implements **Anthropic Messages**, **OpenAI Responses**, **OpenAI Chat Completions** and
**Google Gemini** (plus Bedrock Converse and Mistral Conversations, for which the harness contract has no base
URL variable). The package names each of the contract's four variables to Pi's internal `api` value:

| Contract variable | Pi `api` value |
|---|---|
| `HG_PROVIDER_ANTHROPIC` | `anthropic-messages` |
| `HG_PROVIDER_OPENAI_RESPONSES` | `openai-responses` |
| `HG_PROVIDER_OPENAI_CHAT` | `openai-completions` |
| `HG_PROVIDER_GEMINI` | `google-generative-ai` |

## How `run` puts a request into Pi

| In the request | What `run` does |
|---|---|
| `input` as a string | The prompt argument. |
| `input` as messages | `user` text becomes the prompt; `developer`/`system` text becomes instructions; `assistant` text is added as "Earlier, you said: …". |
| `input_text` | Prompt text. |
| `input_image` | A data URL is decoded and passed as an `@path` argument; an `http(s)` URL is fetched and passed the same way (or, if the fetch fails, named in the prompt). |
| `input_file` | `file_data` (base64 or data URL) is written under `/tmp/given-<pid>/` and passed as `@path`; `file_url` is named in the prompt. |
| `instructions` | `--append-system-prompt`, every turn, so a continued session gets it. |
| `reasoning.effort` | `--thinking`: `none`/`off` → `off`; `minimal`, `low`, `medium`, `high`, `xhigh`, `max` as named. Other `reasoning.*` fields are left alone and logged. |
| `text.format` | Left alone and logged: Pi has no flag for constraining its final answer to a schema. |
| `tools` of type `mcp` | Written to the agent directory's `mcp.json` with `url`, `headers`, and `Authorization: Bearer …` from `authorization`; exposure is `direct` so the model calls `mcp__<server>__<tool>` itself. Other tool types are left alone and logged. |
| `tool_choice: "none"` | `--no-tools --no-mcp`. Other values are the default behaviour and are not acted on. |
| `previous.json` not `completed` | The prompt is prefixed with "Your last turn did not finish: it ended as …". |
| `model`, `previous_response_id`, `stream`, `background`, `store`, `metadata` | Core fields. The model is `$HG_MODEL` (as the contract says); the session is Pi's own id under `$HG_STATE`. |

Any other request field is named on standard error as left alone.

## How `run` turns what Pi does into Responses output

| Pi prints | `run` prints |
|---|---|
| `message_update` / `text_delta` | `response.output_text.delta` |
| `message_update` / `thinking_delta` | `response.reasoning_summary_text.delta` |
| `tool_execution_start` / `end` for `bash` | `shell_call` with `action.commands` (and `timeout_ms`), then `shell_call_output` with `stdout`, `stderr`, and the command's own `exit_code`; a timed-out command gets `{"type":"timeout"}` |
| `tool_execution_start` / `end` for `write` and `edit` | `apply_patch_call` with `create_file` (a new file) or `update_file`, `path`, and the diff — from `details.patch` for an edit, from the written content for a write — then `apply_patch_call_output` (`failed` with an `output` when it could not) |
| `tool_execution_start` / `end` for `mcp__<server>__<tool>` | `response.output_item.added` and `.done` around an `mcp_call` with `id`, `server_label`, `name`, `arguments`, `status`, and `output` or an `mcp_tool_execution_error` |
| The system message's `toolsAdded`, plus `pi mcp list --json` for each server's state | `mcp_list_tools` per configured server, with each tool's `input_schema` from Pi, and an `error` when the server did not connect |
| Any other tool (`read`, `grep`, `find`, `ls`, …) | `custom_tool_call` with `name` and `input`, then `custom_tool_call_output` with the same `call_id`, a `status` and `output` |
| `agent_settled` | `response.completed`, or `response.incomplete` (`max_output_tokens`) when the last stop reason was `length`, or `response.failed` for an error/stop. Usage is summed over the turn's assistant messages: `input_tokens` (including cache reads and writes), `output_tokens`, `cached_tokens`, `cache_write_tokens`, `reasoning_tokens`. |

Pi has no built-in web-search tool, so no `web_search_call` is produced.

## Sessions and stopping

The session id is written to `$HG_STATE/session` the moment the `session` record arrives, and read back on the
next turn as `--session-id`. `run` ignores `SIGTERM` and keeps reading until Pi exits, so Pi can save its session
after a stopped turn.
