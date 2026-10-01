#!/bin/zsh
# Runs one case in a fresh Claude Code session: only this plugin, every MCP off.
# usage: run1.sh <case> <run#>   env: CONN_TEST_CONFIG (default ~/claude-connector-test)
here=${0:A:h}; setopt null_glob
CLAUDE=${CLAUDE_BIN:-$(command -v claude || echo $HOME/.local/bin/claude)}; c=$1; i=$2
prompt=$(grep "^$c	" $here/cases.tsv | cut -f2); [ -z "$prompt" ] && { echo "no case $c"; exit 1; }
cfg=${CONN_TEST_CONFIG:-$HOME/claude-connector-test}; mkdir -p $here/runs
W=$(mktemp -d /tmp/conntest.XXXX); cd $W && CLAUDE_CONFIG_DIR=$cfg ENABLE_CLAUDEAI_MCP_SERVERS=false CDT_FLAGS=--headless \
  $CLAUDE -p "$prompt" --output-format stream-json --verbose --strict-mcp-config \
  --allowedTools "Bash" "Read" "Skill" --max-turns 30 > $here/runs/$c.$i.jsonl 2>$here/runs/$c.$i.err
rm -rf $W
