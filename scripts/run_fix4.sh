#!/bin/bash
# Wave-1d: price dose-response for the clone channel (E4).
set -u
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
cd $ROOT/code || exit 1
MODEL=${MODEL:-Qwen/Qwen2.5-7B-Instruct}
PORT=${PORT:-8000}
RES=$ROOT/results
stamp(){ date -u +%FT%TZ; }
archive(){ [ -s "$RES/$1" ] && mv "$RES/$1" "$RES/_prev_$1.$(date +%s)" && echo "archived $1"; }

echo "== wave1d start $(stamp) =="
python3 scripts/make_price_dose.py

for K in 90 80 70; do
  archive p1_price${K}.csv
  echo "== price dose f=0.${K} start $(stamp) =="
  python3 -m synthflood.probe_p1 --pool $ROOT/data/contamination/pool_price${K}.json \
    --out $RES/p1_price${K}.csv --model $MODEL --port $PORT || echo "FAIL price${K}"
done

echo "== WAVE1D_DONE $(stamp) =="
