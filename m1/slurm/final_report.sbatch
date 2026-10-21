#!/bin/bash
#SBATCH --job-name=sf-m1-final-report
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/final-report-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
python3 m1/build_final_report.py
