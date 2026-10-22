#!/bin/bash
#SBATCH --job-name=sf-paper-audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/paper-position-inventory-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python audit_dose_positions/paper_inventory.py
