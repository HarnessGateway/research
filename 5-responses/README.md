# 5. One API: harness packages and OpenAI Responses

I could run any harness, safely, and carry on a session with any of them. But each still took its prompt its own
way and answered in its own format, and whatever called them had to know all of it. I wanted to ask every
harness the same way and be answered the same way.

Stage 3 had found that a harness is two things: how it is installed and how it is run. Those became two
programs. What was left to choose was the API in front of them.

## Why OpenAI Responses

Because I needed the session kept on the server. Stage 4's session is two folders, and they live where the
harness runs, not with whoever is asking. A caller cannot carry them, and should not have to.

Most model APIs are stateless: the caller holds the conversation and sends all of it again with every request.
That cannot work here, because the conversation is not the session. The session is a harness's own memory and a
folder of work, on a disk the caller never sees. I needed an API where the server keeps the state and a request
only names what it continues.

The OpenAI Responses API is that. A response is stored on the server under an id, and the next request says
`previous_response_id`. That one field is stage 4's session: it names the turn to continue from, and the server
finds the two folders. It also already had an item for everything stage 2 saw an agent do (run a command,
change a file, think, speak), and every client already speaks it. So I did not invent anything. I gave `run`
one job: read a Responses request, and print Responses output.

That is a **harness package**.

## A harness package

A folder with two programs:

```
install      runs once, before the first turn
run          runs once a turn
```

Both run in the container of stage 3, as a user that is not root, on a read-only root. They may be written in
any language the image can run. Anything else the two need can be in the folder beside them.

### install

Runs with the package's folder writable at `$HG_HARNESS`, which is its working directory, and `$HOME` in `/tmp`.
It installs the agent CLI at a pinned version under `$HG_HARNESS/tools`, by its makers' own method, and checks
the version it got. It is given no provider and no key. After it has run, the folder is read-only.

### What run is given

| | |
|---|---|
| `$HG_TURN/request.json` | The Responses request, exactly as it was sent |
| `$HG_TURN/previous.json` | The response this request continues from, or `null` |
| `$HG_HARNESS` | The installed package, read-only |
| `$HOME` | The session's `mind`: where the CLI keeps its own memory |
| the working directory | The session's `work` |
| `$HG_STATE` | A folder in `mind` for the package's own small values: the CLI's session id, to resume it |
| `$HG_MODEL`, `$HG_PROVIDER_KEY` | The model to call, and the provider's key |
| `$HG_PROVIDER_ANTHROPIC`, `$HG_PROVIDER_OPENAI_RESPONSES`, `$HG_PROVIDER_OPENAI_CHAT`, `$HG_PROVIDER_GEMINI` | The provider's base URL for each API it speaks: one variable for each, and none for an API it does not speak |

### What run does with the request

A request is the whole of the Responses API's, as it was sent. `run` gives its CLI every field the CLI has a flag
or a setting for:

| In the request | What a package does with it |
|---|---|
| `input` | The task. A string, or a list of messages: from the person (`user`), from whoever built the application (`developer`, `system`), and what the agent said earlier (`assistant`). A message is a string, or parts: `input_text`; `input_image`, with an `image_url`; `input_file`, with `file_data` and a `filename`, or a `file_url` |
| `instructions` | The CLI's system prompt for this turn. It must reach the CLI on a continued session too. What a `developer` or a `system` message says is instructions as well |
| `reasoning` | `effort`: how hard the CLI thinks |
| `text` | `format`, of type `json_schema`: the schema its answer must fit |
| `tools` | Of type `mcp`: a tool server to connect the CLI to, at `server_url`, with its `headers` and its `authorization` token |
| `tool_choice` | `none`: the CLI answers, and does nothing |

- A field the CLI has no use for is left alone, and `run` says so on standard error: nothing is ignored unsaid.
- It starts the CLI on the provider: with the base URL of the first API the CLI speaks, the key and the model.
  When the provider speaks none of them, it ends the turn as failed and says which APIs the CLI needs.
- When `previous.json` says the turn before did not complete, it tells the CLI so.

### What run prints

One JSON object a line, on standard output, and nothing else there. Standard error is the turn's log. Every
line is a piece of an OpenAI response, in one of three forms:

```json
{"type": "shell_call", "call_id": "c1", "status": "completed", "action": {"commands": ["ls"]}}
{"type": "response.output_text.delta", "delta": "Done."}
{"type": "response.completed", "response": {"usage": {"input_tokens": 1200, "output_tokens": 80}}}
```

