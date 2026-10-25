#!/bin/bash
#SBATCH --job-name=sf-publish-archive-only
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=.runtime/publish/archive-fast-%j.log
set -euo pipefail
cd /mnt/beegfs/home/liudianru26/project/www2027/SynthFlood-local
python3 -u .runtime/publish/archive_fast.py
