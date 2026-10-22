#!/bin/bash
#SBATCH --job-name=sf-n98rf-freeze
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=.runtime/slurm/n98rf-freeze-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official"
export WEBSHOP_REPO="$PWD/.runtime/WebShop" SYNTHFLOOD_STRICT_REWARD=1 SYNTHFLOOD_PRODUCT_CACHE=0
.runtime/venv/bin/python -m paired_sweep_ratingfix.test_invariants
.runtime/venv/bin/python -m paired_sweep_ratingfix.freeze
tar -czf .runtime/paired-n98-ratingfix-source.tar.gz paired_sweep_ratingfix synthflood m1/server_ready.py
echo N98_PREPARE_COMPLETE
