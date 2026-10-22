"""Read-only audit of historical washout requests; run on a Slurm CPU node."""
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'results_m1_washout40'
SEEDS = range(2030, 2038)
CPS = range(0, 41, 2)

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def read(p):
    return json.loads(p.read_text())

PAIRS = sorted(map(int, read(ROOT / 'data/m1_washout40/manifest.json')['quality']))
assert len(PAIRS) == 452

def key(r):
    return (r['arm'], int(r['checkpoint']), int(r.get('pair_idx', r.get('pair'))), r['input_sha256'])

def csv_sig(r):
    return (r['chosen_kind'], round(float(r['reward']), 3), int(r['steps']), int(r['malformed']))

expected = Counter()
signatures = defaultdict(set)
contexts = {}
indexed = {}
checkpoints = []
lesson_ids = []
lesson_pairs = []
starts, ends = [], []
for seed in SEEDS:
    directory = BASE / f'seed{seed}'
    starts.append((directory / 'checkpoint_M0_00.json').stat().st_mtime)
    ends.append((directory / 'COMPLETE.json').stat().st_mtime)
    with (directory / 'm1_exams.csv').open() as f:
        rows = [r for r in csv.DictReader(f) if r['phase'] == 'parity']
    for r in rows:
        k = key(r)
        expected[k] += 1
        signatures[k].add(csv_sig(r))
        indexed[seed, r['arm'], int(r['checkpoint']), int(r['pair_idx'])] = r
    for cp in CPS:
        snapshots = [read(directory / f'checkpoint_{arm}_{cp:02d}.json') for arm in ('M0', 'B0')]
        for arm, s in zip(('M0', 'B0'), snapshots):
            rendered = ('Your experience notes from earlier shopping sessions:\n' + '\n'.join(f"- [{e['type']}] {e['text']}" for e in s['entries'][-3:])) if s['entries'] else ''
            assert rendered == s['injected_context']
            for pi in PAIRS:
                r = indexed[seed, arm, cp, pi]
                k = key(r)
                if k in contexts:
                    assert contexts[k] == rendered
                contexts[k] = rendered
        pairs = [(indexed[seed, 'M0', cp, pi], indexed[seed, 'B0', cp, pi]) for pi in PAIRS]
        checkpoints.append(dict(seed=seed, checkpoint=cp,
            same_context=snapshots[0]['injected_context'] == snapshots[1]['injected_context'],
            M0_entries=len(snapshots[0]['entries']), B0_entries=len(snapshots[1]['entries']),
            input_differences=sum(a['input_sha256'] != b['input_sha256'] for a,b in pairs),
            choice_differences=sum(a['chose_clone'] != b['chose_clone'] for a,b in pairs),
            outcome_differences=sum(csv_sig(a) != csv_sig(b) for a,b in pairs),
            M0_clone=sum(int(a['chose_clone']) for a,b in pairs), B0_clone=sum(int(b['chose_clone']) for a,b in pairs)))
    lessons = {}
    for arm in ('M0', 'B0'):
        lessons[arm] = [json.loads(line) for line in (directory / f'lesson_calls_{arm}.jsonl').read_text().splitlines()]
        lesson_ids.extend(x['raw']['id'] for x in lessons[arm])
    for a,b in zip(lessons['M0'], lessons['B0']):
        lesson_pairs.append(dict(seed=seed,t=a['t'], same_prompt=a['messages']==b['messages'],same_response=a['response']==b['response'],different_request_ids=a['raw']['id']!=b['raw']['id']))

