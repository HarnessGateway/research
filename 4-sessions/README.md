# 4. A session that outlives its container

With one harness on my own machine, I run it again and it carries on. I wanted that in a container that is
thrown away, and I wanted more than one harness gives: to continue the same work whichever harness I ran next,
in whatever environment I ran it.

## What a session turned out to be

Stage 2 had already answered it. Every harness keeps its whole memory of a session in its home folder, and does
its work in the folder it is started in. So a session is two folders:

| | | |
|---|---|---|
| `mind` | The agent's home (`$HOME`) | Where each harness keeps its own memory, in a folder of its own: `.claude`, `.codex`, `.local/share/opencode` |
| `work` | Its working directory | What it is working on |

Keep those two, throw everything else away, and nothing is lost. A harness is continued with its own flag for
that (`--continue`, `exec resume --last`), because its session is where it left it.

## The file

[session.sh](session.sh) is stage 3's `docker run` with the second folder, and each harness's flag to continue:

```sh
./session.sh claude-code "Create notes.txt containing the word PELICAN. Remember: the secret number is 7741."
./session.sh claude-code "What is the secret number?"                    # the same harness
./session.sh codex "Read notes.txt, then append the word OSPREY."        # another harness
IMAGE=nikolaik/python-nodejs:python3.13-nodejs22 ./session.sh codex "Which word did I ask you to append?"
./session.sh opencode "Print notes.txt."                                 # a third
./session.sh claude-code "What does notes.txt hold now, and what was the secret number?"
```

That is one session, and it is what I ran. Six turns, three harnesses, two images:

| Turn | Harness | Answered |
|---|---|---|
| 1 | Claude Code | wrote the file |
| 2 | Claude Code | `7741`, from its own memory |
| 3 | Codex | read `PELICAN` from the file Claude Code wrote, and appended `OSPREY` |
| 4 | Codex, on another image | `OSPREY`, from its own memory |
| 5 | OpenCode | printed both lines |
| 6 | Claude Code | both lines, which it had not written, and `7741`, which it had been told four turns before |

## What I noticed

- **A session does not belong to a harness.** Each harness has its own memory in `mind`, side by side, and they
  share `work`. I can change harness in the middle of a job and change back.
- **A session does not belong to an environment.** The two folders are only folders. Mount them into another
  image, or copy them to another machine, and the session is there.
- **A harness is not told what another did.** Codex found the file Claude Code wrote, but not why it was written.
  What one harness said to me is in its own memory only.

## What it led to

I could now run any harness, safely, and carry on. But I was still the one who knew three sets of flags, and
anything that called these agents would have to know them too, and read three kinds of output. I wanted to ask
every harness the same way and be answered the same way: [5. Responses](../5-responses).
