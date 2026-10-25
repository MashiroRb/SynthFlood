#!/bin/bash
#SBATCH --job-name=sf-v3-final-csv-exports
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/v3-final-exports-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1
.runtime/venv/bin/python -u .runtime/summarize_completed_wash_seed.py 2032
.runtime/venv/bin/python -u .runtime/export_v3_final_results.py
