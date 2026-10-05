#!/bin/zsh
# Reliability run for the optional google-workspace plugin, loaded from the LOCAL working tree (no GitHub, no updates).
# usage: ./run-google.sh [-n runs] [-j parallel] [-c max_usd] [case ...]   cases: cases.google.tsv (git-ignored)
here=${0:A:h}; setopt null_glob
n=2; j=2; cap=15
while getopts n:j:c: o; do case $o in n) n=$OPTARG;; j) j=$OPTARG;; c) cap=$OPTARG;; esac; done; shift $((OPTIND-1))
export CONN_CASES=$here/cases.google.tsv CONN_RUNS=$here/runs-google
export CONN_EXTRA_ARGS="--plugin-dir ${here:h}/plugins/google-workspace --settings {\"enabledPlugins\":{\"custom-connectors@custom-connectors\":false}}"
[ -f $CONN_CASES ] || { echo "Create tests/cases.google.tsv first"; exit 1; }
cases=(${@:-$(grep -v '^#' $CONN_CASES | cut -f1)})
rm -rf $CONN_RUNS; mkdir -p $CONN_RUNS
cost() { local f=($CONN_RUNS/*.jsonl); (( ${#f} )) || { echo 0; return; }; cat $f | jq -s '[.[]|select(.type=="result")|.total_cost_usd]|add // 0'; }
for i in $(seq 1 $n); do for c in $cases; do
  (( $(cost) > cap )) && { echo "Stopped: cost cap \$$cap reached"; break 2; }
  $here/run1.sh $c $i & while (( $(jobs -r | wc -l) >= j )); do sleep 2; done
done; done; wait
python3 $here/grade.py $CONN_RUNS
