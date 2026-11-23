# 1. How to research a harness

To build an agent around a harness, I first have to know the harness. Every agent CLI can be run without a
person, told which model to call, given instructions and asked to carry on where it left off. Each does it with
different words. Researching a harness is finding its words for the same nine things.

## The nine questions

| | Question | What I am looking for |
|---|---|---|
| 1 | How is it installed? | Its makers' own method, the latest stable version, and what the machine must already have |
| 2 | How does it run one turn with no person? | The headless flag or subcommand, and where the prompt goes: an argument, or standard input |
| 3 | What does it print that a program can read? | Its machine-readable output, and what each line of it means |
| 4 | How is it told its provider? | Where the base URL, the key and the model go, and which provider APIs it speaks |
| 5 | How is it given instructions? | Where a system prompt goes for one run |
| 6 | How does it continue a session? | Where it keeps a session, what names one, and the flag that resumes it |
| 7 | How does it act without asking? | What approves its commands and edits when nobody is there to |
| 8 | How is it kept off the network? | Turning off updates, telemetry and anything else it fetches unasked |
| 9 | What does it leave behind? | What appears in its home folder and its working folder after a run |

## The order

1. **Install it at a pinned version**, by its makers' method, somewhere that is thrown away afterwards.
2. **Read its `--help`**, and the help of every subcommand that looks like it answers a question above.
3. **Read its documentation**, for what the help does not say.
4. **Try it**: one turn, headless, against a real provider. Keep what it printed.
5. **Try the things that matter twice**: a second turn on the same session, with different instructions.

## The rules

- **Help wins over documentation.** Documentation is often written for another version than the one installed.
- **A test wins over both.** What a CLI does on a resumed session is rarely written down anywhere.
- **Pin the version.** An answer is true of one version. Say which.
- **Say where each answer came from**: help, documentation, or a test.

## The file

[research.sh](research.sh) does steps 1 and 2 for a CLI that is installed from npm: it installs it in a
container and saves its help, to be read.

```sh
./research.sh @openai/codex@0.171.0 codex exec "exec resume" mcp
```

Inside a sandbox, where there is no Docker, the same two steps are done directly: install the CLI under `/tmp`
and run its `--help`.

## What it led to

A method is only worth having if it holds for more than one harness. So I took the three most installed agent
CLIs and asked each the nine questions: [2. Headless](../2-headless).
