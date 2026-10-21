#!/bin/bash
#SBATCH --job-name=sf-parity-review
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/expanded-review-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
python3 m1/review_expanded.py
