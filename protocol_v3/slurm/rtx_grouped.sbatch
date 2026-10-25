#!/bin/bash
#SBATCH --job-name=sf-v3-rtx-stateless
#SBATCH --kill-on-invalid-dep=yes
#SBATCH --partition=rtx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=168:00:00
#SBATCH --output=.runtime/slurm/v3-stateless-%A_%a.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export V3_TENSOR_PARALLEL=1
V3_LANE_INDEX="${SLURM_ARRAY_TASK_ID:?}"
bash protocol_v3/slurm/launch.sh worker "$V3_LANE_INDEX"
if [ "$V3_LANE_INDEX" -lt 2 ]; then
    bash protocol_v3/slurm/launch.sh worker "$((V3_LANE_INDEX+6))"
fi
