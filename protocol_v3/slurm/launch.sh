#!/bin/bash
set -euo pipefail
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official"
export WEBSHOP_REPO="$PWD/.runtime/WebShop" SYNTHFLOOD_STRICT_REWARD=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
MODE="${1:?}"; INDEX="${2:-0}"
TENSOR_PARALLEL="${V3_TENSOR_PARALLEL:-1}"
case "$MODE" in
    generate|finalize) OUTDIR=results_protocol_v3_20261024_relaxed_v1/preflight; MODEL_CONTEXT=131072; GPU_BUDGET_GIB=30 ;;
    worker) OUTDIR="results_protocol_v3_20261024_relaxed_v1/worker$INDEX"; MODEL_CONTEXT=65536; GPU_BUDGET_GIB=22 ;;
    washout) OUTDIR="results_protocol_v3_20261024_relaxed_v1/washout$INDEX"; MODEL_CONTEXT=131072; GPU_BUDGET_GIB=30 ;;
    *) exit 2 ;;
esac
if [ "$TENSOR_PARALLEL" -gt 1 ]; then
    GPU_BUDGET_GIB=14
    export OMP_NUM_THREADS=2
fi
mkdir -p "$OUTDIR"
if [ -e "$OUTDIR/LAUNCH.json" ]; then echo 'Refusing duplicate launcher'; exit 1; fi
export V3_OUTDIR="$OUTDIR" V3_CONTEXT="$MODEL_CONTEXT" V3_GPU_BUDGET_GIB="$GPU_BUDGET_GIB" V3_TENSOR_PARALLEL="$TENSOR_PARALLEL"
.runtime/venv/bin/python - <<'PY'
import os,torch
from pathlib import Path
from protocol_v3.common import write,REVISION
p=torch.cuda.get_device_properties(0)
devices=[]
for index in range(torch.cuda.device_count()):
    prop=torch.cuda.get_device_properties(index)
    devices.append(dict(index=index,name=prop.name,uuid=str(getattr(prop,'uuid','')),total_memory=prop.total_memory))
assert len(devices)==int(os.environ['V3_TENSOR_PARALLEL'])
d=Path(os.environ['V3_OUTDIR'])
write(d/'hardware.json',dict(name=p.name,uuid=str(getattr(p,'uuid','')),total_memory=p.total_memory,
    compute_capability=[p.major,p.minor],torch=torch.__version__,cuda=torch.version.cuda,
    visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),node=os.environ.get('SLURMD_NODENAME'),
    revision=REVISION,context=int(os.environ['V3_CONTEXT']),dtype='bfloat16',vllm='0.8.1',
    rope_scaling=dict(rope_type='yarn',factor=4.0,original_max_position_embeddings=32768),
    chunked_prefill=True,max_num_batched_tokens=4096,max_num_seqs=1,prefix_caching=False,
    tensor_parallel_size=int(os.environ['V3_TENSOR_PARALLEL']),devices=devices,
    kv_cache_dtype='auto-bfloat16',custom_all_reduce=False if len(devices)>1 else 'default',
    torch_inductor_fx_graph_cache=False,torch_inductor_force_disable_caches=True))
write(d/'LAUNCH.json',dict(job=os.environ['SLURM_JOB_ID'],array_task=os.environ.get('SLURM_ARRAY_TASK_ID')))
PY
cp .runtime/environment.txt "$OUTDIR/environment.txt"
export VLLM_CACHE_ROOT="$PWD/.runtime/v3-vllm-${SLURM_JOB_ID}"
export TRITON_CACHE_DIR="$PWD/.runtime/v3-triton-${SLURM_JOB_ID}"
export XDG_CACHE_HOME="$PWD/.runtime/v3-cache-${SLURM_JOB_ID}"
export TORCHINDUCTOR_CACHE_DIR="$PWD/.runtime/v3-inductor-${SLURM_JOB_ID}"
export TORCHINDUCTOR_FX_GRAPH_CACHE=0 TORCHINDUCTOR_FORCE_DISABLE_CACHES=1
mkdir -p "$VLLM_CACHE_ROOT" "$TRITON_CACHE_DIR" "$XDG_CACHE_HOME" "$TORCHINDUCTOR_CACHE_DIR"
export SYNTHFLOOD_API_BASE="http://127.0.0.1:$((18000 + SLURM_JOB_ID % 30000))/v1"
PORT="${SYNTHFLOOD_API_BASE##*:}"; PORT="${PORT%/v1}"
GPU_UTIL=$(.runtime/venv/bin/python - <<'PY'
import os,json
from pathlib import Path
x=json.loads((Path(os.environ['V3_OUTDIR'])/'hardware.json').read_text())
print(min(.92,int(os.environ['V3_GPU_BUDGET_GIB'])*1024**3/x['total_memory']))
PY
)
MODEL_PATH=/mnt/beegfs/home/liudianru26/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28
SERVER_PID=
cleanup() {
    code=$?
    if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null || true; fi
    if [ "$code" -ne 0 ]; then
        printf '{"exit_code":%s,"job_id":"%s"}\n' "$code" "$SLURM_JOB_ID" > "$OUTDIR/FAILED.json"
    fi
}
trap cleanup EXIT
TP_ARGS=(--tensor-parallel-size "$TENSOR_PARALLEL")
if [ "$TENSOR_PARALLEL" -gt 1 ]; then
    TP_ARGS+=(--distributed-executor-backend mp --disable-custom-all-reduce)
fi
.runtime/venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name Qwen/Qwen2.5-7B-Instruct \
    --host 127.0.0.1 --port "$PORT" --dtype bfloat16 \
    --max-model-len "$MODEL_CONTEXT" --max-num-seqs 1 --enforce-eager \
    --rope-scaling '{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":32768}' \
    --enable-chunked-prefill --max-num-batched-tokens 4096 --no-enable-prefix-caching \
    --gpu-memory-utilization "$GPU_UTIL" --seed 2027 --swap-space 0 \
    "${TP_ARGS[@]}" \
    --disable-log-requests --disable-log-stats --uvicorn-log-level warning \
    > "$OUTDIR/server.log" 2>&1 &
SERVER_PID=$!
ready=0
for ((attempt=0; attempt<180; attempt++)); do
    if .runtime/venv/bin/python m1/server_ready.py "$SYNTHFLOOD_API_BASE/models" "$OUTDIR/models.json"; then ready=1;break;fi
    kill -0 "$SERVER_PID" 2>/dev/null || { tail -60 "$OUTDIR/server.log";exit 1; }
    sleep 5
done
[ "$ready" = 1 ] || { echo 'Server startup timed out'; exit 1; }
if [ "$MODE" = generate ] || [ "$MODE" = finalize ]; then
    if [ "$MODE" = finalize ]; then
        .runtime/venv/bin/python -m protocol_v3.preflight_only
    else
        .runtime/venv/bin/python -m protocol_v3.generate
    fi
else
    .runtime/venv/bin/python -c 'from protocol_v3.common import validate; validate()'
    cp data/protocol_v3_20261024_relaxed_v1/manifest.json "$OUTDIR/input-manifest.json"
    cp .runtime/protocol-v3-relaxed-v1-source.tar.gz "$OUTDIR/code-snapshot.tar.gz"
    .runtime/venv/bin/python -m "protocol_v3.$MODE" "$INDEX"
fi
