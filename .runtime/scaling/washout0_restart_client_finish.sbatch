#!/bin/bash
#SBATCH --job-name=sf-v3-washout0-resume
#SBATCH --partition=rtx
#SBATCH --nodelist=aias-compute-01
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=36:00:00
#SBATCH --output=.runtime/slurm/v3-washout0-resume-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop"
export SYNTHFLOOD_STRICT_REWARD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1
export SYNTHFLOOD_API_BASE=http://127.0.0.1:18049/v1
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
.runtime/venv/bin/python -u .runtime/scaling/resume_washout.py --shard 0 --seeds 2030 2032
.runtime/venv/bin/python - <<'PY'
import json,subprocess,time
from pathlib import Path
p=Path('results_protocol_v3_20261024_relaxed_v1/washout0')
done=json.loads((p/'COMPLETE.json').read_text())
assert done['validated'] and done['seeds']==[2030,2032]
subprocess.run(['scancel','150039_0'],check=True)
for _ in range(60):
    state=subprocess.run(['squeue','-h','-j','150049','-o','%i'],capture_output=True,text=True)
    if not state.stdout.strip():break
    time.sleep(1)
subprocess.run(['scancel','150933'],check=True)
Path('.runtime/scaling/washout0_inplace_restart/COMPLETE.json').write_text(json.dumps(dict(validated=True,seeds=[2030,2032],original_gpu_job=150049,retired_server_controller=150933)))
PY
