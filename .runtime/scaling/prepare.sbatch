#!/bin/bash
#SBATCH --job-name=sf-v3-scale-prepare
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=.runtime/slurm/v3-scale-prepare-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python -u .runtime/scaling/prepare.py
