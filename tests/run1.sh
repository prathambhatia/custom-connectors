#!/bin/zsh
# Runs one case in a fresh Claude Code session: only this plugin, every MCP off.
# usage: run1.sh <case> <run#>   env: CONN_TEST_CONFIG (default ~/claude-connector-test), CONN_CASES, CONN_RUNS, CONN_EXTRA_ARGS
here=${0:A:h}; setopt null_glob
CLAUDE=${CLAUDE_BIN:-$(command -v claude || echo $HOME/.local/bin/claude)}; c=$1; i=$2
CASES=${CONN_CASES:-$here/cases.tsv}; RUNS=${CONN_RUNS:-$here/runs}
prompt=$(grep "^$c	" $CASES | cut -f2); [ -z "$prompt" ] && { echo "no case $c"; exit 1; }
cfg=${CONN_TEST_CONFIG:-$HOME/claude-connector-test}; mkdir -p $RUNS
W=$(mktemp -d /tmp/conntest.XXXX); cd $W && CLAUDE_CONFIG_DIR=$cfg ENABLE_CLAUDEAI_MCP_SERVERS=false CDT_FLAGS=--headless \
  $CLAUDE -p "$prompt" --output-format stream-json --verbose --strict-mcp-config ${=CONN_EXTRA_ARGS} \
  --allowedTools "Bash" "Read" "Skill" --max-turns 30 > $RUNS/$c.$i.jsonl 2>$RUNS/$c.$i.err
rm -rf $W
