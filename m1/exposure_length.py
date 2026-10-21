"""Continue the same pollution trajectories to 40/80 episodes, frozen exams."""
import argparse
import collections
import copy
import csv
import hashlib
import json
import os
import random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/m1_exposure_length'
OUT=ROOT/'results_m1_exposure_length'
SEEDS=list(range(2030,2038))
LENGTHS=(20,40,80)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    from expanded_parity import validate_inputs
    previous=validate_inputs()
    if (DATA/'context.json').exists():
        raise RuntimeError('Refusing to overwrite frozen length experiment')
    from m1_run import load_everything
    from synthflood.select_env import build_task
    from synthflood.contaminate import _as_candidate
    from freeze_v2 import show_price
    by_asin,prices,_,goals_by_asin=load_everything()
    ctx=read(ROOT/'data/m1_expanded/context.json')
    archived_goals=read(ROOT/'data/contamination/goals100.json')
    pool=read(ROOT/'data/contamination/pool.json')
    forbidden={q['gold_asin'] for q in previous['quality'].values()}
    forbidden|={g['asin'] for g in ctx['exposure_goals']+ctx['washout_goals']}
    candidates=[];dispositions=[]
    for index,goal in enumerate(archived_goals):
        asin=goal['asin'];reason=[]
        if asin in forbidden:
            reason.append('overlap_exam_or_previous_shopping_target')
        if asin not in by_asin or asin not in goals_by_asin:
            reason.append('no_official_goal_or_product')
        counts=collections.Counter(b['family'] for b in pool.get(str(index),[]))
        if any(counts[f]<2 for f in ('geo','clone','reviews')):
            reason.append('insufficient_archived_family_pool')
        dispositions.append({'index':index,'asin':asin,'excluded_reasons':reason})
        if not reason:
            candidates.append(index)
    if len(candidates)<60:
        raise ValueError(f'Only {len(candidates)} eligible new tasks, need60')
    selected=candidates[:60]
    new_goals=[copy.deepcopy(goals_by_asin[archived_goals[i]['asin']]) for i in selected]
    assert len({g['asin'] for g in new_goals})==60
    ctx['exposure_goals']+=new_goals
    for goal in new_goals:
        asin=goal['asin']
        ctx['by_asin'][asin]=copy.deepcopy(by_asin[asin])
        ctx['product_prices'][asin]=prices[asin]
        ctx['goals_by_asin'][asin]=goal
    for seed in SEEDS:
        tasks=ctx['episode_tasks'][str(seed)]
        for ep,source_index in enumerate(selected,start=20):
            goal=ctx['exposure_goals'][ep]
            draw=50000+ep+(seed-2027)*100000
            clean,_=build_task(goal,by_asin,0.0,[],draw,n_candidates=10)
            clean=[show_price(c) for c in clean]
            treated=copy.deepcopy(clean);synths=[]
            for family_id,family in enumerate(('geo','clone','reviews')):
                choices=[b for b in pool[str(source_index)] if b['family']==family]
                for item in random.Random(draw+family_id*1000).sample(choices,2):
                    item=copy.deepcopy(item)
                    item['options']=copy.deepcopy(by_asin[goal['asin']].get('options',{}))
                    synths.append(show_price(_as_candidate(item)))
            replace=random.Random(draw).sample(list(range(1,10)),6)
            for slot,candidate in zip(replace,synths):
                treated[slot]=candidate
            order=list(range(10));random.Random(draw+999999).shuffle(order)
            tasks[f'warmup_treated:{ep}']=[treated[i] for i in order]
            counts=collections.Counter(c['kind'] for c in treated if c['synthetic'])
            if counts!={'synthetic:geo':2,'synthetic:clone':2,'synthetic:reviews':2}:
                raise ValueError('Incorrect pollution-family allocation')
            if len(treated)!=10 or sum(c['kind']=='gold' for c in treated)!=1:
                raise ValueError('Candidate/gold count changed')
            if any(c['item']['Price']!=f"${c['price_float']:.2f}" for c in treated):
                raise ValueError('Displayed/reward price mismatch')
    # Preserve all pre-existing contexts exactly, especially the full exam.
    old=read(ROOT/'data/m1_expanded/context.json')
    for name in ('parity_clones','pairs','washout_goals'):
        assert ctx[name]==old[name]
    assert ctx['exposure_goals'][:20]==old['exposure_goals']
    for seed in SEEDS:
        for ep in range(20):
            assert ctx['episode_tasks'][str(seed)][f'warmup_treated:{ep}']==old['episode_tasks'][str(seed)][f'warmup_treated:{ep}']
    ctx['protocol']='exposure_length_new_tasks_20_40_80'
    sources=dict(previous['source_sha256'])
    additional=['m1/exposure_length.py','m1/exposure_length_summary.py','m1/EXPOSURE_LENGTH_PROTOCOL.md',
        'm1/slurm/exposure_prepare.sbatch','m1/slurm/exposure_run.sbatch','m1/slurm/exposure_summary.sbatch',
        'synthflood/contaminate.py','data/contamination/goals100.json','data/contamination/pool.json',
        'data/m1_expanded/context.json','data/m1_expanded/manifest.json']
    additional += [f'results_m1_expanded/seed{seed}/m1_exams.csv' for seed in SEEDS]
    sources.update({name:sha(ROOT/name) for name in additional})
    payload=json.dumps(ctx,sort_keys=True,ensure_ascii=False).encode()
    manifest={'seeds':SEEDS,'lengths':list(LENGTHS),'schedule':'new_goals',
        'n_pairs':previous['n_pairs'],'n_gold_asins':previous['n_gold_asins'],
        'selected_new_goal_indices':selected,'new_goal_asins':[g['asin'] for g in new_goals],
        'eligibility':dispositions,'eligible_new_tasks':len(candidates),
        'sentinel_pairs':previous['sentinel_pairs'],'quality':previous['quality'],'old36':previous['old36'],
        'context_sha256':hashlib.sha256(payload).hexdigest(),'source_sha256':sources,
        'source20':'existing exposure-end M0 snapshots and measured expanded exam results',
        'empty_reference':'existing expanded B0 clean0, validated by new sentinels',
        'new_shopping_per_seed':60,'new_full_exam_cells_per_seed':2,'new_sentinel_rows_per_seed':32}
    DATA.mkdir(parents=True,exist_ok=True)
    (DATA/'context.json').write_bytes(payload)
    (DATA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ('eligible_new_tasks','n_pairs','n_gold_asins','context_sha256')})+'\nLENGTH_PREPARED',flush=True)


