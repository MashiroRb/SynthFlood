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
