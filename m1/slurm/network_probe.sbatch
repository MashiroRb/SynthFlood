#!/bin/bash
#SBATCH --job-name=sf-m1-net
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=512M
#SBATCH --time=00:05:00
#SBATCH --output=.runtime/slurm/network-%j.log
set -u
cd "${SLURM_SUBMIT_DIR:?}"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
for base in https://huggingface.co https://hf-mirror.com; do
    curl -sSI --connect-timeout 5 --max-time 10 "$base/datasets/YWZBrandon/webshop-data/resolve/main/items_shuffle.json" | head -n 3
done
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$PWD/.runtime/login-known-hosts" \
    -N -L 127.0.0.1:18991:127.0.0.1:7891 liudianru26@192.168.10.100 &
TUNNEL=$!
trap 'kill "$TUNNEL" 2>/dev/null || true' EXIT
sleep 3
curl -sSI --proxy http://127.0.0.1:18991 --connect-timeout 5 --max-time 15 \
    https://huggingface.co/datasets/YWZBrandon/webshop-data/resolve/main/items_shuffle.json | head -n 5
