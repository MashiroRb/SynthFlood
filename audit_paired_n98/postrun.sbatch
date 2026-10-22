#!/bin/bash
#SBATCH --job-name=sf-n98-postrun
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=.runtime/slurm/n98-postrun-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1
export SYNTHFLOOD_ROOT="$PWD" WEBSHOP_REPO="$PWD/.runtime/WebShop"
.runtime/venv/bin/python -m audit_paired_n98.postrun
