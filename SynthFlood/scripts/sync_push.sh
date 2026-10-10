#!/bin/bash
# Sync experiment logs + result CSVs into the repo and push to GitHub.
set -e
cd ~/synthflood/code
mkdir -p logs results
rsync -a --exclude 'vllm_gpu*' ~/synthflood/logs/ logs/ 2>/dev/null || cp -r ~/synthflood/logs/* logs/ 2>/dev/null || true
rsync -a ~/synthflood/results/ results/ 2>/dev/null || true
git add -A
git commit -q -m "sync: experiment logs and results $(date -u +%FT%TZ)" || echo "nothing to commit"
git push -q origin master 2>/dev/null || git push -q origin main
echo PUSH_OK
