"""Validate prepared inputs before any model calls; validate each completed run."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def validate_inputs(root):
    directory = root / "data/m1_v2"
    payload = (directory / "context.json").read_bytes()
    manifest = json.loads((directory / "manifest.json").read_text())
    if hashlib.sha256(payload).hexdigest() != manifest["context_sha256"]:
        raise ValueError("Frozen input checksum mismatch")
    critical=('m1/m1_run.py','m1/m1_memory.py','m1/replay_v2.py',
              'synthflood/agent_react.py','synthflood/select_env.py',
              'synthflood/config.py','synthflood/vllm_client.py')
    for name in critical:
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=manifest['source_sha256'][name]:
            raise ValueError(f'Inference source changed since freeze: {name}')
    if hashlib.sha256((root/'m1/slurm/run.sbatch').read_bytes()).hexdigest()!=manifest['run_script_sha256']:
        raise ValueError('Run configuration changed since freeze')
    if hashlib.sha256((root/'m1/PRE_REG_M1_V2.md').read_bytes()).hexdigest()!=manifest['protocol_sha256']:
        raise ValueError('Protocol changed since freeze')
    for name,expected in manifest['official_reward_sha256'].items():
        if hashlib.sha256((root/'.runtime/WebShop/web_agent_site/engine'/name).read_bytes()).hexdigest()!=expected:
            raise ValueError(f'Official reward source changed: {name}')
    ctx = json.loads(payload)
    if len(ctx['exam_clones']) != 38 or len(ctx['parity_clones']) != 36 or len(ctx['diagnostic_parity_clones'])!=38:
        raise ValueError("Unexpected frozen pair membership")
    exposed={goal['asin'] for goal in ctx['exposure_goals']+ctx['washout_goals']}
    for phase in ('exam','parity'):
        if any(ctx['pairs'][int(i)]['gold_asin'] in exposed for i in ctx[phase+'_clones']):
            raise ValueError('Main exam is not ASIN-disjoint from the shopping episodes')
    for seed in manifest['seeds']:
        tasks = ctx['episode_tasks'][str(seed)]
        for episode in range(20):
            clean = tasks[f'warmup_clean:{episode}']
            treated = tasks[f'warmup_treated:{episode}']
            if len(clean) != 10 or len(treated) != 10:
                raise ValueError('Candidate count mismatch')
            families = collections.Counter(c['kind'] for c in treated if c['synthetic'])
            if families != {'synthetic:clone':2, 'synthetic:geo':2, 'synthetic:reviews':2}:
                raise ValueError('Exposure family balance mismatch')
            gold_c = [(i,c) for i,c in enumerate(clean) if c['kind']=='gold']
            gold_t = [(i,c) for i,c in enumerate(treated) if c['kind']=='gold']
            if gold_c != gold_t or len(gold_c) != 1:
                raise ValueError('Gold or presentation order differs across arms')
            for a,b in zip(clean,treated):
                if not b['synthetic'] and a != b:
                    raise ValueError('Non-replaced real candidate differs')
            for c in clean+treated+tasks[f'washout:{episode}']:
                if c['item']['Price'] != f"${c['price_float']:.2f}":
                    raise ValueError('Displayed/reward price mismatch')
    for phase,factor in [('exam',.9),('parity',1.0)]:
        for pi,clone in ctx[phase+'_clones'].items():
            gold_asin=ctx['pairs'][int(pi)]['gold_asin']
            if clone['price_float'] != round(ctx['product_prices'][gold_asin]*factor,2):
                raise ValueError('Incorrect exam price factor')
            if clone['item']['options'] != ctx['by_asin'][gold_asin].get('options',{}):
                raise ValueError('Clone option term not controlled')
    print('INPUTS_VALID', manifest['context_sha256'], flush=True)


def validate_results(root, directory):
    ctx=json.loads((root/'data/m1_v2/context.json').read_text())
    rows=list(csv.DictReader((directory/'m1_exams.csv').open()))
    expected=set()
    for phase in ('exam','parity'):
        pairs=set(ctx[phase+'_clones'])
        expected.update(('PRE',phase,'-1',pi) for pi in pairs)
        expected.update((arm,phase,str(cp),pi) for arm in ('M0','B0','M2') for cp in (0,4,10,20) for pi in pairs)
    actual=[(r['arm'],r['phase'],r['checkpoint'],r['pair_idx']) for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:
        raise ValueError(f'Incomplete/duplicate exam cells: missing {len(expected-set(actual))}, extra {len(set(actual)-expected)}')
    episodes=list(csv.DictReader((directory/'m1_episodes.csv').open()))
    if len(episodes)!=120:
        raise ValueError('Expected 40 episodes in each of 3 arms')
    for arm in ('M0','B0','M2'):
        for cp in (0,4,10,20):
            snapshot=json.loads((directory/f'checkpoint_{arm}_{cp:02d}.json').read_text())
            if arm=='M2' and snapshot['injected_context']:
                raise ValueError('M2 injected memory')
    for phase in ('exam','parity'):
        cells=[{r['pair_idx']:(r['chose_clone'],r['chosen_kind'],r['purchased'],r['reward']) for r in rows if r['arm']=='M2' and r['phase']==phase and r['checkpoint']==str(cp)} for cp in (0,4,10,20)]
        pre={r['pair_idx']:(r['chose_clone'],r['chosen_kind'],r['purchased'],r['reward']) for r in rows if r['arm']=='PRE' and r['phase']==phase}
        if pre!=cells[0]:
            raise ValueError(f'PRE/M2 identical-input repeatability failure in {phase}')
        if any(cell!=cells[0] for cell in cells[1:]):
            raise ValueError(f'M2 repeatability failure in {phase}; do not interpret as washout')
    print('RESULTS_VALID', directory, flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    validate_inputs(root)
    if args.results:
        validate_results(root,args.results)