with (OUT / 'checkpoints.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(checkpoints[0]));w.writeheader();w.writerows(checkpoints)
print('CSV_AND_SNAPSHOTS',len(indexed),flush=True)

found = Counter()
actual = defaultdict(set)
trajectories = defaultdict(set)
examples = {}
errors = Counter()
inodes = set()
scanned = eligible = calls = matched = 0
low, high = min(starts)-5, max(ends)+5

def load_trace(entry):
    st=entry.stat()
    if not low <= st.st_mtime <= high:
        return entry, st, None, False
    try:
        return entry, st, read(Path(entry.path)), True
    except Exception:
        return entry, st, None, True

def records():
    with os.scandir(ROOT / 'logs/runs') as entries, ThreadPoolExecutor(max_workers=8) as pool:
        iterator=(e for e in entries if e.name.endswith('.jsonl'))
        while batch:=list(islice(iterator,256)):
            yield from pool.map(load_trace,batch)

for entry, st, trace, in_window in records():
    scanned += 1
    if scanned % 20000 == 0:
        print('SCANNED',scanned,'MATCHED',matched,flush=True)
    if not in_window:
        continue
    eligible += 1
    if trace is None:
        errors['unreadable_in_time_window'] += 1
        continue
    meta = trace.get('meta', {})
    if meta.get('stage') != 'M1' or meta.get('phase') != 'parity' or meta.get('arm') not in ('M0','B0'):
        continue
    k = key(meta)
    if k not in expected:
        errors['unmatched_parity_key_in_time_window'] += 1
        continue
    found[k] += 1
    matched += 1
    inode = (st.st_dev,st.st_ino)
    if inode in inodes:
        errors['duplicate_inode'] += 1
    inodes.add(inode)
    inputs = [x for x in trace['steps'] if x['kind']=='input']
    replies = [x for x in trace['steps'] if x['kind']=='llm']
    calls += len(replies)
    if not inputs or not replies:
        errors['missing_model_input_or_output'] += 1
        continue
    first = inputs[0]['messages']
    context = contexts[k]
    if context and not first[0]['content'].endswith('\n\n'+context):
        errors['actual_memory_mismatch'] += 1
    if any(x.get('temperature')!=0 or x.get('seed')!=0 for x in inputs):
        errors['nonzero_decoding'] += 1
    if any('lat' not in x or not x.get('usage') for x in replies):
        errors['missing_call_metadata'] += 1
    s=trace['summary']
    sig=(s['chosen_kind'],round(s['reward'],3),s['steps'],s['malformed'])
    if sig not in signatures[k]:
        errors['trace_csv_outcome_mismatch'] += 1
    ih=digest(first)
    th=digest([(x['kind'], x.get('messages'), x.get('raw'), x.get('parsed')) for x in trace['steps'] if x['kind'] in ('input','llm','conf')])
    actual[k].add(ih)
    trajectories[k].add(th)
    if meta['checkpoint']==14 and meta['pair']==0:
        examples.setdefault(k,dict(path=str(Path(entry.path).relative_to(ROOT)),mtime=st.st_mtime,wall_sec=trace['wall_sec'],input_hash=ih,trajectory_hash=th,arm=meta['arm'],audit_input_hash=k[3]))
    if matched % 20000 == 0:
        print('MATCHED',matched,'SCANNED',scanned,flush=True)

rawpairs=rawsame=trajectorysame=0
for seed in SEEDS:
    for cp in CPS:
        if cp<14:
            continue
        for pi in PAIRS:
            a,b=[key(indexed[seed,arm,cp,pi]) for arm in ('M0','B0')]
            rawpairs += 1
            rawsame += bool(actual[a]) and actual[a]==actual[b] and len(actual[a])==1
            trajectorysame += bool(trajectories[a]) and trajectories[a]==trajectories[b] and len(trajectories[a])==1
permanent={}
for seed in SEEDS:
    states=[r for r in checkpoints if r['seed']==seed]
    permanent[seed]=next(r['checkpoint'] for i,r in enumerate(states) if all(x['same_context'] for x in states[i:]))
result=dict(expected_main_rows=sum(expected.values()),matched_raw_traces=sum(found.values()),
    unique_trace_inodes=len(inodes),scanned_files=scanned,time_eligible_files=eligible,
    missing_traces=sum((expected-found).values()),excess_traces=sum((found-expected).values()),
    actual_action_model_calls=calls,errors=dict(errors),
    cp14_through40_pairs=rawpairs,identical_actual_first_inputs=rawsame,
    identical_full_input_output_trajectories=trajectorysame,
    multiple_first_inputs_for_same_key=sum(len(v)>1 for v in actual.values()),
    csv_signature_conflicts=sum(len(v)>1 for v in signatures.values()),
    permanent_context_equality=permanent,
    lesson_calls=len(lesson_ids),unique_lesson_request_ids=len(set(lesson_ids)),
    lesson_pairs=lesson_pairs,evidence=list(examples.values()),
    provenance_limit='Raw episode metadata lacks seed; coverage is checked by aggregate multiplicity of (arm, checkpoint, pair, frozen input hash) within study time range, not by claiming unique per-seed trace attribution.')
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('lesson_pairs','evidence')},ensure_ascii=False,indent=2),flush=True)
