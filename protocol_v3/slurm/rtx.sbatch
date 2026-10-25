#!/bin/bash
#SBATCH --job-name=sf-v3-stateless
#SBATCH --kill-on-invalid-dep=yes
#SBATCH --partition=rtx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=168:00:00
#SBATCH --output=.runtime/slurm/v3-stateless-%A_%a.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
bash protocol_v3/slurm/launch.sh worker "${SLURM_ARRAY_TASK_ID:?}"
