#!/usr/bin/env bash
# Phase 3 Batch-API driver: submit one chunk, wait until it is collected, repeat.
# The 80% budget guard sees only collected spend, so chunks are never overlapped.
# Usage: study/v3/run_batches.sh <model> <out> [dataset ids...]
set -u
model="$1"; out="$2"; shift 2
py="./.venv/Scripts/python.exe -W ignore -m study.v3.phase3_llm"
datasets=()
[ "$#" -gt 0 ] && datasets=(--datasets "$@")
while true; do
  until $py collect --model "$model" --out "$out" | tee -a "$out/collect-$model.log" | grep -q "open batches: 0"; do sleep 180; done
  result=$($py submit --model "$model" --out "$out" --max-chunks 1 "${datasets[@]}" 2>&1)
  echo "$result" | tee -a "$out/submit-$model.log"
  echo "$result" | grep -q "BudgetStop" && { echo "BUDGET STOP"; exit 3; }
  echo "$result" | grep -q "Traceback" && { echo "ERROR"; exit 2; }
  echo "$result" | grep -q "pending: 0" && { echo "ALL DONE"; exit 0; }
  sleep 60
done
