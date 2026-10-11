#!/bin/bash
# Auto-sync daemon: every 10 min, copy fresh results/logs into the repo and
# push to GitHub. Safe against concurrent pushes (pull --rebase first).
# Run: nohup bash scripts/sync_daemon.sh > /dev/null 2>&1 &
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
LOGF=/root/sync_daemon.log
cd $ROOT/code || exit 1
echo "daemon started $(date -u +%FT%TZ)" >> $LOGF
while true; do
  sleep 600
  {
    echo "--- cycle $(date -u +%FT%TZ)"
    git pull --rebase origin main 2>&1 | tail -1
    cp -u $ROOT/results/*.csv results_csv/ 2>/dev/null
    cp -ru $ROOT/logs/. logs/ 2>/dev/null
    cp -u $ROOT/EXPERIMENT_PLAN_V2.md . 2>/dev/null
    git add -A results_csv logs EXPERIMENT_LOG.md EXPERIMENT_PLAN_V2.md 2>/dev/null
    if ! git diff --cached --quiet; then
      git commit -m "auto-sync $(date -u +%FT%TZ)" 2>&1 | tail -1
      git push origin main 2>&1 | tail -1 || {
        echo "push failed; retry after rebase"
        git pull --rebase origin main 2>&1 | tail -1
        git push origin main 2>&1 | tail -1
      }
    fi
  } >> $LOGF 2>&1
done