1. **An output item, whole**: any item of the Responses API, without an `id`.
2. **A stream event**, for what arrives in pieces.
   - A piece of text: `response.output_text.delta` for what the agent says, and
     `response.reasoning_summary_text.delta` for what it thinks. Each goes on a message, or a reasoning, that is
     kept for it until anything else is printed.
   - An item that begins and ends: `response.output_item.added` with `{"item": {…}}`, the item with an `id` of
     your making and `"status": "in_progress"`; then `response.output_item.done` with the item as it ended.
3. **The last line**: how the run ended. `response.completed`; `response.incomplete` with
   `{"response": {"incomplete_details": {"reason": "max_output_tokens"}}}`; or `response.failed` with
   `{"response": {"error": {"code": "…", "message": "…"}}}`, the message saying what a person can do about it.
   `usage` is optional in each, and may carry `input_tokens_details` (`cached_tokens`, `cache_write_tokens`) and
   `output_tokens_details` (`reasoning_tokens`).

What an agent does, as output items. A call is printed when the agent makes it, and what came of it when it
returns, with the CLI's own id for the call as the `call_id` of both:

| The agent | The item |
|---|---|
| Says something | `message`: `{"type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "…", "annotations": []}]}`, or text deltas |
| Thinks | `reasoning`: `{"type": "reasoning", "summary": [{"type": "summary_text", "text": "…"}]}`, or reasoning deltas |
| Runs a command | `shell_call`, then `shell_call_output`: `{"type": "shell_call_output", "call_id": "c1", "status": "completed", "output": [{"stdout": "…", "stderr": "", "outcome": {"type": "exit", "exit_code": 0}}]}`. The exit code is the command's own; a command that ran out of time has `"outcome": {"type": "timeout"}` |
| Creates, changes or deletes a file | `apply_patch_call` with `"operation": {"type": "create_file" \| "update_file" \| "delete_file", "path": "…", "diff": "…"}`, the diff saying what changed, then `apply_patch_call_output`, with `"status": "failed"` and an `output` when it could not |
| Connects to a tool server | `mcp_list_tools`: `{"type": "mcp_list_tools", "server_label": "docs", "tools": [{"name": "lookup", "input_schema": {}}]}`, with an `error` when it did not connect |
| Calls a tool of a tool server | `mcp_call`, begun and ended: `{"type": "mcp_call", "id": "c2", "server_label": "docs", "name": "lookup", "arguments": "{…}", "status": "completed", "output": "…"}`, or `"status": "failed"` with `"error": {"type": "mcp_tool_execution_error", "content": "…"}` |
| Searches the web, or opens a page | `web_search_call`, begun and ended: `{"type": "web_search_call", "id": "c3", "status": "completed", "action": {"type": "search", "query": "…", "sources": [{"type": "url", "url": "…"}]}}`, or `"action": {"type": "open_page", "url": "…"}` |
| Uses any other tool | `custom_tool_call` with `name` and `input` (a string), then `custom_tool_call_output` with the same `call_id`, a `status` and `output` |

### Sessions and stopping

- The moment the CLI reports its own session id, `run` writes it under `$HG_STATE`. On the next turn it finds it
  there and resumes that session.
- A stopped turn sends `SIGTERM` to `run` and to the CLI at once. `run` takes the signal, does nothing with it,
  and goes on reading until the CLI has ended, which is what gives the CLI the time to save its session.

## The three packages

[claude-code](../packages/claude-code/run), [codex](../packages/codex/run) and
[opencode](../packages/opencode/run). Each `run` is about a hundred lines: its harness's nine answers from stage
2, written down as a program. They take the slice of the API the work began with: `input` as text,
`instructions`, and five kinds of item. [Stage 7](../7-fde) takes one of them as far as its CLI goes. What each
turns into what:

| The agent | Claude Code prints | Codex prints | OpenCode prints | The package prints |
|---|---|---|---|---|
| Runs a command | `tool_use` named `Bash` | `command_execution` | `tool_use` with tool `bash` | `shell_call` |
| Writes a file | `tool_use` named `Write` | `file_change` | `tool_use` with tool `write` | `apply_patch_call` |
| Says something | `stream_event` text deltas | `agent_message` | `text` | a `message`, or text deltas |
| Finishes | `result` with usage | `turn.completed` with usage | `step_finish` with tokens | `response.completed` |

## The file

[respond.sh](respond.sh) runs one turn of a package by hand:

```sh
./respond.sh codex '{"input": "Create fact.txt containing the word PELICAN, then run: cat fact.txt"}'
./respond.sh codex '{"input": "Which word is in the file?", "instructions": "End every reply with the word ZEBRA."}'
```

I sent those two requests to each of the three. All three wrote the file and printed the same kinds of line; all
three, continuing, knew the word and ended with ZEBRA.

## What it led to

Every harness now takes the same request and gives the same answer. The only thing still done by hand was
running it: [6. Core](../6-core).
