#!/bin/bash
#SBATCH --job-name=sf-w40-server-audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/w40-server-audit-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
.runtime/venv/bin/python -u audit_washout40_logs/server_audit.py
