#!/bin/bash
# Generate the synthetic contamination pool.
# Generator: GPU1 (Llama-3.1-8B). Judge: GPU0 (Qwen2.5-7B).
set -e
cd ~/synthflood/code
python3 -m synthflood.generate_driver --n-tasks 40 --per-task 4 --port 8001 \
  --model NousResearch/Meta-Llama-3.1-8B-Instruct \
  --judge-port 8000 --judge-model Qwen/Qwen2.5-7B-Instruct
