#!/bin/bash
# One-shot guaranteed sync: copy fresh results/logs into repo, commit FIRST,
# then rebase, then push with retries. Safe to run repeatedly.
ROOT=${SYNTHFLOOD_ROOT:-/root/synthflood}
LOGF=${SYNC_LOG:-/root/sync_now.log}
cd $ROOT/code || exit 1
{
if [ -f QUEUE.cmd ]; then
  echo "--- executing QUEUE.cmd $(date -u +%FT%TZ)"
  bash QUEUE.cmd >> /root/queue_exec.log 2>&1
  mv QUEUE.cmd QUEUE.done
  echo "--- QUEUE.cmd done $(date -u +%FT%TZ)"
fi
echo "--- sync_now $(date -u +%FT%TZ)"
cp -u $ROOT/results/*.csv results_csv/ 2>/dev/null
cp -ru $ROOT/logs/. logs/ 2>/dev/null
git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "results sync $(date -u +%FT%TZ)" || true
  echo "committed"
fi
ok=0
for i in 1 2 3 4 5; do
  if git pull --rebase -q origin main 2>/dev/null; then
    if git push -q origin main 2>/dev/null; then
      ok=1; echo "PUSH_OK attempt $i"; break
    fi
  else
    git rebase --abort 2>/dev/null
    git rebase -q origin/main 2>/dev/null || true
  fi
  sleep 15
done
[ "$ok" = 1 ] || echo "PUSH_FAILED after retries"
} >> "$LOGF" 2>&1
