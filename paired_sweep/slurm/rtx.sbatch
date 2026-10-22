#!/bin/bash
#SBATCH --job-name=sf-n98
#SBATCH --partition=rtx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=72:00:00
#SBATCH --output=.runtime/slurm/n98-rtx-%A_%a.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PAIR_LANE_ID="${SLURM_ARRAY_TASK_ID:?}"
bash paired_sweep/slurm/launch.sh
