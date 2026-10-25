import copy
import json
from pathlib import Path

from paired_sweep_ratingfix.common import MODEL, REVISION, ARMS, digest, file_sha, read, write, rng, uniform

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/protocol_v3_20261024_relaxed_v1'
OUT = ROOT / 'results_protocol_v3_20261024_relaxed_v1'
OLD_DATA = ROOT / 'data/protocol_v3_20261023'
PARENT = ROOT / 'data/paired_n98_ratingfix_v2'
MODEL_PATH = Path('/mnt/beegfs/home/liudianru26/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots') / REVISION
FAMILIES = ('geo', 'clone', 'reviews')
SEEDS = tuple(range(2030, 2038))
CONTEXT = 131072
STATELESS_CONTEXT = 65536


def append(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')


def rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def source_hashes():
    paths = list((ROOT / 'protocol_v3').rglob('*.py')) + list((ROOT / 'protocol_v3').rglob('*.sh'))
    paths += list((ROOT / 'protocol_v3').rglob('*.sbatch')) + list((ROOT / 'protocol_v3').glob('*.md'))
    paths += [ROOT / 'synthflood' / name for name in ('select_env.py', 'product_metadata.py',
        'ws_loader.py', 'contaminate.py', 'defenses.py', 'agent_react.py', 'config.py', 'vllm_client.py', 'runlog.py', 'metrics.py')]
    paths += [ROOT / 'paired_sweep_ratingfix' / name for name in ('common.py', 'defenses.py')]
    paths += [ROOT / 'paired_sweep/freeze.py', ROOT / 'paired_sweep/common.py', ROOT / 'm1/m1_memory.py', ROOT / 'm1/server_ready.py']
    paths += [ROOT / '.runtime/WebShop/web_agent_site/engine' / name for name in ('goal.py', 'normalize.py')]
    return {str(p.relative_to(ROOT)): file_sha(p) for p in sorted(set(paths))}


def validate():
    manifest = read(DATA / 'manifest.json')
    for name, sha in manifest['source_sha256'].items():
        if file_sha(ROOT / name) != sha:
            raise ValueError('Frozen source changed: ' + name)
    for name, sha in manifest['inputs_sha256'].items():
        if file_sha(DATA / name) != sha:
            raise ValueError('Frozen input changed: ' + name)
    return manifest


def rotate(items, offset):
    return copy.deepcopy(items[offset:] + items[:offset])


def replace(block, synths, offset):
    items = copy.deepcopy(block['base'])
    for slot, candidate in zip(block['replace_order'], synths):
        items[slot] = copy.deepcopy(candidate)
    return rotate(items, offset)
