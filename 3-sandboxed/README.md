# 3. In a container that is thrown away

An agent told to act without asking should not be doing it as me, on my machine. So the same turn, in a
container: started for one prompt, given one folder, and gone when the turn ends.

## The file

[sandbox.sh](sandbox.sh) is one `docker run`:

```sh
./sandbox.sh claude-code "Create a file named hello.txt containing the single word hello."
./sandbox.sh codex       "Create a file named hello.txt containing the single word hello."
IMAGE=nikolaik/python-nodejs:python3.13-nodejs22 ./sandbox.sh opencode "…"
```

```sh
docker run --rm --init --cpus 2 --memory 4g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,exec,size=1g --cap-drop ALL --security-opt no-new-privileges \
  --user 10000:10000 -e HOME=/tmp -v "$PWD/work:/work" -w /work -e DEEPSEEK_API_KEY \
  node:22 sh -c "<install> && <run> <prompt>"
```

All three wrote the file, in 15 to 20 seconds, and OpenCode did the same on a second image. Most of that time is
the install, done again every run.

## What the container is

Everything in that command but the last line is the same for every harness, and none of it is optional:

| | |
|---|---|
| `--rm`, `--init` | It is gone when the turn ends, and so is everything the agent started |
| `--read-only`, `--tmpfs /tmp` | It cannot change the image it runs in. What it writes outside its folder is in memory, and gone too |
| `--cap-drop ALL`, `no-new-privileges`, `--user 10000:10000` | It is not root, and cannot become root |
| `--cpus`, `--memory`, `--pids-limit` | It cannot take the machine |
| `-v "$PWD/work:/work" -w /work` | The one folder of this machine it sees: where its work is |

## What I noticed

Writing the three commands side by side, the `docker run` was identical. Only two things changed from one
harness to the next: **how it is installed** and **how it is run**. In the file they are two variables,
`INSTALL` and `RUN`, and a harness is one `case` that sets them. Swapping harnesses became swapping one word.

Those two things are the whole of what I have to know about a harness to run it. Everything else is the
container's.

## What it led to

The container forgets. I ran Claude Code a second time in the same folder and asked what it had just done. It
answered `UNKNOWN`: the file was there, and it had no idea it had written it. Its memory of the session had been
in its home folder, and its home had been thrown away with the container.

A single harness on my own machine does not have this problem: I run it again and it carries on. I wanted that
back, and more: to carry on with whichever harness I ran next, in whatever environment I ran it:
[4. Sessions](../4-sessions).
