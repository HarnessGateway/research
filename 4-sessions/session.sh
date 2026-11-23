#!/bin/sh
# session.sh <cli> "<prompt>"
#
# A turn of a session that is kept. Two folders outlive the container: ./mind, the agent's home, where every
# harness keeps its own memory of the session, and ./work, where the work is. Run it again and that harness
# carries on. Run another harness and it carries on with the same work. Change the image and both still do.
#
#   export DEEPSEEK_API_KEY=sk-…
#   ./session.sh claude-code "Write notes.txt with three facts about pelicans."
#   ./session.sh claude-code "Add a fourth."                    # the same harness: it remembers
#   ./session.sh codex "Check the facts in notes.txt."          # another harness: the same work
#   IMAGE=nikolaik/python-nodejs:python3.13-nodejs22 ./session.sh codex "What did you correct?"
NPM='npm install --prefix /tmp/cli --no-audit --no-fund --loglevel=error'
BIN=/tmp/cli/node_modules/.bin
[ -e "mind/.ran-$1" ] && again=yes || again=           # whether this harness has a session here to continue
case "$1" in
  claude-code)
    INSTALL="$NPM --ignore-scripts @anthropic-ai/claude-code@2.1.330 && node /tmp/cli/node_modules/@anthropic-ai/claude-code/install.cjs"
    RUN="env ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic ANTHROPIC_AUTH_TOKEN=\$DEEPSEEK_API_KEY ANTHROPIC_MODEL=deepseek-flash ANTHROPIC_SMALL_FAST_MODEL=deepseek-flash $BIN/claude -p ${again:+--continue} --dangerously-skip-permissions --output-format stream-json --verbose" ;;
  codex)
    INSTALL="$NPM @openai/codex@0.171.0"
    RUN="$BIN/codex exec ${again:+resume --last} --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -c model_provider=deepseek -c 'model_providers.deepseek={name=\"DeepSeek\",base_url=\"https://api.deepseek.com/v1\",env_key=\"DEEPSEEK_API_KEY\",wire_api=\"responses\"}' -m deepseek-flash" ;;
  opencode)
    INSTALL="$NPM --ignore-scripts opencode-ai@1.19.6 && node /tmp/cli/node_modules/opencode-ai/postinstall.mjs"
    RUN="$BIN/opencode run ${again:+--continue} --format json --auto -m deepseek/deepseek-flash" ;;
  *) echo 'session.sh claude-code | codex | opencode "<prompt>"' >&2; exit 2 ;;
esac
mkdir -p mind work && chmod 777 mind work
docker run --rm --init --cpus 2 --memory 4g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,exec,size=1g --cap-drop ALL --security-opt no-new-privileges \
  --user 10000:10000 -e HOME=/mind -v "$PWD/mind:/mind" -v "$PWD/work:/work" -w /work \
  -e DEEPSEEK_API_KEY -e npm_config_cache=/tmp/npm \
  "${IMAGE:-node:22}" sh -c "$INSTALL >&2 && $RUN \"\$1\" </dev/null && touch /mind/.ran-$1" sh "$2"
