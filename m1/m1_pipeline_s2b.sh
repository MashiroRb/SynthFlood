#!/bin/bash
# M1 S2b (fixed-instrument replication): exam/parity clone caches byte-copied
# from seed-1; goals seed 2027 (identical instructions/tasks); treatment-side
# randomness shifted to 2029. Isolation: contamination_s2b / results_m1_s2b.
set -e
CODE=/root/synthflood/code
LOGD=/root/synthflood/logs
export M1_SEED_BASE=2029 M1_GOALS_SEED=2027 M1_FIX_INSTRUMENT=1 M1_GEN_SUBDIR=contamination_s2b M1_OUT_SUBDIR=results_m1_s2b
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOGD/m1s2b_console.log; }

if ! mkdir /tmp/m1s2b.lock 2>/dev/null; then say "FATAL: lock held"; exit 1; fi
trap 'rmdir /tmp/m1s2b.lock 2>/dev/null' EXIT
curl -s -m 5 http://localhost:8000/v1/models | grep -q Qwen || { say "FATAL: vLLM not serving"; exit 1; }
[ -s /root/data/items_shuffle.json ] || { say "FATAL: data missing"; exit 1; }
cd $CODE
mkdir -p data/contamination_s2b results_m1_s2b
say "=== M1-S2b pipeline start $(date -u +'%FT%TZ') treatment=2029 instrument=2027-fixed ==="

# instrument: byte-copy seed-1 exam + parity clone caches (prep will reuse)
if [ ! -s data/contamination_s2b/m1_exam_clones.json ]; then
  cp data/contamination/m1_exam_clones.json data/contamination_s2b/
  cp data/contamination/m1_parity_clones.json data/contamination_s2b/
  say "instrument caches copied from seed-1 (byte-identical)"
fi

# prep: regenerates goals(frozen 2027), pool(2029), transfer/rank/xdom(2029)
if [ ! -s data/contamination_s2b/m1_pool.json ]; then
  say "PREP: S2b pools under seed 2029 (exam clones reused)..."
  python3 m1/m1_run.py --mode prep 2>&1 | tee $LOGD/m1s2b_prep.log | grep -E "froze|cached|DONE|WARN|Error|Traceback" || true
fi
for f in goals_m1.json m1_pool.json m1_exam_clones.json m1_parity_clones.json m1_transfer_clones.json m1_rank_clones.json m1_xdom_options.json m1_transfer_plan.json; do
  [ -s "data/contamination_s2b/$f" ] || { say "FATAL: cache $f missing"; touch $LOGD/m1s2b.done; echo "aborted: cache $f missing" >> $LOGD/m1s2b.done; exit 1; }
done
cmp -s data/contamination_s2b/m1_exam_clones.json data/contamination/m1_exam_clones.json || { say "FATAL: exam clones not byte-identical"; touch $LOGD/m1s2b.done; echo "aborted: instrument mismatch" >> $LOGD/m1s2b.done; exit 1; }
say "caches OK (instrument verified byte-identical)"

say "SMOKE..."
rm -f results_m1_s2b/*.csv results_m1_s2b/mem_*.json 2>/dev/null || true
M1_SMOKE=1 python3 m1/m1_run.py --mode smoke 2>&1 | tee $LOGD/m1s2b_smoke.log | grep -E "done|DONE|Error|Traceback|WARN" || true
L=$(wc -l < results_m1_s2b/m1_exams.csv 2>/dev/null || echo 0)
[ "$L" -ge 8 ] || { say "FATAL: smoke rows=$L"; touch $LOGD/m1s2b.done; echo "aborted: smoke rows=$L" >> $LOGD/m1s2b.done; exit 1; }
say "smoke OK ($L exam rows)"

say "FULL: launching S2b full run..."
rm -f results_m1_s2b/*.csv results_m1_s2b/mem_*.json results_m1_s2b/snapshot_*.json results_m1_s2b/m1_reward_autopsy.jsonl
nohup env M1_SEED_BASE=2029 M1_GOALS_SEED=2027 M1_FIX_INSTRUMENT=1 M1_GEN_SUBDIR=contamination_s2b M1_OUT_SUBDIR=results_m1_s2b \
  python3 m1/m1_run.py --mode full > $LOGD/m1s2b_full.log 2>&1 &
echo $! > /tmp/m1s2b_full.pid
say "full run pid $(cat /tmp/m1s2b_full.pid)"
say "PIPELINE-S2B-SETUP-DONE"
