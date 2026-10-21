#!/bin/bash
#SBATCH --job-name=sf-m1-download
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:00:00
#SBATCH --output=.runtime/slurm/download-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
python3 m1/download_official.py --output data/official
