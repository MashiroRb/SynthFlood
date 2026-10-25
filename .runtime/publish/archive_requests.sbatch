#!/bin/bash
#SBATCH --job-name=sf-publish-request-archive
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=.runtime/publish/archive-%j.log
set -euo pipefail
cd /mnt/beegfs/home/liudianru26/project/www2027/SynthFlood-local
python3 -u .runtime/publish/archive_requests.py
