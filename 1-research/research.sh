#!/bin/sh
# research.sh <npm package@version> <binary> [subcommand ...]
#
# Install an agent CLI at a pinned version in a container that is thrown away, and save what it says about
# itself into ./help: its version, its --help, and the --help of each subcommand named.
#
#   ./research.sh @openai/codex@0.171.0 codex exec "exec resume" mcp
set -eu
mkdir -p help && chmod 777 help
docker run --rm --user 10000:10000 -e HOME=/tmp -e NO_COLOR=1 -v "$PWD/help:/help" node:22 sh -c '
  npm install --prefix /tmp/cli --no-audit --no-fund --loglevel=error "$1" >/dev/null 2>&1
  cd /tmp && PATH=/tmp/cli/node_modules/.bin:$PATH && bin=$2 && shift 2
  "$bin" --version > /help/"$bin"-version.txt 2>/dev/null
  "$bin" --help > /help/"$bin".txt 2>&1
  for sub in "$@"; do "$bin" $sub --help > "/help/$bin-$(echo "$sub" | tr " " -).txt" 2>&1; done' sh "$@"
wc -l help/"$2"*.txt
