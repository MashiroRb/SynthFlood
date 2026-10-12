#!/bin/bash
# wave-1e: E5 spoof envelope 35/65 (Qwen) -> A8 stealth pool (Llama swap)
#          -> none/struct/prov rerun on stealth pool (Qwen swap back).
# Output naming: {stage}.lower()_sweep.csv.  Done marker: "WAVE1E_DONE"
set -x
cd /root/synthflood/code
export HF_HUB_OFFLINE=1
mkdir -p /root/synthflood/archive
wait_port() { for i in $(seq 1 120); do curl -s "localhost:$1/v1/models" | grep -q '"data"' && return 0; sleep 10; done; echo "PORT_${1}_TIMEOUT"; return 1; }
kill_vllm() { pkill -f "vllm" || true; sleep 8; pkill -9 -f "vllm" || true; sleep 7; }

echo "== wave1e start $(date -u +%FT%TZ) =="

# ---------- Stage 1: E5 spoof 35/65 with Qwen ----------
wait_port 8000 || exit 1
for R in 35 65; do
  mv -f /root/synthflood/results/p4i_spoof${R}_sweep.csv /root/synthflood/archive/ 2>/dev/null
  echo "== spoof${R} start $(date -u +%FT%TZ) =="
  python3 -m synthflood.run_sweep --stage P4I_SPOOF${R} --n-tasks 40 \
    --eps 0.75 --family mix --seed 1 --defense provenance --spoof 0.${R} \
    --workers 32 >> /root/synthflood/logs/run_fix5.log 2>&1
  echo "== spoof${R} done $(date -u +%FT%TZ) rc=$? =="
done

# ---------- Stage 2: swap to Llama, generate stealth pool ----------
kill_vllm
export HF_HUB_OFFLINE=0
python3 - <<'PYEOF' >> /root/synthflood/logs/run_fix5.log 2>&1
import os
os.environ.pop("HF_HUB_OFFLINE", None)
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
from huggingface_hub import snapshot_download
snapshot_download("NousResearch/Meta-Llama-3.1-8B-Instruct",
                  ignore_patterns=["original/*"])
print("llama downloaded")
PYEOF
export HF_HUB_OFFLINE=1
nohup python3 -m vllm.entrypoints.openai.api_server \
  --model NousResearch/Meta-Llama-3.1-8B-Instruct --port 8001 \
  --max-model-len 16384 --gpu-memory-utilization 0.92 --enforce-eager \
  &> /root/vllm_llama.log &
wait_port 8001 || exit 1
echo "== stealth gen start $(date -u +%FT%TZ) =="
python3 -m synthflood.generate_driver --n-tasks 40 --per-task 4 \
  --port 8001 --model NousResearch/Meta-Llama-3.1-8B-Instruct \
  --judge-port 8001 --judge-model NousResearch/Meta-Llama-3.1-8B-Instruct \
  --style stealth \
  --out /root/synthflood/data/contamination/pool_stealth.json \
  >> /root/synthflood/logs/run_fix5.log 2>&1
echo "== stealth gen done $(date -u +%FT%TZ) rc=$? =="

# ---------- Stage 3: swap back to Qwen ----------
kill_vllm
nohup python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct --port 8000 \
  --max-model-len 16384 --gpu-memory-utilization 0.92 --enforce-eager \
  &> /root/vllm.log &
wait_port 8000 || exit 1

# ---------- Stage 4: rerun defenses on stealth pool ----------
for ARM in P4M_NONE_ST:none P4M_STRUCT_ST:struct P4M_PROV_ST:provenance; do
  ST=${ARM%%:*}; D=${ARM#*:}
  mv -f /root/synthflood/results/${ST,,}_sweep.csv /root/synthflood/archive/ 2>/dev/null
  echo "== ${ST} start $(date -u +%FT%TZ) =="
  python3 -m synthflood.run_sweep --stage $ST --n-tasks 40 --eps 0.75 \
    --family mix --seed 1 --defense $D \
    --pool /root/synthflood/data/contamination/pool_stealth.json \
    --workers 32 >> /root/synthflood/logs/run_fix5.log 2>&1
  echo "== ${ST} done $(date -u +%FT%TZ) rc=$? =="
done

echo "== WAVE1E_DONE $(date -u +%FT%TZ) =="
