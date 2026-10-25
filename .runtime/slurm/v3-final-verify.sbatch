#!/bin/bash
#SBATCH --job-name=sf-v3-final-completeness-audit
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/v3-final-verify-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop" OMP_NUM_THREADS=1
.runtime/venv/bin/python -u .runtime/manual_v3_check.py
.runtime/venv/bin/python -u .runtime/manual_v3_window.py
.runtime/venv/bin/python -u .runtime/manual_v3_design_audit.py
