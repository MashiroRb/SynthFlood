#!/bin/bash
#SBATCH --job-name=sf-m1-setup
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=.runtime/slurm/setup-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export TMPDIR="$PWD/.runtime/tmp"
export PIP_CACHE_DIR="$PWD/.runtime/pip-cache"
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
mkdir -p "$TMPDIR" .runtime/slurm data/official .runtime
# Compute nodes must not inherit a login-node loopback proxy.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
if [ -e .runtime/venv/bin/python3.11 ]; then
    mv .runtime/venv .runtime/venv-unused-python311
fi
# Reuse the cluster's read-only vLLM/Torch stack in an isolated overlay.
# Avoid downloading a second multi-GB CUDA environment.
/apps/miniconda3/envs/vllm/bin/python -m venv --system-site-packages .runtime/venv
.runtime/venv/bin/python -m pip install --upgrade pip
.runtime/venv/bin/python -m pip install 'spacy==3.7.5' thefuzz prettytable gdown matplotlib scipy
if [ ! -d .runtime/WebShop/.git ]; then
    git clone --depth 1 https://github.com/princeton-nlp/WebShop.git .runtime/WebShop
fi
.runtime/venv/bin/python -m spacy download en_core_web_sm
.runtime/venv/bin/python m1/download_official.py --output data/official
.runtime/venv/bin/python -m pip freeze > .runtime/environment.txt
git -C .runtime/WebShop rev-parse HEAD > .runtime/webshop-commit.txt
echo SETUP_COMPLETE
