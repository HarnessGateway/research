#!/bin/sh
# headless.sh <cli> "<prompt>"
#
# One turn of an agent CLI with no person there: the prompt in, the work done in this folder, and what it did
# printed as lines a program can read. Each CLI must be installed, and the provider's key exported:
#
#   npm install -g @anthropic-ai/claude-code@2.1.330 @openai/codex@0.171.0 opencode-ai@1.19.6
#   export DEEPSEEK_API_KEY=sk-…
#   ./headless.sh codex "Create a file named hello.txt containing the single word hello."
case "$1" in
  claude-code)
    ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic ANTHROPIC_AUTH_TOKEN=$DEEPSEEK_API_KEY \
    ANTHROPIC_MODEL=deepseek-flash ANTHROPIC_SMALL_FAST_MODEL=deepseek-flash \
      claude -p --dangerously-skip-permissions --output-format stream-json --verbose "$2" </dev/null ;;
  codex)
    codex exec --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
      -c model_provider=deepseek \
      -c 'model_providers.deepseek={name="DeepSeek",base_url="https://api.deepseek.com/v1",env_key="DEEPSEEK_API_KEY",wire_api="responses"}' \
      -m deepseek-flash "$2" </dev/null ;;
  opencode)
    opencode run --format json --auto -m deepseek/deepseek-flash "$2" </dev/null ;;
  *) echo 'headless.sh claude-code | codex | opencode "<prompt>"' >&2; exit 2 ;;
esac
