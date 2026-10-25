#!/bin/bash
#SBATCH --job-name=sf-v3-washout0-server-restart
#SBATCH --partition=rtx
#SBATCH --nodelist=aias-compute-01
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=36:00:00
#SBATCH --output=.runtime/slurm/v3-washout0-restart-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1
.runtime/venv/bin/python -u .runtime/scaling/washout0_restart_control.py
