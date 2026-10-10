#!/bin/bash
# Auto chain: wait for contamination pool, then audit -> P1 -> P2 -> sync.
set -u
cd ~/synthflood/code
POOL=~/synthflood/data/contamination/pool.json

echo "[chain] waiting for $POOL ..."
for i in $(seq 1 720); do
  [ -s "$POOL" ] && break
  sleep 10
done
if [ ! -s "$POOL" ]; then echo "[chain] pool never appeared"; exit 1; fi
echo "[chain] pool found at $(date -u +%FT%TZ)"

python3 -m synthflood.audit_export > ../logs/audit_export.log 2>&1
echo "[chain] audit exported"

echo "[chain] P1 starting at $(date -u +%FT%TZ)"
python3 -m synthflood.probe_p1 --n-tasks 30 --pairs 10 --port 8000 \
  > ../logs/p1_run.log 2>&1
echo "[chain] P1 done"
tail -3 ../logs/p1_run.log

echo "[chain] P2 starting at $(date -u +%FT%TZ)"
python3 -m synthflood.run_sweep --stage P2 --n-tasks 50 \
  --eps 0,0.25,0.75 --family mix --seed 1 --port 8000 --workers 32 \
  > ../logs/p2_run.log 2>&1
echo "[chain] P2 done"
tail -3 ../logs/p2_run.log

bash scripts/sync_push.sh
echo "[chain] ALL DONE $(date -u +%FT%TZ)"
