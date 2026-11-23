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
four of them are not new:

| | |
|---|---|
| `install`, `run` | The Claude Code package's own, by link. HG FDE is a harness like any other |
| `research.md` | Stage 1's page, by link |
| `contract.md` | Stage 5's page, by link |
| `AGENTS.md` | The one new file: who it is, the five steps of the job, and where to put the package |

A package's `run` gives its agent whatever pages sit beside it, before the person speaks. So HG FDE is taught by
the same two pages a person reads here, and when either page changes, what it knows changes with it.

## The file

[build.py](build.py) asks it for a package, through the core, and brings what it wrote into `packages/`:

```sh
python3 ../6-core/core.py &
./build.py pi "the Pi coding agent CLI, the npm package @earendil-works/pi-coding-agent"
```

It is one Responses request to `fde/deepseek/deepseek-flash`, like any other.

## What I ran

I asked it for Pi, a CLI I had written no package for. In under twelve minutes it:

1. installed Pi 1.6.0 and read its help and its documentation,
2. ran it headless against the provider, over two different APIs, and kept what it printed,
3. wrote `install`, `run` (256 lines) and a `README.md` giving the nine answers and where each came from,
4. handed over: *pi is ready in /work/pi*.

[packages/pi](../packages/pi) is that package, exactly as it wrote it. I ran it on the core without touching it:

| Request | Answer |
|---|---|
| `pi`: create a file holding one word | wrote the file |
| `pi`, continuing, with new instructions | named the word, checked it with a command, and obeyed the instructions |
| `codex`, on the same session | appended a line to the file Pi wrote |
| `pi`, again | printed the file, and said it held a line it had not written |

All four responses are what the OpenAI SDK's own model of a response describes. The last answer is stage 4's
finding again, seen from inside: a harness is not told what another did.

## Where the story ends

One harness package builds every other harness package, because it knows how I research a harness, it knows the
contract, and it runs on the platform it builds for. The work this repository set out to capture, building an
agent around any agent harness CLI, is now something I can ask for by name.

This is where the research stops and the platform begins:
[HarnessGateway](https://github.com/HarnessGateway/harnessgateway), the self-hosted community edition, which
ships two packages: a shell, to try an environment, and HG FDE, to build the rest.
