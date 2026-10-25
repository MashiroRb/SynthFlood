#!/bin/bash
#SBATCH --job-name=sf-v3-washout
#SBATCH --kill-on-invalid-dep=yes
#SBATCH --partition=rtx
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=240:00:00
#SBATCH --output=.runtime/slurm/v3-washout-%A_%a.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export V3_TENSOR_PARALLEL=2
bash protocol_v3/slurm/launch.sh washout "${SLURM_ARRAY_TASK_ID:?}"
