# 6. The core

Everything was there. A harness was a package of two programs. A turn was one `docker run`. A session was two
folders. The request and the answer were OpenAI Responses. The only thing left was that I was the one running
it, so I put it behind HTTP.

## The file

[core.py](core.py) is 168 lines of standard library, and it is the whole of the idea:

```sh
python3 core.py          # http://127.0.0.1:8600/v1
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8600/v1", api_key="none")
first = client.responses.create(model="claude-code/deepseek/deepseek-flash", input="Write fizzbuzz.py and run it.")
again = client.responses.create(model="codex/deepseek/deepseek-flash", input="Now add a test.",
                                previous_response_id=first.id)        # another harness, the same session
```

It adds nothing to the API. The one field with a meaning of its own is `model`, which says what runs the request
and with what: `harness/provider/model`.

## What happens to a request

| | | From |
|---|---|---|
| 1 | `model` names a package in `../packages` and a provider | |
| 2 | `previous_response_id` finds the session, or a new one begins: two folders, `mind` and `work` | stage 4 |
| 3 | The package is installed, once: a copy of its folder that its `install` has run in | stage 5 |
| 4 | The request is written to a file, and the package's `run` is started in the container | stages 3 and 5 |
| 5 | What `run` printed becomes the response: items are given ids, pieces of text are gathered into a message | stage 5 |
| 6 | The response is kept, so that the next request can continue from it | |

## What I ran

Two requests to each of the three packages, through the OpenAI client: write a file, then, continuing, say what
is in it, with instructions given only on the second request. All three did both. Every response is what the
OpenAI SDK's own model of a response describes.

Then one session across all three: Claude Code wrote the file, OpenCode appended to it, Codex printed both
lines. Three requests, three harnesses, one `previous_response_id` after another.

## What it is not

It is the idea, working, for one person on their own machine. It answers one request at a time, on `127.0.0.1`,
with no key.

| Missing | Why it matters |
|---|---|
| Secrets kept out of the container | The provider's real key is handed to the agent, which can send it anywhere |
| A network policy | The container reaches every host |
| Snapshots | A session is one folder: it cannot be forked, or taken back to an earlier turn |
| Streaming, a queue, cancelling | A caller waits for the whole turn, and turns run one after another |
| Environments, limits that can be set, usage, API keys, a console | It is one image and one user |

Every one of those is a part of [HarnessGateway](https://github.com/HarnessGateway/harnessgateway). None of them
changes what is here: a package is still `install` and `run`, a turn is still that container, a session is still
those two folders, and the API is still Responses, unmodified.

## What it led to

The core runs any harness that has a package, and a package is the nine answers of stage 1 written as two
programs. I had written three by hand, the same way each time: research the CLI, write `install`, write `run`,
try it. That is a job with a method and a contract, both of which are already written down in this repository.
It is a job for an agent: [7. FDE](../7-fde).
