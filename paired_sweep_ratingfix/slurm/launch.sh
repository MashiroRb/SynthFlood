#!/bin/bash
set -euo pipefail
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official"
export WEBSHOP_REPO="$PWD/.runtime/WebShop" SYNTHFLOOD_STRICT_REWARD=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
OUTDIR="results_paired_n98_ratingfix_v2/worker${PAIR_LANE_ID:?}"
mkdir -p "$OUTDIR"
if [ -e "$OUTDIR/main.jsonl" ]; then echo 'Refusing overwrite'; exit 1; fi
SERVER_PID=
cleanup() {
    status=$?
    if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null || true; fi
    if [ "$status" -ne 0 ]; then
        PAIR_FAILURE_CODE="$status" .runtime/venv/bin/python - <<'PY'
import os
from pathlib import Path
from paired_sweep_ratingfix.common import write,OUT
if not (OUT/'FAILED.json').exists():
    write(OUT/'FAILED.json',{'lane':os.environ['PAIR_LANE_ID'],'stage':'launcher','exit':os.environ['PAIR_FAILURE_CODE']})
PY
    fi
}
trap cleanup EXIT
.runtime/venv/bin/python - <<'PY'
import os,torch
from paired_sweep_ratingfix.common import OUT,write,load_lane
lane=int(os.environ['PAIR_LANE_ID']);load_lane(lane)
p=torch.cuda.get_device_properties(0)
write(OUT/f'worker{lane}'/'hardware.json',{'name':p.name,'uuid':str(getattr(p,'uuid','')),
    'total_memory':p.total_memory,'compute_capability':[p.major,p.minor],
    'torch':torch.__version__,'cuda':torch.version.cuda,
    'visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'node':os.environ.get('SLURMD_NODENAME')})
print('GPU_READY',p.name,flush=True)
PY
cp data/paired_n98_ratingfix_v2/manifest.json "$OUTDIR/input-manifest.json"
cp .runtime/environment.txt "$OUTDIR/environment.txt"
cp .runtime/paired-n98-ratingfix-source.tar.gz "$OUTDIR/code-snapshot.tar.gz"
export VLLM_CACHE_ROOT="$PWD/.runtime/n98rf-vllm-${SLURM_JOB_ID}"
export TRITON_CACHE_DIR="$PWD/.runtime/n98rf-triton-${SLURM_JOB_ID}"
export XDG_CACHE_HOME="$PWD/.runtime/n98rf-cache-${SLURM_JOB_ID}"
mkdir -p "$VLLM_CACHE_ROOT" "$TRITON_CACHE_DIR" "$XDG_CACHE_HOME"
export SYNTHFLOOD_API_BASE="http://127.0.0.1:$((18000 + SLURM_JOB_ID % 30000))/v1"
PORT="${SYNTHFLOOD_API_BASE##*:}"; PORT="${PORT%/v1}"
GPU_UTIL=$(.runtime/venv/bin/python - <<'PY'
import os,json
from pathlib import Path
x=json.loads((Path('results_paired_n98_ratingfix_v2')/f"worker{os.environ['PAIR_LANE_ID']}"/'hardware.json').read_text())
print(min(.88,22*1024**3/x['total_memory']))
PY
)
MODEL_PATH=/mnt/beegfs/home/liudianru26/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28
.runtime/venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name Qwen/Qwen2.5-7B-Instruct \
    --host 127.0.0.1 --port "$PORT" --dtype bfloat16 \
    --max-model-len 16384 --max-num-seqs 1 --enforce-eager \
    --no-enable-prefix-caching --max-num-batched-tokens 16384 \
    --gpu-memory-utilization "$GPU_UTIL" --seed 2027 \
    --disable-log-requests --disable-log-stats --uvicorn-log-level warning \
    > "$OUTDIR/server.log" 2>&1 &
SERVER_PID=$!
ready=0
for ((attempt=0; attempt<120; attempt++)); do
    if .runtime/venv/bin/python m1/server_ready.py "$SYNTHFLOOD_API_BASE/models" "$OUTDIR/models.json"; then ready=1;break;fi
    kill -0 "$SERVER_PID" 2>/dev/null || { tail -50 "$OUTDIR/server.log";exit 1; }
    sleep 5
done
[ "$ready" = 1 ] || { echo 'Server startup timed out'; exit 1; }
.runtime/venv/bin/python -m paired_sweep_ratingfix.worker "$PAIR_LANE_ID"
