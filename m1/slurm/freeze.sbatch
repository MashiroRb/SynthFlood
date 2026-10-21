#!/bin/bash
#SBATCH --job-name=sf-m1-freeze
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=.runtime/slurm/freeze-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official"
export WEBSHOP_REPO="$PWD/.runtime/WebShop"
export M1_GOALS_SEED=2027
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
.runtime/venv/bin/python -m pip install matplotlib scipy
export RA_CATALOG="$PWD/data/official/items_shuffle.json"
export RA_HUMAN_INS="$PWD/data/official/items_human_ins.json"
export RA_PAIRS_OUT="$PWD/data/official/realattack_pairs.json"
if [ ! -s "$RA_PAIRS_OUT" ]; then
    .runtime/venv/bin/python results_realattack/mine_full_pairs.py
fi
.runtime/venv/bin/python m1/freeze_v2.py
.runtime/venv/bin/python m1/validate_v2.py
tar -czf .runtime/code-snapshot.tar.gz m1 synthflood results_realattack/mine_full_pairs.py
echo FREEZE_COMPLETE
