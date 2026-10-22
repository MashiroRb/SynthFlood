"""One persistent GPU service per lane; main then globally gated defense."""
import argparse
import collections
import copy
import gzip
import json
import math
import os
import time
import traceback

from .common import DATA, OUT, ROOT, COUNTS, ROTATIONS, ARMS, MODEL, REVISION
from .common import candidates, case_key, digest, file_sha, read, write, load_lane, validate_sources
from .defenses import transform, _page_text


def read_rows(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def read_worker(lane, phase):
    return read_rows(OUT / f'worker{lane}' / f'{phase}.jsonl')


def append(path, value):
    with path.open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()


def input_hash(block, final, extra):
    return digest({'goal': block['goal'], 'candidates': final, 'sys_extra': extra,
        'defense_prompt': 'none', 'model': MODEL, 'revision': REVISION,
        'temperature': 0, 'seed': 0, 'max_steps': 10, 'max_tokens': 300})


def freeze_plans(lane, blocks, directory, client_factory):
    # Text scores precede ALL defense purchases and are never tuned to outcomes.
    scores = {}
    with gzip.open(directory / 'detector_requests.jsonl.gz', 'wt') as scorelog:
        for block in blocks:
            local = {}
            for c in block['base'] + block['synthetics']:
                text = _page_text(c)[:3000]
                key = digest(text)
                if key not in scores:
                    client = client_factory()
                    ppl, count = client.perplexity(text)
                    if not math.isfinite(ppl) or count <= 0:
                        raise ValueError('Invalid perplexity score; refusing silent filtering fallback')
                    scores[key] = {'ppl': ppl, 'n_logprobs': count, 'text_sha256': key}
                    scorelog.write(json.dumps({'text': text, **scores[key]}, ensure_ascii=False) + '\n')
                local[c['cid']] = scores[key]
            write(directory / f"ppl_{block['seed']}_{block['task_id']}.json", local)
    plans = []
    for block in blocks:
        ppl = read(directory / f"ppl_{block['seed']}_{block['task_id']}.json")
        keys = [((k, rotation, arm), case_key(block, k, rotation, arm))
            for k in (0, 6) for rotation in ROTATIONS for arm in ARMS]
        from .common import rng
        rng('defense_call_order', block['seed'], block['task_id']).shuffle(keys)
        for (k, rotation, arm), key in keys:
            raw = candidates(block, k, rotation)
            final, extra, metadata = transform(block, raw, k, rotation, arm, ppl)
            if any(c['item'].get('options') != next(x for x in raw if x['cid'] == c['cid'])['item'].get('options') for c in final):
                raise ValueError('Defense changed options')
            plans.append({'case_key': key, 'seed': block['seed'], 'task_id': block['task_id'],
                'k': k, 'rotation': rotation, 'arm': arm, 'pre_sha256': digest(raw),
                'post_sha256': input_hash(block, final, extra), 'ids': [c['cid'] for c in final],
                'badges': [c['cid'] for c in final if c.get('prov_badge')], 'metadata': metadata})
    path = directory / 'defense_plan.jsonl'
    with path.open('w') as stream:
        for plan in plans:
            stream.write(json.dumps(plan, ensure_ascii=False, allow_nan=False) + '\n')
    write(directory / 'DEFENSE_PLAN_FROZEN.json', {'lane': lane, 'rows': len(plans),
        'sha256': file_sha(path), 'score_files_sha256': {p.name: file_sha(p) for p in directory.glob('ppl_*.json')}})
    return plans


def validate_lane(lane, phase):
    manifest, blocks = load_lane(lane)
    lookup = {(b['seed'], b['task_id']): b for b in blocks}
    rows = read_worker(lane, phase)
    arms = ('none',) if phase == 'main' else ARMS
    ks = COUNTS if phase == 'main' else (0, 6)
    expected = {case_key(b, k, r, a) for b in blocks for k in ks for r in ROTATIONS for a in arms}
    keys = [r['case_key'] for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError(f'Incomplete/duplicate {phase} lane{lane}: {len(keys)}/{len(expected)}')
    hashes = collections.defaultdict(set)
    for row in rows:
        block = lookup[row['seed'], row['task_id']]
        raw = candidates(block, row['k'], row['rotation'])
        if row['pre_sha256'] != digest(raw):
            raise ValueError('Unpaired defense/main input')
        if row['chosen_cid'] is not None:
            expected_reward = block['reward_by_cid'][row['chosen_cid']]
            if abs(row['reward'] - expected_reward) > 1e-9:
                raise ValueError('Frozen and runtime scoring disagree')
        elif row['reward'] != 0:
            raise ValueError('Non-purchase has nonzero reward')
        hashes[row['post_sha256']].add((row['chosen_cid'], row['reward'], row['confidence'], row['purchased']))
    if any(len(v) > 1 for v in hashes.values()):
        raise ValueError('Identical complete inputs have inconsistent outcomes')
    if phase == 'defense':
        freeze = read(OUT / f'worker{lane}' / 'DEFENSE_PLAN_FROZEN.json')
        if file_sha(OUT / f'worker{lane}' / 'defense_plan.jsonl') != freeze['sha256']:
            raise ValueError('Frozen defense plan changed')
        plans = {p['case_key']: p for p in read_rows(OUT / f'worker{lane}' / 'defense_plan.jsonl')}
        for row in rows:
            plan = plans[row['case_key']]
            if row['post_sha256'] != plan['post_sha256'] or row['post_ids'] != plan['ids'] or row['badges'] != plan['badges']:
                raise ValueError('Runtime defense input differs from frozen plan')
    return rows


def run(lane):
    from synthflood.agent_react import run_episode
    from synthflood.select_env import SelectEnv
    from synthflood.vllm_client import LLMClient
    manifest, blocks = load_lane(lane)
    directory = OUT / f'worker{lane}'
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / 'main.jsonl').exists():
        raise RuntimeError('Existing worker results; refusing overwrite or uncontrolled resume')
    logdir = directory / 'requests'; logdir.mkdir(exist_ok=True)
    hardware = read(directory / 'hardware.json')
    backend = {'gpu': hardware, 'revision': REVISION, 'serving': 'vllm0.8.1-bf16-eager-serial-16384-no-prefix'}
    backend_sha = digest(backend)
    write(directory / 'backend.json', backend)
    cache = {}; sentinel_cases = []
    def client_factory():
        return LLMClient(8000, MODEL)
    def evaluate(block, k, rotation, arm, phase, final, extra, metadata, force=False):
        key = case_key(block, k, rotation, arm)
        raw = candidates(block, k, rotation)
        post_hash = input_hash(block, final, extra)
        reused = cache.get(post_hash) if not force else None
        result = {'case_key': key, 'phase': phase, 'seed': block['seed'], 'task_id': block['task_id'],
            'k': k, 'rotation': rotation, 'arm': arm, 'pre_sha256': digest(raw), 'post_sha256': post_hash,
            'backend_sha256': backend_sha, 'post_ids': [c['cid'] for c in final],
            'badges': [c['cid'] for c in final if c.get('prov_badge')], 'defense_metadata': metadata,
            'n_candidates_after': len(final), 'gold_reward': block['gold_reward']}
        if reused is not None:
            for field in ('reward','success_full','success80','chosen_kind','chosen_is_synthetic','chosen_position',
                'steps','malformed','confidence','purchased','chosen_cid'):
                result[field] = reused[field]
            result.update(origin='reused_main' if reused['phase'] == 'main' else 'reused_defense',
                source_case_key=reused['case_key'], new_model_calls=0, request_log=reused['request_log'])
        else:
            suffix = f'sentinel{len(read_rows(directory / "sentinels.jsonl"))}' if force else phase
            logfile = logdir / (key.replace(':','_') + f'_{suffix}.jsonl')
            env = SelectEnv(block['goal'], copy.deepcopy(final), n_candidates=len(final))
            client = client_factory()
            summary = run_episode(env, client, block['goal']['instruction_text'], defense='none',
                max_steps=10, sys_extra=extra, log_path=str(logfile),
                meta={'protocol':'paired_n98_v1', 'case_key':key, 'phase':phase,
                    'pre_sha256':result['pre_sha256'], 'post_sha256':post_hash, 'backend_sha256':backend_sha})
            confidence = summary['confidence']
            if confidence is not None and (not math.isfinite(confidence) or not 0 <= confidence <= 1):
                confidence = None
            for field in ('reward','success_full','success80','chosen_kind','chosen_is_synthetic',
                'chosen_position','steps','malformed'):
                result[field] = summary[field]
            result.update(confidence=confidence, purchased=bool(env.done),
                chosen_cid=env.chosen['cid'] if env.chosen else None, origin='new', source_case_key=None,
                new_model_calls=client.calls)
            with logfile.open('rb') as source, gzip.open(str(logfile)+'.gz','wb') as target:
                target.write(source.read())
            logfile.unlink()
            result['request_log'] = str(logfile.relative_to(ROOT)) + '.gz'
            if not force:
                cache[post_hash] = result
        if force:
            reference = cache[post_hash]
            fields = ('reward','chosen_cid','confidence','purchased')
            if any(result[f] != reference[f] for f in fields):
                raise ValueError(f'Repeatability sentinel failed: {key}')
            result['source_case_key'] = reference['case_key']
            append(directory / 'sentinels.jsonl', result)
        else:
            append(directory / f'{phase}.jsonl', result)
        return result
    def sentinels():
        for block, k, rotation in sentinel_cases:
            raw = candidates(block, k, rotation)
            final, extra, meta = transform(block, raw, k, rotation, 'none', {})
            evaluate(block, k, rotation, 'none', 'sentinel', final, extra, meta, force=True)
    main_cases = [(b,k,r) for b in blocks for k in COUNTS for r in ROTATIONS]
    from .common import rng
    rng('main_call_order', lane, 2027).shuffle(main_cases)
    for index, (block,k,rotation) in enumerate(main_cases):
        if (OUT / 'FAILED.json').exists():
            raise RuntimeError('Another worker failed')
        raw = candidates(block, k, rotation)
        final, extra, meta = transform(block, raw, k, rotation, 'none', {})
        evaluate(block, k, rotation, 'none', 'main', final, extra, meta)
        if index < 4:
            sentinel_cases.append((block,k,rotation))
        if index == 3:
            sentinels()
        if (index+1) % 20 == 0:
            print('MAIN_PROGRESS', lane, index+1, '/', len(main_cases), flush=True)
    sentinels(); validate_lane(lane, 'main')
    write(directory / 'MAIN_COMPLETE.json', {'lane':lane,'validated':True,'rows':len(main_cases),'backend_sha256':backend_sha})
    print('WAIT_MAIN_BARRIER', lane, flush=True)
    while not (OUT / 'DEFENSE_READY.json').exists():
        if (OUT / 'FAILED.json').exists():
            raise RuntimeError('Global main validation failed')
        time.sleep(15)
    barrier = read(OUT / 'DEFENSE_READY.json')
    if barrier['manifest_sha256'] != file_sha(DATA / 'manifest.json'):
        raise ValueError('Wrong main barrier')
    sentinels()
    plans = freeze_plans(lane, blocks, directory, client_factory)
    lookup = {(b['seed'],b['task_id']):b for b in blocks}
    ppl_cache = {(b['seed'],b['task_id']):read(directory/f"ppl_{b['seed']}_{b['task_id']}.json") for b in blocks}
    for index, plan in enumerate(plans):
        if (OUT / 'FAILED.json').exists():
            raise RuntimeError('Another worker failed')
        block = lookup[plan['seed'],plan['task_id']]
        k,r,arm = plan['k'],plan['rotation'],plan['arm']
        raw = candidates(block,k,r)
        final,extra,meta = transform(block,raw,k,r,arm,ppl_cache[block['seed'],block['task_id']])
        if input_hash(block,final,extra) != plan['post_sha256']:
            raise ValueError('Defense plan mismatch before model call')
        evaluate(block,k,r,arm,'defense',final,extra,meta)
        if (index+1) % 100 == 0:
            print('DEFENSE_PROGRESS',lane,index+1,'/',len(plans),flush=True)
    sentinels(); validate_lane(lane,'defense'); validate_sources()
    write(directory / 'COMPLETE.json', {'lane':lane,'validated':True,'main_rows':len(main_cases),
        'defense_rows':len(plans),'backend_sha256':backend_sha})
    print('PAIRED_WORKER_COMPLETE',lane,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('lane',type=int)
    lane = parser.parse_args().lane
    try:
        run(lane)
    except Exception as error:
        OUT.mkdir(parents=True,exist_ok=True)
        write(OUT / 'FAILED.json', {'lane':lane,'error':repr(error),'traceback':traceback.format_exc()})
        raise
