# How I arrived at HarnessGateway

I build agents for a living, as a forward deployed engineer: I go to where the work is, take an agent harness CLI
(Claude Code, Codex, OpenCode, whichever fits), and build an agent around it that does a real job for a real team.
Anthropic's Claude Forward Deployed Engineer course describes largely this kind of work, for one harness. I do it
across all of them, because I am harness agnostic: the right harness is the one that suits the job, and that
changes from job to job and from month to month.

This repository began as an attempt to capture the essence of that work. It became the story of how I arrived at
my platform, because every time I wrote down what I do by hand, the next question was how to stop doing it by
hand. Each stage below is one question I asked, the smallest thing that answered it, and the question it left
me with.

| Stage | The question |
|---|---|
| 1. Research | How do I research a harness, so that I can build an agent around any of them? |
| 2. Headless | Run the top three with no person there. What do they have in common? |
| 3. Sandboxed | How do I run one in a container I throw away? |
| 4. Sessions | How do I continue the same work whatever harness I run, wherever I run it? |
| 5. Responses | How do I put every harness behind one API? |
| 6. Core | What is the smallest platform that does all of that? |
| 7. FDE | Can one harness package build every other harness package? |

Each stage is a folder with one page that explains it and one file that does it. They are added to this
repository in order, one commit each.
