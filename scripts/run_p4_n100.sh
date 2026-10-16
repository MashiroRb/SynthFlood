#!/bin/bash
# Defense battery completion to N=100 tasks per arm (review commitment).
# New stage names *_N100 -> fresh CSVs; the committed 40-task rows untouched.
# sham is already N=100 (P4G_SHAM) and is not rerun.
set -u
CODE=/root/synthflood/code
LOGD=/root/synthflood/logs
cd $CODE
W=24
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOGD/p4n100_console.log; }
for i in $(seq 1 90); do
  curl -s -m 3 http://localhost:8000/v1/models | grep -q Qwen && break
  sleep 10
done
curl -s -m 3 http://localhost:8000/v1/models | grep -q Qwen || { say "FATAL: vLLM not up"; exit 1; }

run() { say "RUN $*"; python3 -m synthflood.run_sweep "$@" >> $LOGD/p4n100.log 2>&1 || say "FAIL: $*"; }

# --- s2-pool replication arms (seed 2), eps {0, 0.75} ---
run --stage P4J_PROV_S2_N100   --n-tasks 100 --eps 0,0.75 --family mix --seed 2 --defense provenance      --port 8000 --workers $W
run --stage P4J_STRUCT_S2_N100 --n-tasks 100 --eps 0,0.75 --family mix --seed 2 --defense detector_struct --port 8000 --workers $W

# --- provenance-prior re-ranking lambda sweep (seed 1, eps 0.75) ---
for L in 0.5 1.0 2.0; do
  run --stage P4H_PPR_L${L}_N100 --n-tasks 100 --eps 0.75 --family mix --seed 1 \
      --defense ppr --ppr-lambda $L --port 8000 --workers $W
done

# --- badge-forgery tolerance (seed 1, eps 0.75) ---
run --stage P4I_SPOOF25_N100 --n-tasks 100 --eps 0.75 --family mix --seed 1 \
    --defense provenance --spoof 0.25 --port 8000 --workers $W
run --stage P4I_SPOOF50_N100 --n-tasks 100 --eps 0.75 --family mix --seed 1 \
    --defense provenance --spoof 0.50 --port 8000 --workers $W

# --- popularity/review-trust + text + oracle + random baselines (seed 1) ---
run --stage P4K_REVTRUST_N100 --n-tasks 100 --eps 0,0.75 --family mix --seed 1 --defense reviewtrust    --port 8000 --workers $W
run --stage P4C_TEXT_N100     --n-tasks 100 --eps 0,0.75 --family mix --seed 1 --defense detector_text  --port 8000 --workers $W
run --stage P4C_ORACLE_N100   --n-tasks 100 --eps 0,0.75 --family mix --seed 1 --defense oracle         --port 8000 --workers $W
run --stage P4C_RANDOM_N100   --n-tasks 100 --eps 0,0.75 --family mix --seed 1 --defense random         --port 8000 --workers $W

touch $LOGD/p4n100.done
say "P4-N100 ALL DONE"
