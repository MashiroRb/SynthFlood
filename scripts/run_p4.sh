#!/bin/bash
# P4 compressed main matrix (pre-registered after P2 gate).
# All runs on Qwen2.5-7B :8000 unless noted. Appends to per-stage CSVs.
set -u
cd ~/synthflood/code
W=32

echo "[P4] main dose-response curve: mix x eps{0,0.1,0.25,0.5,0.75} x 100 tasks"
python3 -m synthflood.run_sweep --stage P4A --n-tasks 100 \
  --eps 0,0.1,0.25,0.5,0.75 --family mix --seed 1 --defense none \
  --port 8000 --workers $W > ../logs/p4a.log 2>&1

echo "[P4] per-family attribution at eps=0.75 (+0 baseline pairs)"
for FAM in geo clone reviews; do
  python3 -m synthflood.run_sweep --stage P4B_$FAM --n-tasks 40 \
    --eps 0,0.75 --family $FAM --seed 1 --defense none \
    --port 8000 --workers $W > ../logs/p4b_$FAM.log 2>&1
done

echo "[P4] defense battery at eps=0.75 mix, 40 tasks"
for DEF in prompt detector_text detector_struct random provenance oracle; do
  python3 -m synthflood.run_sweep --stage P4C_$DEF --n-tasks 40 \
    --eps 0,0.75 --family mix --seed 1 --defense $DEF \
    --port 8000 --workers $W > ../logs/p4c_$DEF.log 2>&1
done

echo "[P4] backbone generality: Llama-3.1-8B on :8001"
python3 -m synthflood.run_sweep --stage P4D_llama --n-tasks 40 \
  --eps 0,0.25,0.75 --family mix --seed 1 --defense none \
  --model NousResearch/Meta-Llama-3.1-8B-Instruct --port 8001 \
  --workers $W > ../logs/p4d.log 2>&1

echo "[P4] done; syncing"
bash scripts/sync_push.sh
