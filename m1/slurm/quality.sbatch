#!/bin/bash
#SBATCH --job-name=sf-m1-quality
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=.runtime/slurm/quality-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 SYNTHFLOOD_ROOT="$PWD"
export WEBSHOP_REPO="$PWD/.runtime/WebShop" SYNTHFLOOD_STRICT_REWARD=1
.runtime/venv/bin/python m1/autopsy_quality.py
