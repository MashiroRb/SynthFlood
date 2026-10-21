#!/bin/bash
#SBATCH --job-name=sf-m1-audit
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/audit-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
python3 m1/test_reproducibility.py
python3 m1/audit_figure6.py
python3 -m compileall -q m1 synthflood
