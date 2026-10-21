#!/bin/bash
#SBATCH --job-name=sf-parity-summary
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/expanded-summary-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python m1/expanded_summary.py
