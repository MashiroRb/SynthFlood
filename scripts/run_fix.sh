#!/bin/bash
# Wave-1 GPU experiment queue for the revision round (single RTX 4090).
# Order: A1 sham -> A2 probeB -> A3 probeC -> A5 spoof -> A7 reviewtrust
#        -> A4 PPR lambda -> A6 seed-2 replication.
# Run:   nohup bash scripts/run_fix.sh > /root/fix_wave1.log 2>&1 &
set -u
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
cd $ROOT/code || exit 1
MODEL=${MODEL:-Qwen/Qwen2.5-7B-Instruct}
PORT=${PORT:-8000}
RES=$ROOT/results
mkdir -p $RES
stamp(){ date -u +%FT%TZ; }

archive(){ [ -s "$RES/$1" ] && mv "$RES/$1" "$RES/_prev_$1.$(date +%s)" && echo "archived $1"; }

echo "== queue start $(stamp) =="

# A1: real-swap placebo arm (endpoint eps=0.75 first; extend later if needed)
archive p4g_sham_sweep.csv
echo "== A1 P4G_SHAM start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4G_SHAM --n-tasks 100 --eps 0.75 \
  --family mix --seed 1 --defense none --sham \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL A1"

# A2: probe B (clone price anchored to gold) 30 tasks x 10 duels
[ -s "$ROOT/data/contamination/pool_probeB.json" ] || python3 scripts/make_probe_variants.py
archive p1_probeB.csv
echo "== A2 probeB start $(stamp) =="
python3 -m synthflood.probe_p1 --pool $ROOT/data/contamination/pool_probeB.json \
  --out $RES/p1_probeB.csv --model $MODEL --port $PORT || echo "FAIL A2"

# A3: probe C (clone social proof stripped to gold levels)
archive p1_probeC.csv
echo "== A3 probeC start $(stamp) =="
python3 -m synthflood.probe_p1 --pool $ROOT/data/contamination/pool_probeC.json \
  --out $RES/p1_probeC.csv --model $MODEL --port $PORT || echo "FAIL A3"

# A5: provenance spoofing (25% and 50% fake-verified synthetics)
archive p4i_spoof25_sweep.csv p4i_spoof50_sweep.csv
echo "== A5 spoof25 start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4I_SPOOF25 --n-tasks 40 --eps 0.75 \
  --family mix --seed 1 --defense provenance --spoof 0.25 \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL A5-25"
echo "== A5 spoof50 start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4I_SPOOF50 --n-tasks 40 --eps 0.75 \
  --family mix --seed 1 --defense provenance --spoof 0.50 \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL A5-50"

# A7: naive social-proof re-ranking defense (expected to backfire)
archive p4k_revtrust_sweep.csv
echo "== A7 reviewtrust start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4K_REVTRUST --n-tasks 40 --eps 0,0.75 \
  --family mix --seed 1 --defense reviewtrust \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL A7"

# A4: PPR lambda sweep
for L in 0.5 1.0 2.0; do
  archive p4h_ppr_l${L}_sweep.csv
  echo "== A4 ppr lambda=$L start $(stamp) =="
  python3 -m synthflood.run_sweep --stage P4H_PPR_L${L} --n-tasks 40 --eps 0.75 \
    --family mix --seed 1 --defense ppr --ppr-lambda $L \
    --model $MODEL --port $PORT --workers 32 || echo "FAIL A4-$L"
done

# A6: seed-2 cross-pool replication of provenance + struct defenses
archive p4j_prov_s2_sweep.csv p4j_struct_s2_sweep.csv
echo "== A6 provenance seed2 start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4J_PROV_S2 --n-tasks 40 --eps 0,0.75 \
  --family mix --seed 2 --defense provenance \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL A6-p"
echo "== A6 struct seed2 start $(stamp) =="
python3 -m synthflood.run_sweep --stage P4J_STRUCT_S2 --n-tasks 40 --eps 0,0.75 \
  --family mix --seed 2 --defense detector_struct \
  --model $MODEL --port $PORT --workers 32 || echo "FAIL A6-s"

echo "== ALL_DONE $(stamp) =="
