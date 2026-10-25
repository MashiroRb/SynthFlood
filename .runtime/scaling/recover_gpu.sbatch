#!/bin/bash
#SBATCH --job-name=sf-v3-washout-recover
#SBATCH --partition=rtx
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=120:00:00
#SBATCH --output=.runtime/slurm/v3-recover-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export V3_TENSOR_PARALLEL=2
: "${V3_EXTRA_SEEDS:?Resume only the seeds assigned in scaling_manifest.json}"
bash .runtime/scaling/launch_extra.sh washout "${V3_TARGET_SHARD:?}"
