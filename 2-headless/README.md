# 2. The top three, headless

I asked the nine questions of the three agent CLIs most installed from npm (downloads in the week of 22 November
2026): Codex, 27.6 million; Claude Code, 22.2 million; OpenCode, 3.6 million. Then I ran each with no person
there. The provider is DeepSeek, here and in every later stage, because one key speaks all three API shapes
these CLIs need.

## The file

[headless.sh](headless.sh) is one turn of any of the three:

```sh
./headless.sh codex "Create a file named hello.txt containing the single word hello."
```

All three wrote the file, in 3 to 5 seconds.

## The nine answers

| | Claude Code 2.1.330 | Codex 0.171.0 | OpenCode 1.19.6 |
|---|---|---|---|
| 1 Install | `npm install @anthropic-ai/claude-code` | `npm install @openai/codex` | `npm install opencode-ai` |
| 2 Headless | `claude -p "<prompt>"` | `codex exec "<prompt>"` | `opencode run "<prompt>"` |
| 3 Output | `--output-format stream-json --verbose` | `--json` | `--format json` |
| 4 Provider | Environment: `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL` | Command line: `-c model_providers.<id>={…}`, `-m` | A provider it knows by name in `-m`, or a config in `OPENCODE_CONFIG_CONTENT` |
| 4 APIs | Anthropic | OpenAI Responses | Anthropic, OpenAI Chat |
| 5 Instructions | `--append-system-prompt` | `-c developer_instructions=` | A file named in its config's `instructions` |
| 6 Continue | `--resume <id>`, or `--continue` | `exec resume <id>`, or `--last` | `--session <id>`, or `--continue` |
| 7 Unattended | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` | `--auto` |
| 8 Off the network | `DISABLE_AUTOUPDATER`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | Nothing found in its help or documentation | `autoupdate: false` in its config; its effect was not measured |
| 9 Leaves behind | `~/.claude/`, `~/.claude.json` | `~/.codex/` | `~/.local/share/opencode/` |

And one line of what each printed for the same reply:

```
{"type":"assistant","message":{"content":[{"type":"text","text":"done"}]}}                Claude Code
{"type":"item.completed","item":{"type":"agent_message","text":"done"}}                   Codex
{"type":"text","part":{"type":"text","text":"done"}}                                      OpenCode
```

## What they have in common

Everything that matters. Each one:

- takes a prompt and runs to the end with no person,
- prints one JSON object a line, saying what it did: the commands it ran, the files it wrote, what it said,
- keeps its whole memory of a session in its home folder, and does its work in the folder it is started in,
- can be pointed at any provider that speaks an API it knows.

What differs is only the words: the flags, the variables, the names in the output. Nine answers a harness.

## What only a test showed

- **Claude Code** records its system prompt on a session's first request and sends it again unchanged, so a
  later request's instructions are ignored unless it is run with `--system-prompt-snapshot off`.
- **Codex** takes instructions only when a session begins. On a resumed session new ones are silently dropped:
  its own session file shows nothing was added.
- **OpenCode**'s website documents a configuration (`providers`, `package`, `settings`) that its latest release
  does not accept, and none of the flags of `opencode run`. Its `--help` was right.
- Claude Code and Codex both wait on standard input if it is left open, and Codex reports a changed file without
  saying what changed.

## What it led to

Headless, an agent runs as me, on my machine, with everything I can reach, and it was told to act without
asking. That is fine for one test and for nothing else. The next question was how to run one where it can do no
harm: [3. Sandboxed](../3-sandboxed).
