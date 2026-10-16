#!/bin/bash
# Relink legacy paths (scripts hardcode /root/synthflood_repo etc.) and start
# the single-GPU vLLM server (Qwen2.5-7B-Instruct on :8000).
set -e
ln -sfn /root/synthflood/code /root/synthflood_repo
ln -sfn /root/synthflood/webshop_repo /root/webshop_repo
ln -sfn /root/synthflood/data /root/data
mkdir -p /root/realattack /root/synthflood/logs
export HF_HUB_OFFLINE=1
if ! curl -s -m 3 http://localhost:8000/v1/models | grep -q Qwen; then
  nohup python3 -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct --port 8000 --max-model-len 16384 \
    --gpu-memory-utilization 0.92 --enforce-eager \
    > /root/synthflood/logs/vllm.log 2>&1 &
  echo $! > /tmp/vllm.pid
  echo "vllm starting pid $(cat /tmp/vllm.pid)"
else
  echo "vllm already serving"
fi
