#!/usr/bin/env bash
# Phase 3 curation worker: repeatedly curates every unit whose U2-side generation is complete
# for all 5 split seeds of its dataset, claiming units (claims.py) so workers never overlap.
# Usage: study/v3/curate_worker.sh forward|reverse  (order only; results are identical)
set -u
order="$1"
runs=study/v3/runs/phase3
py=./.venv/Scripts/python.exe
while true; do
  mapfile -t ds < <("$py" - "$order" <<'PY'
import json, os, sys
jobs = json.load(open("study/v3/runs/phase3/u2/jobs.json", encoding="utf-8"))
names = list(dict.fromkeys(j["dataset_id"] for j in jobs))
ready = [d for d in names if all(os.path.exists(f"study/v3/runs/phase3/u2/units/{d}__s{s}.json")
                                 for s in (13, 29, 43, 61, 79))]
print("\n".join(reversed(ready) if sys.argv[1] == "reverse" else ready))
PY
)
  if [ "${#ds[@]}" -gt 0 ]; then
    "$py" -W ignore -m study.v3.phase3 curate --u2 "$runs/u2" --llm "$runs/llm" \
      --generators claude-haiku-5-5 gpt-6-luna muse-spark-1.3 --out "$runs/curated" \
      --datasets "${ds[@]}"
  fi
  n=$(ls "$runs/curated/units" | grep -c '\.json$')
  [ "$n" -ge 200 ] && { echo "ALL DONE curation"; exit 0; }
  sleep 300
done
