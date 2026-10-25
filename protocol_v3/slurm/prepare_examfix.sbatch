#!/bin/bash
#SBATCH --job-name=sf-v3-examfix-prepare
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=.runtime/slurm/v3-examfix-prepare-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=2 PYTHONUNBUFFERED=1
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop" SYNTHFLOOD_STRICT_REWARD=1
.runtime/venv/bin/python -m protocol_v3.prepare_examfix
.runtime/venv/bin/python -m protocol_v3.test_executor
.runtime/venv/bin/python -m protocol_v3.test_inputs
