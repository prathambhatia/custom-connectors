#!/bin/zsh
# Runs every case (or the ones named) N times, then scores them.
# usage: ./run.sh [-n runs] [-j parallel] [-c max_usd] [case ...]
here=${0:A:h}; setopt null_glob
CLAUDE=${CLAUDE_BIN:-$(command -v claude || echo $HOME/.local/bin/claude)}; n=2; j=2; cap=25
while getopts n:j:c: o; do case $o in n) n=$OPTARG;; j) j=$OPTARG;; c) cap=$OPTARG;; esac; done; shift $((OPTIND-1))
[ -f $here/cases.tsv ] || { echo "Create tests/cases.tsv first (see cases.example.tsv)"; exit 1; }
cases=(${@:-$(grep -v '^#' $here/cases.tsv | cut -f1)})
rm -rf $here/runs; mkdir -p $here/runs
cost() { local f=($here/runs/*.jsonl); (( ${#f} )) || { echo 0; return; }; cat $f | jq -s '[.[]|select(.type=="result")|.total_cost_usd]|add // 0'; }
CLAUDE_CONFIG_DIR=${CONN_TEST_CONFIG:-$HOME/claude-connector-test} $CLAUDE plugin marketplace update custom-connectors >/dev/null 2>&1
CLAUDE_CONFIG_DIR=${CONN_TEST_CONFIG:-$HOME/claude-connector-test} $CLAUDE plugin update custom-connectors@custom-connectors 2>&1 | tail -1
for i in $(seq 1 $n); do for c in $cases; do
  (( $(cost) > cap )) && { echo "Stopped: cost cap \$$cap reached"; break 2; }
  # chrome cases share one browser, so never run two at once
  if [[ $c == chrome* ]]; then wait; $here/run1.sh $c $i; lsof -ti tcp:4330 | xargs kill 2>/dev/null
  else $here/run1.sh $c $i & while (( $(jobs -r | wc -l) >= j )); do sleep 2; done; fi
done; done; wait
python3 $here/grade.py $here/runs
