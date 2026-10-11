#!/bin/bash
# Wave-1 follow-up: A2/A3 probe duels (pools now generated) + PPR lambda 4/8.
# Run after run_fix.sh prints ALL_DONE.
set -u
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
cd $ROOT/code || exit 1
MODEL=${MODEL:-Qwen/Qwen2.5-7B-Instruct}
PORT=${PORT:-8000}
RES=$ROOT/results
stamp(){ date -u +%FT%TZ; }
archive(){ [ -s "$RES/$1" ] && mv "$RES/$1" "$RES/_prev_$1.$(date +%s)" && echo "archived $1"; }

echo "== wave1b start $(stamp) =="

archive p1_probeB.csv
echo "== A2 probeB start $(stamp) =="
python3 -m synthflood.probe_p1 --pool $ROOT/data/contamination/pool_probeB.json \
  --out $RES/p1_probeB.csv --model $MODEL --port $PORT || echo "FAIL A2"

archive p1_probeC.csv
echo "== A3 probeC start $(stamp) =="
python3 -m synthflood.probe_p1 --pool $ROOT/data/contamination/pool_probeC.json \
  --out $RES/p1_probeC.csv --model $MODEL --port $PORT || echo "FAIL A3"

for L in 4.0 8.0; do
  archive p4h_ppr_l${L}_sweep.csv
  echo "== A4b ppr lambda=$L start $(stamp) =="
  python3 -m synthflood.run_sweep --stage P4H_PPR_L${L} --n-tasks 40 --eps 0.75 \
    --family mix --seed 1 --defense ppr --ppr-lambda $L \
    --model $MODEL --port $PORT --workers 32 || echo "FAIL A4b-$L"
done

echo "== WAVE1B_DONE $(stamp) =="
