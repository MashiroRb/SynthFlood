#!/bin/bash
#SBATCH --job-name=sf-n98-a800
#SBATCH --partition=a800
#SBATCH --qos=a800
#SBATCH --gres=gpu:a800:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=72:00:00
#SBATCH --output=.runtime/slurm/n98-a800-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PAIR_LANE_ID=7
bash paired_sweep/slurm/launch.sh
