#!/bin/bash
#SBATCH --job-name=sf-publish-verify-results
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=.runtime/publish/verify-published-%j.log
set -euo pipefail
cd /mnt/beegfs/home/liudianru26/project/www2027/SynthFlood-local
export PYTHONPATH="$PWD" OMP_NUM_THREADS=1
.runtime/venv/bin/python -u .runtime/publish/verify_published.py
