#!/bin/sh
# respond.sh <harness> '<Responses request>'
#
# One turn of a harness package, by hand. The request goes in as a file, in the OpenAI Responses API's own shape;
# what the agent does comes out as Responses output, one JSON object a line. It is stage 4's docker run with two
# more folders: the request (turn) and the package (harness). Run it again in the same place and the session
# continues.
#
#   export DEEPSEEK_API_KEY=sk-…
#   ./respond.sh codex '{"input": "Create hello.txt containing the word hello.", "instructions": "Be brief."}'
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p mind work turn "harness/$1" && chmod 777 mind work "harness/$1"
cp -RL "$HERE/../packages/$1/." "harness/$1/" && chmod -R a+rwX "harness/$1"
printf '%s' "$2" > turn/request.json && echo null > turn/previous.json
docker run --rm --init --cpus 2 --memory 4g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,exec,size=1g --cap-drop ALL --security-opt no-new-privileges \
  --user 10000:10000 -e HOME=/mind -v "$PWD/mind:/mind" -v "$PWD/work:/work" -w /work \
  -v "$PWD/turn:/turn:ro" -v "$PWD/harness/$1:/harness" -e npm_config_cache=/tmp/npm \
  -e HG_TURN=/turn -e HG_HARNESS=/harness -e HG_STATE="/mind/.harnessgateway/$1" -e HG_MODEL=deepseek-flash \
  -e HG_PROVIDER_KEY="$DEEPSEEK_API_KEY" -e HG_PROVIDER_ANTHROPIC=https://api.deepseek.com/anthropic \
  -e HG_PROVIDER_OPENAI_RESPONSES=https://api.deepseek.com/v1 -e HG_PROVIDER_OPENAI_CHAT=https://api.deepseek.com/v1 \
  "${IMAGE:-node:22}" sh -c '[ -e /harness/.installed ] || { /harness/install >&2 && touch /harness/.installed; }; exec /harness/run'
