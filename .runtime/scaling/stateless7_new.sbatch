#!/bin/bash
#SBATCH --job-name=sf-v3-stateless7-independent
#SBATCH --partition=rtx
#SBATCH --nodelist=aias-compute-2
#SBATCH --gres=gpu:4090:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=120:00:00
#SBATCH --output=.runtime/slurm/v3-stateless7-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1 V3_TENSOR_PARALLEL=1
exec 9>results_protocol_v3_20261024_relaxed_v1/worker7-owner.lock
flock -n 9
.runtime/venv/bin/python -u .runtime/scaling/stateless7_handoff.py verify-new
bash protocol_v3/slurm/launch.sh worker 7
