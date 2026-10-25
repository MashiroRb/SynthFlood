#!/bin/bash
#SBATCH --job-name=sf-v3-washout-24g
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=36:00:00
#SBATCH --output=.runtime/slurm/v3-washout24-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop"
export SYNTHFLOOD_STRICT_REWARD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
.runtime/venv/bin/python -u .runtime/scaling/mem24_run.py "${V3_MEM24_SHARD:?}"
