#!/usr/bin/env bash
# Phase 3 TEST-evaluation worker: repeatedly evaluates every curated unit not yet done,
# claiming each unit with a lock (u3_eval._claim), so any number of workers can run.
# Usage: study/v3/eval_worker.sh primary|rest
# primary = the success family (merged, no-oversampling, u2); rest = every other method.
# Datasets listed in runs/phase3/eval-legacy-datasets.txt are covered by earlier lock-free
# processes and are skipped here.
set -u
stage="$1"
sha=a65e20f96d093c9f8f18190027429a0f78c02fbf58f08d88d3d5d7dd58f8cb30
py=study/v3/vendor/.venv-u2/Scripts/python.exe
runs=study/v3/runs/phase3
case "$stage" in
  primary) sel=(--methods merged no-oversampling u2) ;;
  rest) sel=(--exclude-methods merged no-oversampling u2) ;;
  *) echo "stage must be primary or rest"; exit 2 ;;
esac
while true; do
  mapfile -t ds < <(ls "$runs/curated/units" | grep '\.json$' | sed 's/__s.*//' | sort -u \
                    | grep -vxF -f "$runs/eval-legacy-datasets.txt")
  if [ "${#ds[@]}" -gt 0 ]; then
    "$py" -I study/v3/u3_eval.py --units "$runs/curated" --out "$runs/eval-$stage" \
      --expected-protocol-sha256 "$sha" "${sel[@]}" --only "${ds[@]}" 2>&1 \
      | grep -vE "Warning|warn\(|optimize.minimize|^\s*$|booster|device ordinal|inplace_predict|return func"
  fi
  done_n=$(ls "$runs/eval-$stage/units" 2>/dev/null | grep -c '\.json$')
  [ "$done_n" -ge 200 ] && { echo "ALL DONE $stage"; exit 0; }
  sleep 300
done
