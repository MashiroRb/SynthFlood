#!/bin/bash
#SBATCH --job-name=sf-w40-summary
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=.runtime/slurm/washout40-summary-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python m1/washout40_summary.py
