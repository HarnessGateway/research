#!/bin/sh
# sandbox.sh <cli> "<prompt>"
#
# The same turn in a container that is thrown away. The agent sees one folder of this machine, ./work, and
# nothing else of it. Only two things differ from one CLI to the next: how it is installed, and how it is run.
#
#   export DEEPSEEK_API_KEY=sk-…
#   ./sandbox.sh codex "Create a file named hello.txt containing the single word hello."
#   IMAGE=nikolaik/python-nodejs:python3.13-nodejs22 ./sandbox.sh codex "…"        # any image with Node.js
NPM='npm install --prefix /tmp/cli --no-audit --no-fund --loglevel=error'
BIN=/tmp/cli/node_modules/.bin
case "$1" in
  claude-code)
    INSTALL="$NPM --ignore-scripts @anthropic-ai/claude-code@2.1.330 && node /tmp/cli/node_modules/@anthropic-ai/claude-code/install.cjs"
    RUN="env ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic ANTHROPIC_AUTH_TOKEN=\$DEEPSEEK_API_KEY ANTHROPIC_MODEL=deepseek-flash ANTHROPIC_SMALL_FAST_MODEL=deepseek-flash $BIN/claude -p --dangerously-skip-permissions --output-format stream-json --verbose" ;;
  codex)
    INSTALL="$NPM @openai/codex@0.171.0"
    RUN="$BIN/codex exec --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -c model_provider=deepseek -c 'model_providers.deepseek={name=\"DeepSeek\",base_url=\"https://api.deepseek.com/v1\",env_key=\"DEEPSEEK_API_KEY\",wire_api=\"responses\"}' -m deepseek-flash" ;;
  opencode)
    INSTALL="$NPM --ignore-scripts opencode-ai@1.19.6 && node /tmp/cli/node_modules/opencode-ai/postinstall.mjs"
    RUN="$BIN/opencode run --format json --auto -m deepseek/deepseek-flash" ;;
  *) echo 'sandbox.sh claude-code | codex | opencode "<prompt>"' >&2; exit 2 ;;
esac
mkdir -p work && chmod 777 work
docker run --rm --init --cpus 2 --memory 4g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,exec,size=1g --cap-drop ALL --security-opt no-new-privileges \
  --user 10000:10000 -e HOME=/tmp -v "$PWD/work:/work" -w /work -e DEEPSEEK_API_KEY \
  "${IMAGE:-node:22}" sh -c "$INSTALL >&2 && exec $RUN \"\$1\" </dev/null" sh "$2"
