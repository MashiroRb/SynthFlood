#!/bin/bash
#SBATCH --job-name=sf-publish-verify
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=.runtime/publish/verify-%j.log
set -euo pipefail
cd /mnt/beegfs/home/liudianru26/project/www2027/SynthFlood-local
export PYTHONPATH="$PWD" OMP_NUM_THREADS=1
.runtime/venv/bin/python -u .runtime/publish/verify.py
