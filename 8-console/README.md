# 8. A console

Everything so far I had used from a terminal: a script, then `curl`, then a few lines of Python with the OpenAI
client. That is how an application uses the core. It is not how a person looks at what an agent did. I wanted a
page: type, send, see each step the agent took, carry on, and change harness when I like.

## The file

[console.html](console.html) is 113 lines: one page, no library, no build step. The core hands it out at its
root:

```sh
python3 ../6-core/core.py          # then open http://127.0.0.1:8600/
```

## What it is

| | |
|---|---|
| The model line | One field: `harness/provider/model`. Change it between two messages and the next is run by another harness, on the same session |
| A message | `POST /v1/responses` with `input`, and `instructions` when some are given |
| Carrying on | The page keeps one value, the id of the last response, and sends it as `previous_response_id`. That is the whole of a session, to a client. "New session" forgets it |
| A reply | Drawn from the response's output items alone: words, thinking, a command and what it printed, a file's diff, a call to a tool server, a search. An item the page has no words for is shown as it is |
| The payload | Under every reply, folded: the response as the core returned it |

## What I noticed

- **The page knows no harness**, as the core knows none. It reads output items, and stage 5 made every package
  print the same ones. So it shows the work of a package it has never seen, one HG FDE writes included.
- **A console is a client.** It calls the one route any application calls, and it asked nothing new of the API.
  The core gained one thing for it: `GET /`, which hands out the file.
- **A browser is a new door.** A page of any other site can make a browser post to `127.0.0.1`. So the core now
  takes a request only as `application/json`, which such a page cannot send unasked. And what an agent printed is
  only ever text on this page: none of it becomes markup.

## What I ran

One session, in a real browser. Claude Code wrote a file and ran a command that exits with 3; Codex appended a
line, with instructions given for that one request; Pi printed both lines. Each reply named the harness that
made it and showed its steps, and the session's id stayed the same. A model line that names no harness is
refused in the core's own words.

## What it is not

| Missing | Why it matters |
|---|---|
| Streaming | The core answers when the turn has ended, so the page shows a clock and then the whole reply |
| Markdown, and a look at the files | A reply is plain text, and what the agent made is only named in its steps |
| Anything kept | A page that is closed has forgotten its session. Only the model line is remembered |
| Setting anything up | A provider is a constant in `core.py`, and a harness a folder in `packages/` |

Every one of those is in [HarnessGateway](https://github.com/HarnessGateway/harnessgateway)'s console, which is
also a client of its API and nothing more.

## Where the story ends

A request in one shape, a container that is thrown away, two folders that are kept, a package of two programs,
one package that builds the rest, and a page to use them through. That is the whole of the idea, and all of it
is in this repository, small enough to read in an afternoon.

This is where the research stops and the platform begins:
[HarnessGateway](https://github.com/HarnessGateway/harnessgateway), the self-hosted community edition, which
ships two packages: a shell, to try an environment, and HG FDE, to build the rest.
