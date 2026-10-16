#!/bin/bash
# M1 seed-2 (S2) pipeline: env check -> prep -> smoke -> full -> done marker.
# Isolation: M1_GEN_SUBDIR=contamination_s2, M1_OUT_SUBDIR=results_m1_s2.
# Never touches seed-1 artifacts (results_m1/, data/contamination/).
set -e
CODE=/root/synthflood/code
LOGD=/root/synthflood/logs
export M1_SEED_BASE=2028 M1_GEN_SUBDIR=contamination_s2 M1_OUT_SUBDIR=results_m1_s2
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOGD/m1s2_console.log; }

if ! mkdir /tmp/m1s2.lock 2>/dev/null; then say "FATAL: lock held"; exit 1; fi
trap 'rmdir /tmp/m1s2.lock 2>/dev/null' EXIT
curl -s -m 5 http://localhost:8000/v1/models | grep -q Qwen || { say "FATAL: vLLM not serving"; exit 1; }
[ -s /root/data/items_shuffle.json ] || { say "FATAL: data missing"; exit 1; }
cd $CODE
say "=== M1-S2 pipeline start $(date -u +'%FT%TZ') seed=2028 ==="

# ---- 0. pair pool (shared, deterministic; same file as seed-1) ----
mkdir -p /root/realattack
if [ ! -s /root/realattack/realattack_pairs.json ]; then
  say "mining real-clone pairs from full catalog (deterministic)..."
  python3 results_realattack/mine_full_pairs.py 2>&1 | tee $LOGD/m1s2_mine.log | tail -3
fi
python3 -c "import json; p=json.load(open('/root/realattack/realattack_pairs.json')); assert len(p)>=460, len(p); print('pairs:', len(p))" || { say "FATAL: pair pool bad"; exit 1; }

# ---- 1. prep: regenerate caches under seed 2028 (~20-30 min) ----
if [ ! -s data/contamination_s2/m1_exam_clones.json ]; then
  say "PREP: generating S2 pools + exam/parity/transfer/rank/xdom caches..."
  python3 m1/m1_run.py --mode prep 2>&1 | tee $LOGD/m1s2_prep.log | grep -E "froze|cached|DONE|WARN|Error|Traceback" || true
else
  say "PREP caches already present, skipping"
fi
for f in goals_m1.json m1_pool.json m1_exam_clones.json m1_parity_clones.json m1_transfer_clones.json m1_rank_clones.json m1_xdom_options.json m1_transfer_plan.json; do
  [ -s "data/contamination_s2/$f" ] || { say "FATAL: cache $f missing"; exit 1; }
done
say "caches OK"

# ---- 2. smoke ----
say "SMOKE: truncated M0 plumb check..."
rm -f results_m1_s2/*.csv results_m1_s2/mem_*.json 2>/dev/null || true
M1_SMOKE=1 python3 m1/m1_run.py --mode smoke 2>&1 | tee $LOGD/m1s2_smoke.log | grep -E "done|DONE|Error|Traceback|WARN" || true
L=$(wc -l < results_m1_s2/m1_exams.csv 2>/dev/null || echo 0)
[ "$L" -ge 8 ] || { say "FATAL: smoke produced $L exam rows"; touch $LOGD/m1s2.done; echo "aborted: smoke rows=$L" >> $LOGD/m1s2.done; exit 1; }
say "smoke OK ($L exam rows)"

# ---- 3. full run (background) ----
say "FULL: launching seed-2028 full run (hours)..."
rm -f results_m1_s2/*.csv results_m1_s2/mem_*.json results_m1_s2/snapshot_*.json results_m1_s2/m1_reward_autopsy.jsonl
nohup env M1_SEED_BASE=2028 M1_GEN_SUBDIR=contamination_s2 M1_OUT_SUBDIR=results_m1_s2 \
  python3 m1/m1_run.py --mode full > $LOGD/m1s2_full.log 2>&1 &
echo $! > /tmp/m1s2_full.pid
say "full run pid $(cat /tmp/m1s2_full.pid); monitor: tail -f $LOGD/m1s2_full.log"
say "PIPELINE-S2-SETUP-DONE (full running in background)"
