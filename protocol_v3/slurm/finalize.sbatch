#!/bin/bash
#SBATCH --job-name=sf-v3-final-preflight
#SBATCH --kill-on-invalid-dep=yes
#SBATCH --partition=rtx,a800
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=.runtime/slurm/v3-finalize-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export SYNTHFLOOD_ROOT="$PWD" SYNTHFLOOD_DATA_DIR="$PWD/data/official" WEBSHOP_REPO="$PWD/.runtime/WebShop"
export V3_TENSOR_PARALLEL=2
.runtime/venv/bin/python -m protocol_v3.test_executor
.runtime/venv/bin/python -c 'from protocol_v3.preflight_only import validate_complete_exam;validate_complete_exam()'
tar -czf .runtime/protocol-v3-relaxed-v1-source.tar.gz protocol_v3 synthflood paired_sweep_ratingfix paired_sweep/common.py paired_sweep/freeze.py m1/m1_memory.py m1/server_ready.py
bash protocol_v3/slurm/launch.sh finalize 0
