#!/bin/bash
# Fresh-lab bootstrap for SynthFlood (single RTX 4090). Run as root.
# Layout: /root/synthflood/{code,data,logs,results,models} + webshop_repo
ROOT=/root/synthflood
mkdir -p $ROOT/data $ROOT/logs $ROOT/results $ROOT/models
cd /root

echo "=== [1/6] clone experiment repo ==="
if [ ! -d $ROOT/code/.git ]; then
  git clone https://x-access-token:$(cat /root/.pat)@github.com/MashiroRb/SynthFlood.git $ROOT/code 2>&1 | tail -1
fi
cd $ROOT/code
git config user.email "lab@synthflood.local"
git config user.name "synthflood-lab"
git log --oneline -1

ln -sfn $ROOT/code/data/contamination $ROOT/data/contamination

echo "=== [2/6] clone WebShop repo (web_agent_site module) ==="
if [ ! -d $ROOT/webshop_repo ]; then
  git clone --depth 1 https://github.com/princeton-nlp/WebShop.git $ROOT/webshop_repo 2>&1 | tail -1
fi

echo "=== [3/6] pip deps: gdown + vllm==0.19.0 ==="
pip install -q gdown 2>&1 | tail -1
pip install -q "vllm==0.19.0" 2>&1 | tail -2
pip install -q hf_transfer 2>&1 | tail -1
python3 -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.cuda.is_available())" || \
  { apt-get update -qq && apt-get install -y -qq python3-dev && pip install -q "vllm==0.19.0" 2>&1 | tail -2; }

echo "=== [4/6] official WebShop data (Google Drive) ==="
cd $ROOT/data
[ -s items_shuffle.json ]   || gdown "https://drive.google.com/uc?id=1A2whVgOO0euk5O13n2iYDM0bQRkkRduB" -O items_shuffle.json   2>&1 | tail -2
[ -s items_ins_v2.json ]    || gdown "https://drive.google.com/uc?id=1s2j6NgHljiZzQNL3veZaAiyW_qDEgBNi" -O items_ins_v2.json    2>&1 | tail -2
[ -s items_human_ins.json ] || gdown "https://drive.google.com/uc?id=14Kb5SPBk_jfdLZ_CDBNitW98QLDlKR5O" -O items_human_ins.json 2>&1 | tail -2
ls -la $ROOT/data | grep items

echo "=== [5/6] model weights: Qwen2.5-7B-Instruct ==="
HF_HUB_OFFLINE=0 HF_HUB_ENABLE_HF_TRANSFER=1 python3 - <<'EOF'
from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen2.5-7B-Instruct")
print("MODEL_AT", p)
EOF

echo "=== [6/6] smoke test ==="
cd $ROOT/code && SYNTHFLOOD_ROOT=$ROOT python3 - <<'EOF'
from synthflood.select_env import get_official_data
all_products, item_dict, prices, attrs = get_official_data()
print("OFFICIAL_OK products:", len(all_products), "by_asin:", len(item_dict))
from synthflood.select_env import build_goals
g = build_goals(n_tasks=40)
print("GOALS_OK", len(g), g[0]["instruction_text"][:60])
from synthflood.contaminate import load_pool
import os
pool = load_pool(os.path.join(os.environ.get("SYNTHFLOOD_ROOT","/root/synthflood"), "data/contamination/pool.json"))
print("POOL_OK tasks:", len(pool))
EOF

echo "SETUP_DONE"
