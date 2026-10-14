#!/bin/bash
# 自动推送：论文+结果 -> GitHub；用法: ./push_auto.sh "提交说明"
set -e
ROOT=/tmp/work/prj_01M4HVRPHEDVD2DBGC9EN30RKN
cd "$ROOT/repo_clone"
rsync -a --delete "$ROOT/初稿/" paper/ \
  --exclude main.pdf --exclude "*.aux" --exclude "*.log" --exclude "*.fls" \
  --exclude "*.fdb_latexmk" --exclude "*.out" --exclude "*.synctex.gz"
mkdir -p results_realattack
[ -d "$ROOT/realattack_results" ] && rsync -a "$ROOT/realattack_results/" results_realattack/
cp -f "$ROOT/realdata/real_stats.json" results_realattack/ 2>/dev/null || true
cp -f "$ROOT/REAL_ATTACK_VALIDATION_PLAN.md" results_realattack/ 2>/dev/null || true
git add -A
if ! git diff --cached --quiet; then git commit -q -m "${1:-auto: sync $(date -u +%FT%TZ)}"; fi
PAT=$(cat "$ROOT/PAT")
OK=""
for i in 1 2 3; do
  if git push -q https://MashiroRb:$PAT@github.com/MashiroRb/SynthFlood.git main 2>/dev/null; then OK=1; break; fi
  echo "push retry $i" >&2; sleep 8
done
[ -n "$OK" ] || { echo "PUSH FAILED after retries" >&2; exit 1; }
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git ls-remote https://MashiroRb:$PAT@github.com/MashiroRb/SynthFlood.git main | cut -f1)
if [ "$LOCAL" = "$REMOTE" ]; then echo "PUSH-VERIFIED $LOCAL $(date -u +%FT%TZ)" >> push_log.txt; echo "OK $LOCAL"; else echo "MISMATCH local=$LOCAL remote=$REMOTE" >&2; exit 1; fi
