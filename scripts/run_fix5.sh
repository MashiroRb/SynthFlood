#!/bin/bash
# wave-1e: E5 spoof envelope 35/65 (Qwen) -> A8 stealth pool (Llama swap)
#          -> struct/prov/none rerun on stealth pool (Qwen swap back).
# Queue log: /root/fix_wave1e.log   Done marker: "WAVE1E_DONE"
set -x
cd /root/synthflood/code
export HF_HUB_OFFLINE=1
mkdir -p /root/synthflood/archive
wait_port() { for i in $(seq 1 120); do curl -s "localhost:$1/v1/models" | grep -q '"data"' && return 0; sleep 10; done; echo "PORT_${1}_TIMEOUT"; return 1; }
kill_vllm() { pkill -f "vllm serve" || true; sleep 8; pkill -9 -f "vllm serve" || true; sleep 7; }

echo "== wave1e start $(date -u +%FT%TZ) =="

# ---------- Stage 1: E5 spoof 35/65 with Qwen ----------
wait_port 8000 || exit 1
for R in 35 65; do
  S=0.${R}
  mv -f /root/synthflood/results/p4i_spoof${R}.csv /root/synthflood/archive/ 2>/dev/null
  echo "== spoof${R} start $(date -u +%FT%TZ) =="
  python3 -m synthflood.run_sweep --stage P4I_SPOOF${R} --n-tasks 40 \
    --eps 0.75 --family mix --seed 1 --defense provenance --spoof $S \
    --workers 32 --out /root/synthflood/results/p4i_spoof${R}.csv \
    >> /root/synthflood/logs/run_fix5.log 2>&1
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
for ARM in none:0.75:p4m_none_stealth struct:0.75:p4m_struct_stealth provenance:0.75:p4m_prov_stealth; do
  D=${ARM%%:*}; REST=${ARM#*:}; E=${REST%%:*}; OUT=${REST#*:}
  mv -f /root/synthflood/results/${OUT}.csv /root/synthflood/archive/ 2>/dev/null
  echo "== ${OUT} start $(date -u +%FT%TZ) =="
  python3 -m synthflood.run_sweep --stage P4M --n-tasks 40 --eps $E \
    --family mix --seed 1 --defense $D \
    --pool /root/synthflood/data/contamination/pool_stealth.json \
    --workers 32 --out /root/synthflood/results/${OUT}.csv \
    >> /root/synthflood/logs/run_fix5.log 2>&1
  echo "== ${OUT} done $(date -u +%FT%TZ) rc=$? =="
done

echo "== WAVE1E_DONE $(date -u +%FT%TZ) =="
