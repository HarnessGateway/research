#!/usr/bin/env python3
"""build.py <name> "<which agent CLI>"

Ask HG FDE, through the core, to build a harness package, and bring what it wrote into ../packages/<name>. The
core must be running (python3 ../6-core/core.py), with the provider's key in its environment.

    ./build.py pi "the Pi coding agent CLI, the npm package @earendil-works/pi-coding-agent"
"""
import json
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
name, cli = sys.argv[1], sys.argv[2]
request = {"model": "fde/deepseek/deepseek-flash", "input": f"Build a harness package named {name} for {cli}."}
asked = urllib.request.Request("http://127.0.0.1:8600/v1/responses", json.dumps(request).encode(),
                               {"Content-Type": "application/json"})
with urllib.request.urlopen(asked, timeout=3600) as answer:  # noqa: S310  a build is one long turn
    response = json.load(answer)
said = [part["text"] for item in response["output"] if item["type"] == "message" for part in item["content"]]
print(f"{response['status']}: {said[-1] if said else response['error']}")
built = HERE.parent / "6-core" / "data" / "sessions" / response["metadata"]["hg_session"] / "work" / name
if not (built / "run").is_file():
    sys.exit(f"HG FDE left no package in /work/{name}")
shutil.copytree(built, HERE.parent / "packages" / name, dirs_exist_ok=True)
print(f"packages/{name}: {', '.join(sorted(path.name for path in built.iterdir()))}")
