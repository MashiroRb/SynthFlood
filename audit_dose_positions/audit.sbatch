#!/bin/bash
#SBATCH --job-name=sf-dose-audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=.runtime/slurm/dose-position-audit-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1
.runtime/venv/bin/python audit_dose_positions/audit.py
