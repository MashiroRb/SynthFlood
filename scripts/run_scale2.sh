#!/bin/bash
# 3B rerun (correct --model), then restore Qwen2.5-7B on GPU0.
set -u
cd ~/synthflood/code

restart_gpu0 () {  # $1 model, $2 logtag
  pkill -f "entrypoints.openai.api_serve[r]" || true
  sleep 8
  CUDA_VISIBLE_DEVICES=0 nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$1" --port 8000 --gpu-memory-utilization 0.92 \
    --max-model-len 8192 --enforce-eager > ../logs/vllm_$2.log 2>&1 &
  for i in $(seq 1 60); do
    sleep 5
    curl -s http://127.0.0.1:8000/v1/models | grep -q "$1" && break
  done
}

echo "[scale2] serving 3B"
restart_gpu0 "Qwen/Qwen2.5-3B-Instruct" "gpu0_3b2"
python3 -m synthflood.run_sweep --stage P4F_3B --n-tasks 40 \
  --eps 0,0.75 --family mix --seed 1 --defense none \
  --model Qwen/Qwen2.5-3B-Instruct --port 8000 --workers 24 \
  > ../logs/p4f_3b2.log 2>&1

echo "[scale2] restoring 7B"
restart_gpu0 "Qwen/Qwen2.5-7B-Instruct" "gpu0"
bash scripts/sync_push.sh > ../logs/push_scale.log 2>&1
echo "[scale2] done"
