# Pi harness package

The Pi coding agent CLI, `@earendil-works/pi-coding-agent`, at **1.6.0** (the `latest` tag on npm when this was
written), behind the OpenAI Responses API. `install` puts it under `$HG_HARNESS/tools`; `run` turns one Responses
request into one Pi turn and Pi's JSON event stream back into Responses items.

The answers below are true of 1.6.0. Each says where it came from: **help** (`pi --help`, `pi mcp --help`,
`pi auth --help`), **docs** (the `docs/` shipped inside the package), or **test** (a headless run against this
session's provider).

## The nine questions

| | Question | Answer | Source |
|---|---|---|---|
| 1 | How is it installed? | npm: `npm install --prefix $HG_HARNESS/tools @earendil-works/pi-coding-agent@1.6.0`. It is plain JavaScript (`dist/bundle/cli.js`); there is no postinstall step and nothing is built. It needs Node >= 22.19.0 (`engines`), and `install` refuses an older Node. | docs: `package.json`; test: install + `--version` |
| 2 | How does it run one turn with no person? | `pi --mode json --print`. The prompt goes in on standard input; Pi prepends piped stdin to the first prompt. The prompt can also be the last argument, and `@path` arguments attach files. `--mode json` implies one-shot even without `--print`. | help; docs `cli.md`, `json.md`; test |
| 3 | What does it print that a program can read? | JSONL on stdout: a `session` header, then `agent_start`, `turn_start`, `message_start`/`message_update`/`message_end`, `tool_execution_start`/`tool_execution_end`, `turn_end`, `agent_end`, `agent_settled`. `message_update.assistantMessageEvent` carries `text_delta`, `thinking_delta`, `toolcall_*`. Usage is on each assistant `message_end`. | docs `json.md`; test |
| 4 | How is it told its provider? | `models.json` in the agent directory (`$PI_CODING_AGENT_DIR`, default `~/.pi/agent`): a provider with `baseUrl`, `api`, `apiKey` and a model. There is no base-URL command-line flag and no `ANTHROPIC_BASE_URL`-style variable (`models.json` is the documented way). `--provider hg --model <id>` selects it. It speaks Anthropic Messages, OpenAI Responses, OpenAI Chat Completions and Google Generative AI. | help; docs `models.md`, `models-configuration.md`, `providers.md`; test |
| 5 | How is it given instructions? | `--append-system-prompt <text-or-file>`, repeatable. `run` writes the combined text to a file under `$HG_STATE` and passes the path. A test confirmed it reaches a **resumed** session. `--system-prompt` replaces Pi's own prompt, which would remove Pi's tool guidance, so it is not used. | help; docs `cli.md`; test |
| 6 | How does it continue a session? | Sessions are saved under `~/.pi/agent/sessions/` (in this container, `$HOME`, the session's mind). The session header's `id` names one; `--session-id <id>` opens that session for the current directory or creates it. `run` writes the id to `$HG_STATE/session` the moment the header arrives. | help; docs `sessions.md`, `json.md`; test (second turn knew the first's file) |
| 7 | How does it act without asking? | It acts without asking by default: `bash`, `edit` and `write` have no approval step in print/JSON mode. `--no-approve` keeps it from trusting project-local `.pi` configuration and resources. The container is what holds it. | help; docs `security.md` |
| 8 | How is it kept off the network? | `--offline` (equal to `PI_OFFLINE=1`) disables startup network operations and model-catalog refreshes; `PI_SKIP_VERSION_CHECK=1` disables the pi.dev version check; `PI_TELEMETRY=0` disables telemetry and provider attribution headers. `run` sets all three. | help; docs `environment-variables.md` |
| 9 | What does it leave behind? | In `$HOME`: `.pi/agent/` with `models.json` (written by `run` every turn), `mcp.json` (written every turn), `auth.json`/`mcp-auth.json` if anything signs in, and `sessions/<cwd-slug>/<time>_<id>.jsonl`. In the working directory: whatever the agent creates, plus `.pi/` only if something writes it. `run` writes no files there. | test |

## The provider APIs it speaks

Pi has an API implementation for each of these; `run` uses the first one the provider's environment supplies:

| Variable | Pi `api` | Pi's name for the protocol |
|---|---|---|
| `HG_PROVIDER_ANTHROPIC` | `anthropic-messages` | Anthropic Messages |
| `HG_PROVIDER_OPENAI_RESPONSES` | `openai-responses` | OpenAI Responses |
| `HG_PROVIDER_OPENAI_CHAT` | `openai-completions` | OpenAI Chat Completions |
| `HG_PROVIDER_GEMINI` | `google-generative-ai` | Google Generative AI |

It also speaks Azure OpenAI Responses, Mistral Conversations and Bedrock Converse, but this contract names no base
URL for those, so they are not reachable here. When no variable is set, `run` ends the turn as failed with code
`no_provider` and names the four APIs. The key goes in `models.json` as `$HG_PROVIDER_KEY` (Pi interpolates the
environment variable at request time), so no secret is written to disk.

## What `run` honours, and what it leaves alone

| Request field | How Pi is given it |
|---|---|
| `input` (string, or message items) | One prompt on stdin. `user` parts become text; `input_image` with a data URL and `input_file` with `file_data` are written under `$HG_STATE/given` and passed as `@path` (Pi inlines text files and attaches images). An image or file at a URL is named in the prompt and noted on stderr: Pi reads from disk, not from a URL. An earlier `assistant` message is given as "Earlier, you said: …". A `developer` or `system` message is instructions. |
| `instructions` | `--append-system-prompt` (file), together with any `developer`/`system` text in `input`. It also reaches a resumed session. |
| `reasoning.effort` | `--thinking` with the same level: `none`→`off`, then `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. A model is told it reasons only when the request asks for an effort. Other `reasoning` fields are noted on stderr. |
| `tools` of type `mcp` | `mcp.json` in the agent directory, one server per request entry with `exposure: "direct"` so its tools are declared to the model. `authorization` becomes `Authorization: Bearer …`; `headers` override it. `$` and a leading `!` are escaped so header values stay literal. The server's tools are printed as `mcp_list_tools` from `pi mcp list --json` before the turn, or from the tools-added system message when the listing did not reach it. |
| `tool_choice: "none"` | `--no-tools`, and no MCP servers are configured; Pi answers and does nothing. |
| `text.format` of type `json_schema` | **Left alone**: Pi 1.6.0 has no flag or setting for a schema-constrained answer. The turn is noted on stderr. |
| `model`, `previous_response_id`, `stream`, `background`, `store`, `metadata` | Core Responses fields with no Pi equivalent; `model` is replaced by `$HG_MODEL` and `previous_response_id` by the stored Pi session. |

Anything else in the request (an unknown field, a non-`mcp` tool, another `tool_choice`, another `text` key) is
named on standard error, one note per field. Nothing is ignored unsaid.

## What `run` prints

One JSON object per line on stdout: `message` / `reasoning` items (or their deltas), `shell_call` +
`shell_call_output`, `apply_patch_call` + `apply_patch_call_output` for `write` and `edit`, `mcp_list_tools`,
`mcp_call` (begun and ended), `custom_tool_call` + `custom_tool_call_output` for `read`, `grep`, `find`, `ls`,
`codemode`, `tool_search` and any other tool Pi registers, and the final `response.completed`,
`response.incomplete` (Pi's `stopReason: "length"`) or `response.failed` (an error or abort, or Pi exiting before
it settled). Usage is summed over the assistant messages of the run: input includes cache reads and cache writes,
and `output_tokens_details.reasoning_tokens` is Pi's `usage.reasoning`.

## Files

```
install      npm install at the pinned version, then a version check
run          Python 3, standard library only; one turn
README.md    this file (also given to Pi as part of its system prompt)
```