def validate_inputs():
    manifest=read(DATA/'manifest.json')
    if sha(DATA/'context.json')!=manifest['context_sha256']:
        raise ValueError('Exposure length context changed')
    for name,expected in manifest['source_sha256'].items():
        if sha(ROOT/name)!=expected:
            raise ValueError(f'Frozen source changed: {name}')
    return manifest


def validate_results(directory,manifest,seed):
    rows=list(csv.DictReader((directory/'m1_exams.csv').open()))
    pairs=set(manifest['quality'])
    expected={('M0','parity',str(length),pi) for length in (40,80) for pi in pairs}
    expected|={('EMPTY_SENTINEL','sentinel',str(cp),pi) for cp in (-1,-2) for pi in manifest['sentinel_pairs']}
    keys=[(r['arm'],r['phase'],r['checkpoint'],r['pair_idx']) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected:
        raise ValueError('Incomplete/duplicate length exam cells')
    episodes=list(csv.DictReader((directory/'m1_episodes.csv').open()))
    if len(episodes)!=60 or {int(r['ep_idx']) for r in episodes}!=set(range(20,80)):
        raise ValueError('Expected exactly60 new exposure episodes')
    if any(r['arm']!='M0' or r['phase']!='exposure' for r in episodes):
        raise ValueError('Unexpected arm/phase: this study is exposure only')
    initial=read(ROOT/f'results_m1_v2/seed{seed}/checkpoint_M0_00.json')
    for length in LENGTHS:
        snapshot=read(directory/f'exposure_M0_{length:03d}.json')
        entries=snapshot['entries']
        if entries[:len(initial['entries'])]!=initial['entries']:
            raise ValueError('Original20-episode prefix changed')
        obs=[e for e in entries if e['type']=='observation']
        if len(obs)!=length or [e['t'] for e in obs]!=list(range(length)):
            raise ValueError('Unexpected memory length/timestamps')
        if sum(e['type']=='lesson' for e in entries)!=length//5:
            raise ValueError('Missing induced lesson')
    old=list(csv.DictReader((ROOT/f'results_m1_expanded/seed{seed}/m1_exams.csv').open()))
    fields=('chosen_kind','chose_clone','reward','purchased','input_sha256')
    baseline={r['pair_idx']:tuple(r[k] for k in fields) for r in old
              if r['phase']=='parity' and r['arm']=='B0' and r['checkpoint']=='0'}
    for row in rows:
        if row['phase']=='sentinel' and tuple(row[k] for k in fields)!=baseline[row['pair_idx']]:
            raise ValueError('Empty-memory sentinel differs from original expanded baseline')
    return rows


def run():
    import m1_run as runner
    from m1_memory import MemoryStore
    manifest=validate_inputs();seed=int(os.environ['M1_SEED_BASE'])
    if seed not in SEEDS:
        raise ValueError('Unplanned seed')
    directory=Path(runner.OUT)
    if (directory/'m1_exams.csv').exists() or (directory/'mem_M0.json').exists():
        raise RuntimeError('Refusing overwrite/append to existing length run')
    directory.mkdir(parents=True,exist_ok=True)
    ctx=read(DATA/'context.json')
    source=ROOT/f'results_m1_v2/seed{seed}/checkpoint_M0_00.json'
    initial=read(source)
    mem=MemoryStore(str(directory/'mem_M0.json'),'M0')
    mem.entries=copy.deepcopy(initial['entries'])
    if mem.inject_context()!=initial['injected_context']:
        raise ValueError('Initial injected text changed')
    cfg={'notes':True,'inject':True,'lessons':True,'correct':False}
    client=runner.RateClient(runner.PORT,runner.MODEL)
    def save(length):
        if sum(e['type']=='observation' for e in mem.entries)!=length or sum(e['type']=='lesson' for e in mem.entries)!=length//5:
            raise ValueError('Incomplete observation/lesson memory at checkpoint')
        snapshot=mem.export();snapshot['injected_context']=mem.inject_context()
        snapshot['initial_source']=str(source.relative_to(ROOT));snapshot['initial_source_sha256']=sha(source)
        (directory/f'exposure_M0_{length:03d}.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=1)+'\n')
    def sentinel(cp):
        runner.run_exams(ctx,'EMPTY_SENTINEL','sentinel',cp,list(map(int,manifest['sentinel_pairs'])),ctx['parity_clones'],'')
    save(20);sentinel(-1)
    for ep in range(20,80):
        runner.run_exposure_episode(ctx,'M0',cfg,ep,mem,client)
        if ep+1 in (40,80):
            save(ep+1)
            runner.run_exams(ctx,'M0','parity',ep+1,sorted(map(int,ctx['parity_clones'])),ctx['parity_clones'],mem.inject_context())
    sentinel(-2)
    rows=validate_results(directory,manifest,seed)
    (directory/'COMPLETE.json').write_text(json.dumps({'seed':seed,'validated':True,
        'new_exposure_episodes':60,'new_main_exams':2*manifest['n_pairs'],'new_sentinels':32,
        'all_rows':len(rows)},indent=2)+'\n')
    print('LENGTH_RUN_COMPLETE',seed,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','validate','run'))
    args=parser.parse_args()
    {'prepare':prepare,'validate':validate_inputs,'run':run}[args.mode]()
