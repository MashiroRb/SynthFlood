#!/bin/bash
#SBATCH --job-name=sf-length-summary
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/length-summary-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python m1/exposure_length_summary.py
