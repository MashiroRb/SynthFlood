#!/bin/bash
#SBATCH --job-name=sf-m1-summary
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/summary-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 MPLCONFIGDIR="$PWD/.runtime/matplotlib"
.runtime/venv/bin/python m1/summarize_v2.py
.runtime/venv/bin/python m1/plot_audit.py
echo SUMMARY_COMPLETE
