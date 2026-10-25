#!/bin/bash
#SBATCH --job-name=sf-v3-washout-continue
#SBATCH --partition=rtx
#SBATCH --gres=none
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=120:00:00
#SBATCH --output=.runtime/slurm/v3-continue-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop"
export SYNTHFLOOD_STRICT_REWARD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export SYNTHFLOOD_API_BASE="http://127.0.0.1:$((18000+V3_ATTACH_JOB%30000))/v1"
.runtime/venv/bin/python -u .runtime/scaling/resume_washout.py --shard "${V3_ATTACH_SHARD:?}" --attach-job "${V3_ATTACH_JOB:?}" --release-target "${V3_RELEASE_TARGET:?}" --seeds $V3_ASSIGNED_SEEDS
