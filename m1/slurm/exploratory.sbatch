#!/bin/bash
#SBATCH --job-name=sf-m1-explore
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/explore-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
python3 m1/exploratory_quality_effects.py
