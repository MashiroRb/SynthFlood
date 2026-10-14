#!/bin/bash
# M1 finalize: analyze -> log -> commit -> push -> verify (three-way sync).
set -e
cd /root/synthflood_repo
LOG="m1/M1_EXPERIMENT_LOG.md"
STAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

echo "[$(date -u +%H:%M:%S)] === M1 finalize start ==="
if [ ! -s results_m1/m1_exams.csv ]; then echo "FATAL: no exam data"; exit 1; fi

python3 m1/m1_run.py --mode analyze 2>&1 | tee /tmp/m1_analyze.log

# append run summary to the log
{
  echo ""
  echo "## 实验执行 ($STAMP)"
  echo ""
  echo "- prep/smoke/full 均由 m1_pipeline.sh + m1_finalize.sh 驱动。"
  echo "- full 运行控制台日志：/tmp/m1_full.log（运行期），关键数字入 results_m1/。"
  echo ""
  echo "### 分析输出（m1_run.py --mode analyze）"
  echo ""
  echo '```'
  grep -v "^\[" /tmp/m1_analyze.log | head -80
  echo '```'
  echo ""
  echo "### 数据完整性"
  echo ""
  echo '```'
  wc -l results_m1/*.csv 2>/dev/null || true
  wc -l results_m1/m1_reward_autopsy.jsonl 2>/dev/null || true
  echo '```'
} >> "$LOG"

git add -A m1 results_m1 data/contamination/m1_*.json data/contamination/goals_m1.json
git add -A synthflood/agent_react.py scripts 2>/dev/null || git add -A synthflood/agent_react.py
git commit -q -m "M1: internalization washout+transfer experiment (code, pre-reg, caches, results, log)" || true
git pull --rebase origin main || true
git push origin main 2>&1 | tail -1
REV=$(git rev-parse --short HEAD)
echo "PUSHED $REV"

# verify: remote contains the artifacts
git fetch -q origin main
git ls-tree -r --name-only origin/main | grep -q results_m1/m1_summary.json && echo "VERIFY: summary on remote OK"
git ls-tree -r --name-only origin/main | grep -q "m1/M1_EXPERIMENT_LOG.md" && echo "VERIFY: log on remote OK"
git ls-tree -r --name-only origin/main | grep -q "m1/PRE_REG_M1.md" && echo "VERIFY: pre-reg on remote OK"
echo "FINALIZE-DONE rev=$REV"
