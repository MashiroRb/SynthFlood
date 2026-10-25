#!/bin/bash
#SBATCH --job-name=sf-v3-stateless-a800
#SBATCH --kill-on-invalid-dep=yes
#SBATCH --partition=a800
#SBATCH --gres=gpu:a800:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=168:00:00
#SBATCH --output=.runtime/slurm/v3-stateless-a800-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
bash protocol_v3/slurm/launch.sh worker 7
