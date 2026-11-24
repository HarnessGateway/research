#!/usr/bin/env python3
"""agent.py: one chat console, with any of the three harnesses behind the agent. Pick one for each message.

    python3 agent.py                    # on this machine
    python3 agent.py --sandbox          # every turn in a container that is thrown away
"""
import console

console.serve([console.load(name) for name in ("claude-code", "codex", "opencode")])
