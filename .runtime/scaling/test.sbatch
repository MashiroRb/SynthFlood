#!/bin/bash
#SBATCH --job-name=sf-v3-resume-tests
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=.runtime/slurm/v3-resume-tests-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop"
export SYNTHFLOOD_STRICT_REWARD=1 OMP_NUM_THREADS=1
.runtime/venv/bin/python -u .runtime/scaling/test_resume.py
.runtime/venv/bin/python -c 'from protocol_v3.common import validate;validate();print("CURRENT_FROZEN_SOURCES_UNCHANGED")'
