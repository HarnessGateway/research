# How I arrived at HarnessGateway

I build agents for a living, as a forward deployed engineer: I go to where the work is, take an agent harness CLI
(Claude Code, Codex, OpenCode, whichever fits), and build an agent around it that does a real job for a real team.
Anthropic's [Claude Forward Deployed Engineer path](https://anthropic-partners.skilljar.com/path/claude-fde)
describes largely this kind of work, for one harness. Of its eleven courses, it is courses 6 to 9 specifically:

| | Course | What it teaches |
|---|---|---|
| 6 | Claude Code 101 | The tool you prototype with in the customer's repository |
| 7 | Claude Code in action | Long, hands-off sessions, controlled with permission modes, hooks and verification |
| 8 | Introduction to Model Context Protocol | Connecting the agent to the customer's systems |
| 9 | Introduction to agent skills | Packaging what works so the customer's team can reuse it |

I do that work across every harness, because I am harness agnostic: the right harness is the one that suits the
job, and that changes from job to job and from month to month.

This repository began as an attempt to capture the essence of that work. It became the story of how I arrived at
my platform, because every time I wrote down what I do by hand, the next question was how to stop doing it by
hand. Each stage is one question I asked, the smallest thing that answered it, and the question it left me with.
Each is a folder with one page that explains it and one file that does it. Everything in them was run.

## The story

**[1. Research.](1-research)** *How do I research a harness, so that I can build an agent around any of them?*
Every agent CLI can run with no person, be told its provider, be given instructions and continue a session, each
in its own words. Researching one is finding its words for the same nine things: install it, read its help,
read its documentation, try it. `research.sh`

**[2. Headless.](2-headless)** *Run the top three with no person there. What do they have in common?*
I asked the nine questions of Codex, Claude Code and OpenCode and ran each headless. They have everything that
matters in common: a prompt in, one JSON object a line out, a session kept in the home folder, work done in the
folder they are started in. Only the words differ. `headless.sh`

**[3. Sandboxed.](3-sandboxed)** *How do I run one in a container I throw away?*
One `docker run`: read-only, no privileges, limited, gone when the turn ends. Writing it for three harnesses, I
saw that the command was identical but for two things: how a harness is installed, and how it is run.
`sandbox.sh`

**[4. Sessions.](4-sessions)** *How do I continue the same work whatever harness I run, wherever I run it?*
The container forgot everything. But a harness's memory is its home folder and its work is its working folder,
so a session is two folders, `mind` and `work`. Keep those and one session runs across three harnesses and two
images, each harness remembering its own part. `session.sh`

**[5. Responses.](5-responses)** *How do I put every harness behind one API?*
The two things of stage 3 became two programs, `install` and `run`: a **harness package**. And `run` got one
job, in a schema that already existed: read an OpenAI Responses request, print Responses output. Three harnesses,
one request, one kind of answer. `respond.sh`, and the three [packages](packages)

**[6. Core.](6-core)** *What is the smallest platform that does all of that?*
168 lines. A Responses request comes in, `model` names a harness and a provider, the package runs in the
container on the session's two folders, and a Responses response goes back. Any OpenAI client can drive any
harness, and change harness in the middle of a session. `core.py`

**[7. FDE.](7-fde)** *Can one harness package build every other harness package?*
I had written three packages by hand, the same way each time. The method was stage 1 and the contract was stage
5, both already written down. So I gave those two pages to an agent, as a harness package of its own, and asked
it for a fourth. `build.py`, and the [fde](packages/fde) package

## What it comes to

| What I found | Became |
|---|---|
| How a harness is installed, and how it is run (stage 3) | A harness package: `install` and `run` |
| The container that is thrown away (stage 3) | The sandbox every turn runs in |
| The home folder and the working folder (stage 4) | A session: `mind` and `work` |
| One request and one answer for every harness (stage 5) | The OpenAI Responses API, unmodified |
| `harness/provider/model` (stage 6) | The model line: the one field that says what runs a request |
| The agent that builds packages (stage 7) | HG FDE, which ships with the platform |

## Where it went

[**HarnessGateway**](https://github.com/HarnessGateway/harnessgateway) is the core of stage 6, built to be run
for other people: secrets that never enter the sandbox, a network policy, snapshots of every turn so a session
can be forked and taken back, streaming, environments, usage, a console. It is open source, the self-hosted
community edition, and what my self-hosted enterprise edition is built around.

Nothing in it replaces anything here. A package is still `install` and `run`. A turn is still that container. A
session is still those two folders. The API is still Responses.
