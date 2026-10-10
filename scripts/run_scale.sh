#!/bin/bash
# Scale ablation: swap GPU0 model to Qwen2.5-3B then 1.5B, run eps{0,0.75},
# then restore Qwen2.5-7B. Run AFTER P4A/P4E (needs port 8000 free of 7B).
set -u
cd ~/synthflood/code
W=24

swap_model () {  # $1 = model path, $2 = log tag
  pkill -f "api_serv[e]r" || true
  sleep 8
  CUDA_VISIBLE_DEVICES=0 nohup python3 -m vllm.entrypoints.openai.api_server \
    --model "$1" --port 8000 --gpu-memory-utilization 0.92 \
    --max-model-len 8192 --enforce-eager > ../logs/vllm_$2.log 2>&1 &
  for i in $(seq 1 60); do
    sleep 5
    curl -s http://127.0.0.1:8000/v1/models | grep -q '"data"' && break
  done
  curl -s http://127.0.0.1:8000/v1/models | head -c 120; echo
}

echo "[scale] swapping to Qwen2.5-3B"
swap_model "Qwen/Qwen2.5-3B-Instruct" gpu0_3b
python3 -m synthflood.run_sweep --stage P4F_3B --n-tasks 40 \
  --eps 0,0.75 --family mix --seed 1 --defense none --port 8000 \
  --workers $W > ../logs/p4f_3b.log 2>&1

echo "[scale] swapping to Qwen2.5-1.5B"
swap_model "Qwen/Qwen2.5-1.5B-Instruct" gpu0_15b
python3 -m synthflood.run_sweep --stage P4F_15B --n-tasks 40 \
  --eps 0,0.75 --family mix --seed 1 --defense none --port 8000 \
  --workers $W > ../logs/p4f_15b.log 2>&1

echo "[scale] restoring Qwen2.5-7B"
swap_model "Qwen/Qwen2.5-7B-Instruct" gpu0
bash scripts/sync_push.sh
echo "[scale] done"
