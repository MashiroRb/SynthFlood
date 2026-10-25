#!/bin/bash
#SBATCH --job-name=sf-v3-washout-extra
#SBATCH --partition=a800
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=120:00:00
#SBATCH --output=.runtime/slurm/v3-extra-%A_%a.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export V3_TENSOR_PARALLEL=1
if [ "${SLURM_ARRAY_TASK_ID:?}" = 0 ]; then
    export V3_EXTRA_SEEDS='2034 2036'
else
    export V3_EXTRA_SEEDS='2035 2037'
fi
bash .runtime/scaling/launch_extra.sh washout "$((SLURM_ARRAY_TASK_ID+2))"
