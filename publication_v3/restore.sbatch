#!/bin/bash
#SBATCH --job-name=sf-v3-restore-archive
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=sf-v3-restore-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
python3 publication_v3/restore.py "$@"
