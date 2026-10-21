#!/bin/bash
#SBATCH --job-name=sf-m1-archive
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/archive-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
python3 m1/prepare_retry_metadata.py
if [ ! -e .runtime/code-snapshot-before-git-fix.tar.gz ]; then
    cp .runtime/code-snapshot.tar.gz .runtime/code-snapshot-before-git-fix.tar.gz
fi
tar -czf .runtime/code-snapshot.tar.gz m1 synthflood results_realattack/mine_full_pairs.py
python3 m1/validate_v2.py
