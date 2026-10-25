#!/bin/bash
#SBATCH --job-name=sf-v3-lane7-routing
#SBATCH --partition=rtx
#SBATCH --nodelist=aias-compute-4
#SBATCH --gres=none
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=.runtime/slurm/v3-lane7-handoff-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1
.runtime/venv/bin/python -u .runtime/scaling/stateless7_handoff.py supervise
