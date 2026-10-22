#!/bin/bash
#SBATCH --job-name=sf-w40-log-audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:40:00
#SBATCH --output=.runtime/slurm/w40-log-audit-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python -u audit_washout40_logs/audit.py
