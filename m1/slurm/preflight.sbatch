#!/bin/bash
#SBATCH --job-name=sf-m1-preflight
#SBATCH --partition=rtx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/preflight-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export XDG_CACHE_HOME="$PWD/.runtime/preflight-cache-${SLURM_JOB_ID}"
export VLLM_CACHE_ROOT="$XDG_CACHE_HOME/vllm" TRITON_CACHE_DIR="$XDG_CACHE_HOME/triton"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
mkdir -p "$XDG_CACHE_HOME"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
.runtime/venv/bin/python m1/gpu_preflight.py
