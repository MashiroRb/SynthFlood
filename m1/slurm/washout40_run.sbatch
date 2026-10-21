#!/bin/bash
#SBATCH --job-name=sf-w40
#SBATCH --partition=rtx
#SBATCH --gres=gpu:3090:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=.runtime/slurm/washout40-run-%A_%a.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official"
export WEBSHOP_REPO="$PWD/.runtime/WebShop"
export M1_PROTOCOL=balanced_v2 M1_FIX_INSTRUMENT=1 M1_EXAM_WORKERS=1 M1_GOALS_SEED=2027
export M1_CONTEXT_PATH="$PWD/data/m1_washout40/context.json"
export M1_SEED_BASE=$((2030 + ${SLURM_ARRAY_TASK_ID:?}))
export M1_OUT_SUBDIR="results_m1_washout40/seed${M1_SEED_BASE}"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export VLLM_CACHE_ROOT="$PWD/.runtime/vllm-${SLURM_JOB_ID}"
export TRITON_CACHE_DIR="$PWD/.runtime/triton-${SLURM_JOB_ID}"
export XDG_CACHE_HOME="$PWD/.runtime/cache-${SLURM_JOB_ID}"
mkdir -p "$VLLM_CACHE_ROOT" "$TRITON_CACHE_DIR" "$XDG_CACHE_HOME"
if [ -e "$M1_OUT_SUBDIR/m1_exams.csv" ]; then
    echo "Refusing to overwrite $M1_OUT_SUBDIR" >&2
    exit 1
fi
.runtime/venv/bin/python m1/washout40.py validate
mkdir -p "$M1_OUT_SUBDIR"
nvidia-smi > "$M1_OUT_SUBDIR/gpu.txt"
cp .runtime/environment.txt "$M1_OUT_SUBDIR/environment.txt"
cp data/m1_washout40/manifest.json "$M1_OUT_SUBDIR/input-manifest.json"
cp .runtime/washout40-source.tar.gz "$M1_OUT_SUBDIR/code-snapshot.tar.gz"
export SYNTHFLOOD_API_BASE="http://127.0.0.1:$((18000 + SLURM_JOB_ID % 30000))/v1"
PORT="${SYNTHFLOOD_API_BASE##*:}"
PORT="${PORT%/v1}"
MODEL_PATH=/mnt/beegfs/home/liudianru26/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28
.runtime/venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name Qwen/Qwen2.5-7B-Instruct \
    --host 127.0.0.1 --port "$PORT" --dtype bfloat16 \
    --max-model-len 16384 --max-num-seqs 1 --enforce-eager \
    --no-enable-prefix-caching --max-num-batched-tokens 16384 \
    --gpu-memory-utilization 0.88 --seed 2027 \
    > "$M1_OUT_SUBDIR/server.log" 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
ready=0
for ((attempt=0; attempt<120; attempt++)); do
    if .runtime/venv/bin/python m1/server_ready.py "$SYNTHFLOOD_API_BASE/models" "$M1_OUT_SUBDIR/models.json"; then
        ready=1
        break
    fi
    kill -0 "$SERVER_PID" 2>/dev/null || { tail -60 "$M1_OUT_SUBDIR/server.log"; exit 1; }
    sleep 5
done
[ "$ready" = 1 ] || { echo 'Server startup timed out'; exit 1; }
.runtime/venv/bin/python m1/washout40.py run
