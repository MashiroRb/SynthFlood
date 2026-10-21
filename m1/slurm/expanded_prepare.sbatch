#!/bin/bash
#SBATCH --job-name=sf-parity-prepare
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=48G
#SBATCH --time=00:45:00
#SBATCH --output=.runtime/slurm/expanded-prepare-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official"
export WEBSHOP_REPO="$PWD/.runtime/WebShop"
export M1_GOALS_SEED=2027 M1_SEED_BASE=2027 M1_PROTOCOL=balanced_v2 SYNTHFLOOD_PRODUCT_CACHE=0
unset M1_CONTEXT_PATH
.runtime/venv/bin/python m1/expanded_summary.py --self-test
.runtime/venv/bin/python m1/expanded_parity.py prepare
tar -czf .runtime/expanded-source.tar.gz m1 synthflood
echo EXPANDED_PREPARE_COMPLETE
