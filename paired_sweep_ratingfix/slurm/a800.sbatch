#!/bin/bash
#SBATCH --job-name=sf-n98rf-a800
#SBATCH --partition=a800
#SBATCH --qos=urgent
#SBATCH --gres=gpu:a800:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=72:00:00
#SBATCH --output=.runtime/slurm/n98rf-a800-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export PAIR_LANE_ID=7
bash paired_sweep_ratingfix/slurm/launch.sh
