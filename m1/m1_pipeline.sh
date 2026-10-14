#!/bin/bash
# M1 pipeline: env check -> pair mining -> prep -> smoke -> full -> analyze
# -> log -> commit -> push -> verify (results + code + log to GitHub).
# Log lives in three places: lab (~/synthflood_repo/m1/M1_EXPERIMENT_LOG.md),
# remote (GitHub main), local (repo_clone pull + project copy).
set -e
cd /root/synthflood_repo
LOG="m1/M1_EXPERIMENT_LOG.md"
STAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a /tmp/m1_console.log; }

# ---- 0. environment checks ----
say "=== M1 pipeline start $STAMP ==="
if ! mkdir /tmp/m1_pipeline.lock 2>/dev/null; then say "FATAL: another pipeline instance holds /tmp/m1_pipeline.lock"; exit 1; fi
trap 'rmdir /tmp/m1_pipeline.lock 2>/dev/null' EXIT
curl -s -m 5 http://localhost:8000/v1/models | grep -q Qwen || { say "FATAL: vLLM not serving"; exit 1; }
python3 -c "import sys; sys.path.insert(0,'/root/synthflood'); sys.path.insert(0,'/root/webshop_repo'); from synthflood.ws_loader import load_official_data" || { say "FATAL: harness import failed"; exit 1; }
[ -s /root/data/items_shuffle.json ] || { say "FATAL: data missing"; exit 1; }
say "env OK (vllm, harness, data)"

# ---- 1. pair pool (deterministic re-mine if missing) ----
mkdir -p /root/realattack
if [ ! -s /root/realattack/realattack_pairs.json ]; then
  say "mining real-clone pairs from full catalog (deterministic)..."
  python3 results_realattack/mine_full_pairs.py 2>&1 | tee /tmp/mine.log | tail -3
fi
python3 -c "import json; p=json.load(open('/root/realattack/realattack_pairs.json')); assert len(p)>=460, len(p); print('pairs:', len(p))" || { say "FATAL: pair pool bad"; exit 1; }
say "pair pool OK"

# ---- 2. prep: freeze goals + build caches (committed for reproducibility) ----
if [ ! -s data/contamination/m1_pool.json ]; then
  say "PREP: generating exposure pool + exam/parity/transfer/rank/xdom caches (~20-30 min)..."
  python3 m1/m1_run.py --mode prep 2>&1 | tee /tmp/m1_prep.log | grep -E "froze|cached|DONE|WARN|Error|Traceback" || true
else
  say "PREP caches already present, skipping"
fi
for f in goals_m1.json m1_pool.json m1_exam_clones.json m1_parity_clones.json m1_transfer_clones.json m1_rank_clones.json m1_xdom_options.json m1_transfer_plan.json; do
  [ -s "data/contamination/$f" ] || { say "FATAL: cache $f missing"; exit 1; }
done
say "caches OK"

# ---- 3. smoke ----
if [ "${M1_SKIP_SMOKE:-0}" != "1" ]; then
  say "SMOKE: truncated M0 plumb check..."
  rm -f results_m1/*.csv results_m1/mem_*.json
  M1_SMOKE=1 python3 m1/m1_run.py --mode smoke 2>&1 | tee /tmp/m1_smoke.log | grep -E "done|DONE|Error|Traceback|WARN" || true
  LINES=$(wc -l < results_m1/m1_exams.csv 2>/dev/null || echo 0)
  [ "$LINES" -ge 8 ] || { say "FATAL: smoke produced $LINES exam rows"; exit 1; }
  say "smoke OK ($LINES exam rows)"
fi

# ---- 4. full run ----
say "FULL: launching pre-registered run (this takes hours)..."
rm -f results_m1/*.csv results_m1/mem_*.json results_m1/snapshot_*.json results_m1/m1_reward_autopsy.jsonl
nohup python3 m1/m1_run.py --mode full > /tmp/m1_full.log 2>&1 &
echo $! > /tmp/m1_full.pid
say "full run pid $(cat /tmp/m1_full.pid); monitor: tail -f /tmp/m1_full.log"
say "PIPELINE-SETUP-DONE (full run running in background)"
