#!/bin/bash
#SBATCH --job-name=sf-n98rf-summary
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=96:00:00
#SBATCH --output=.runtime/slurm/n98rf-summary-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1
export SYNTHFLOOD_ROOT="$PWD" WEBSHOP_REPO="$PWD/.runtime/WebShop"
.runtime/venv/bin/python -m paired_sweep_ratingfix.coordinator
