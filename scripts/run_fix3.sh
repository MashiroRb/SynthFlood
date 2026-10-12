#!/bin/bash
# Wave-1c: double-knockout probe BC + geo seed-2 family sweep + ppr lambda=6.
set -u
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
cd $ROOT/code || exit 1
MODEL=${MODEL:-Qwen/Qwen2.5-7B-Instruct}
PORT=${PORT:-8000}
RES=$ROOT/results
stamp(){ date -u +%FT%TZ; }
archive(){ [ -s "$RES/$1" ] && mv "$RES/$1" "$RES/_prev_$1.$(date +%s)" && echo "archived $1"; }

echo "== wave1c start $(stamp) =="

python3 scripts/make_probe_variants.py
archive p1_probeBC.csv
echo "== A2c probeBC (double knockout) start $(stamp) =="
python3 -m synthflood.probe_p1 --pool $ROOT/data/contamination/pool_probeBC.json \
  --out $RES/p1_probeBC.csv --model $MODEL --port $PORT || echo "FAIL BC"

archive p4b_geo_s2_sweep.csv
echo "== geo seed2 family sweep start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4B_GEO_S2 --n-tasks 40 --eps 0,0.75 \
  --family geo --seed 2 --defense none \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL geo_s2"

archive p4h_ppr_l6.0_sweep.csv
echo "== ppr lambda=6 start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4H_PPR_L6.0 --n-tasks 40 --eps 0.75 \
  --family mix --seed 1 --defense ppr --ppr-lambda 6.0 \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL l6"

echo "== WAVE1C_DONE $(stamp) =="
