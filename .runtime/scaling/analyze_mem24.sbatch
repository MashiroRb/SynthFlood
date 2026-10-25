#!/bin/bash
#SBATCH --job-name=sf-v3-scaled-analysis
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=.runtime/slurm/v3-scaled-analysis-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop"
export OMP_NUM_THREADS=2
.runtime/venv/bin/python -u .runtime/scaling/analyze_scaled.py
