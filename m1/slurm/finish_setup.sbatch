#!/bin/bash
#SBATCH --job-name=sf-m1-setup-rest
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=.runtime/slurm/setup-rest-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export OMP_NUM_THREADS=2 PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export TMPDIR="$PWD/.runtime/tmp" PIP_CACHE_DIR="$PWD/.runtime/pip-cache"
export HF_HOME="$PWD/.runtime/hf"
.runtime/venv/bin/python -m pip install 'numpy<2' hf_transfer gym==0.26.2
.runtime/venv/bin/python m1/download_fast.py --model-only
.runtime/venv/bin/python -m pip install --no-deps .runtime/spacy-model/en_core_web_sm-[0-9]*.whl
.runtime/venv/bin/python -c 'import spacy; nlp=spacy.load("en_core_web_sm"); print("SPACY_READY",spacy.__version__)'
.runtime/venv/bin/python m1/download_fast.py
.runtime/venv/bin/python -m pip freeze > .runtime/environment.txt
git -C .runtime/WebShop rev-parse HEAD > .runtime/webshop-commit.txt
echo SETUP_COMPLETE
