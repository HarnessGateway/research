# 7. One harness package to build the rest

I had written three harness packages by hand, and done the same thing each time: research the CLI, write
`install`, write `run`, try it. That is forward deployed engineering work with a method and a contract, and by
now both were written down in this repository:

- the method is [stage 1](../1-research): the nine questions, the order, the rules;
- the contract is [stage 5](../5-responses): what `install` and `run` are given, and what `run` prints.

So the question was whether an agent, given those two pages, could do the job. And the platform already had a
way to run an agent: as a harness package.

## The package

[packages/fde](../packages/fde) is HG FDE, the forward deployed engineer for the platform. It is five files, and
three of them are not new:

| | |
|---|---|
| `install` | The Claude Code package's own, by link. HG FDE is a harness like any other |
| `research.md` | Stage 1's page, by link |
| `contract.md` | Stage 5's page, by link |
| `AGENTS.md` | Who it is, the five steps of the job, and where to put the package |
| `run` | The Claude Code package's `run`, taken as far as Claude Code goes |

A package's `run` gives its agent whatever pages sit beside it, before the person speaks. So HG FDE is taught by
the same two pages a person reads here, and when either page changes, what it knows changes with it.

## Its run, and the whole of the API

The three packages of stage 5 take a slice of the Responses API: a prompt, instructions, five kinds of item. That
was enough to find the contract. It is not what a builder should copy, and a builder copies its own `run`: every
package HG FDE writes has the shape of it. So its `run` uses everything of the API that its CLI has a flag or a
setting for, and says what it leaves alone.

What it gives Claude Code of a request:

| In the request | Claude Code is given |
|---|---|
| `input`, from the person | One message (`--input-format stream-json`): words as words, an `input_image` as an image, an `input_file` as a file put in `/tmp/given` |
| `instructions`, and what a `developer` or a `system` message says | Its system prompt for the turn (`--append-system-prompt`), after the package's own pages |
| What the agent said earlier (`assistant` messages) | Words, each told as what it said |
| `reasoning.effort` | `--effort` |
| `text.format`, a JSON schema | `--json-schema`. The response is then one message, and it fits the schema |
| `tools` of type `mcp` | `--mcp-config`: the server's address, its `headers`, and its `authorization` as a bearer token |
| `tool_choice: "none"` | `--tools ""`: it answers, and does nothing |
| `temperature`, `max_output_tokens`, a `function` tool, and the rest | Nothing: Claude Code has no flag for them. Each is named in the turn's log |

What it prints of what Claude Code does:

| Claude Code | The response has |
|---|---|
| Speaks, thinks | Text and reasoning, piece by piece as they arrive |
| Runs a command (`Bash`) | `shell_call` when it calls, `shell_call_output` when the command returns, with its real exit code |
| Writes or edits a file (`Write`, `Edit`) | `apply_patch_call`: `create_file` or `update_file`, with the diff Claude Code reports |
| Starts with a tool server | `mcp_list_tools`: the server's tools, or the `error` when it did not connect |
| Calls a tool of a tool server | `mcp_call`, as an item that begins (`response.output_item.added`) and ends (`response.output_item.done`) with its `output`, or its `error` |
| Searches the web, opens a page (`WebSearch`, `WebFetch`) | `web_search_call`, begun and ended the same way: a search with its `sources`, a page with its `url` |
| Uses any other tool | `custom_tool_call`, then `custom_tool_call_output` |
| Ends | `response.completed` or `response.failed`, with the tokens it used: input, output, cached, and reasoning |

## The file

[build.py](build.py) asks it for a package, through the core, and brings what it wrote into `packages/`:

```sh
python3 ../6-core/core.py &
./build.py pi "the Pi coding agent CLI, the npm package @earendil-works/pi-coding-agent"
```

It is one Responses request to `fde/deepseek/deepseek-flash`, like any other.

## What I ran

I asked it for Pi, a CLI I had written no package for. I asked twice.

**The first time**, its `run` was the Claude Code package's. In under twelve minutes it installed Pi 1.6.0, read
its help and its documentation, ran it headless against the provider over two APIs, and wrote `install`, a `run`
of 256 lines and a `README.md` giving the nine answers and where each came from. The package ran on the core
untouched. It took of a request what its builder's `run` showed it, and a little more: a prompt, instructions,
an effort.

**Then I gave it a `run` of its own**, and tried a request for each row of the two tables above: a `developer`
message and an effort; a continued turn with new instructions; a schema for the answer; a tool server with a
token, beside one that is not there; a search and a page; an image and a file inside the request; and no tools.
Each did what its row says. I held every line it printed to HarnessGateway's own rule for a printed line, and
none was refused; the responses the core made of them are what the OpenAI SDK's own model of a response
describes.

**The second time** I asked for Pi, it took 25 minutes, because it tried more. It wrote itself a tool server to
see how Pi takes one, gave Pi an image and a file, ran a command that fails and one that runs out of time, and
stopped a turn to see the session kept. [packages/pi](../packages/pi) is that package, exactly as it wrote it:
a `run` of 562 lines, and a README that says what it honours and what it leaves alone. I ran it on the core
without touching it:

| Request | Answer |
|---|---|
| `pi`: create a file, then run a command that exits 3 | wrote the file; the response has the command's exit code, 3 |
| `pi`, continuing, with an effort: edit the file | `update_file`, with the diff of the one line |
| `pi`, with a `developer` message, on a new turn and on a continued one | obeyed it both times |
| `pi`, with a tool server and a token, beside a server that is not there | listed the first server's tools, said the second did not connect, and called the tool |
| `pi`, with an image and a file inside the request | read the word in the file |
| `codex`, on the same session, then `pi` again | Codex appended a line; Pi printed the file, and said it held a line it had not written |
| `pi`, with `tool_choice: "none"` | answered, and ran nothing |

Every response is what the OpenAI SDK's own model of a response describes. Two things did not go as they
should. Once, on a continued turn with several steps, Pi left a `developer` message unheeded. And the package
gives Pi its own `README.md` as instructions on every turn: it copied that from its builder, whose `run` gives
itself the pages beside it. A builder's own habits are copied with its good ones.

The answer about the line it had not written is stage 4's finding again, seen from inside: a harness is not told
what another did.

## Where the story ends

One harness package builds every other harness package, because it knows how I research a harness, it knows the
contract, and it runs on the platform it builds for. The work this repository set out to capture, building an
agent around any agent harness CLI, is now something I can ask for by name.

This is where the research stops and the platform begins:
[HarnessGateway](https://github.com/HarnessGateway/harnessgateway), the self-hosted community edition, which
ships two packages: a shell, to try an environment, and HG FDE, to build the rest.
