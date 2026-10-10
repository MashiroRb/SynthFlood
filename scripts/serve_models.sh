#!/bin/bash
# Start two vLLM OpenAI-compatible servers, one model per 4090.
# GPU0: main backbone (Qwen2.5-7B)  GPU1: second backbone / generator
set -e
export HF_HUB_OFFLINE=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn

MODEL0=${MODEL0:-Qwen/Qwen2.5-7B-Instruct}
MODEL1=${MODEL1:-NousResearch/Meta-Llama-3.1-8B-Instruct}

CUDA_VISIBLE_DEVICES=0 nohup python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL0" --port 8000 --max-model-len 16384 \
  --gpu-memory-utilization 0.92 --enforce-eager \
  > ~/synthflood/logs/vllm_gpu0.log 2>&1 &
echo "gpu0 pid $!"

CUDA_VISIBLE_DEVICES=1 nohup python3 -m vllm.entrypoints.openai.api_server \
  --model "$MODEL1" --port 8001 --max-model-len 16384 \
  --gpu-memory-utilization 0.92 --enforce-eager \
  > ~/synthflood/logs/vllm_gpu1.log 2>&1 &
echo "gpu1 pid $!"
