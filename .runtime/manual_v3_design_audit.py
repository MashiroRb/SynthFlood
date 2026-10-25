"""Read-only, manually invoked audit. No scheduling, model calls, or job control."""
import collections
import datetime
import gzip
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from protocol_v3.common import DATA, OUT, MODEL, REVISION, digest, read, file_sha, validate
from protocol_v3.plans import cases, key, request_definition
from protocol_v3.executor import SYSTEM, parse_details
from protocol_v3.washout import full_memory
from paired_sweep_ratingfix.common import COMMON_PROMPT, ARMS
from m1.m1_memory import LESSON_PROMPT, _extract_json

issues = []
deferred = []
checks = collections.Counter()
samples = {}
all_rows = {}
by_directory = {}
snapshots = {}
lessons_checked = 0


def check(condition, label, detail):
    checks[label] += 1
    if not condition and len(issues) < 100:
        issues.append(dict(check=label, detail=str(detail)))


def jsonlines(path):
    result = []
    if not path.exists():
        return result
    with path.open() as stream:
        for number, line in enumerate(stream, 1):
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                if not line.endswith('\n'):
                    deferred.append(f'currently writing tail: {path.name}:{number}')
                else:
                    check(False, 'complete_json_line', f'{path}:{number}')
    return result


def context(entries):
    class Notebook:
        pass
    notebook = Notebook()
    notebook.entries = entries
    return full_memory(notebook)


manifest = validate()
ownership = read(ROOT / '.runtime/scaling/scaling_manifest.json')['ownership']
check(sorted(s for seeds in ownership.values() for s in seeds) == list(range(2030, 2038)),
      'exclusive_seed_partition', ownership)
amendment = read(ROOT / '.runtime/scaling/release_routing_amendment.json')
sources = read(ROOT / '.runtime/scaling/scaling_manifest.json')['source_sha256']
sources.update(amendment['sources_sha256'])
for name, sha in sources.items():
    check(file_sha(ROOT / '.runtime/scaling' / name) == sha, 'scaling_source_hash', name)

handoff_path = ROOT / '.runtime/scaling/stateless7_control/manifest.json'
if handoff_path.exists():
    handoff = read(handoff_path)
    check(handoff['old_element'] == '150037_1' and handoff['old_job'] == 150046
          and handoff['new_lane'] == 7 and handoff['current_lane'] == 1,
          'lane7_exclusive_routing_manifest', handoff_path)
    check(handoff['frozen_manifest_sha256'] == digest(manifest), 'lane7_unchanged_frozen_inputs', handoff_path)
    for name, sha in handoff['source_sha256'].items():
        check(file_sha(ROOT / name) == sha, 'lane7_routing_source_hash', name)
    control = handoff_path.parent
    check(file_sha(control / 'original_batch.sbatch') == handoff['original_batch_sha256'],
          'lane7_original_batch_preserved', control)
    if (control / 'state.json').exists():
        state = read(control / 'state.json')
        check(state['phase'] in ('PARENT_ISOLATED','CURRENT_WORKER_FINISHED','OLD_ALLOCATION_RELEASED'),
              'lane7_legacy_launch_disabled', state)
        if state['phase'] != 'OLD_ALLOCATION_RELEASED':
            age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(state['updated_utc'])).total_seconds()
            check(age < 90, 'lane7_routing_controller_alive', age)
    check(not (control / 'ERROR.json').exists(), 'lane7_no_control_error', control)

blocks = read(DATA / 'blocks.json')
typed = read(DATA / 'typed.json')
probes = read(DATA / 'probes.json')
eligibility = read(DATA / 'eligibility_audit.json')
planned = {}
for lane in range(8):
    planned[f'worker{lane}'] = {key(c) for c in cases(blocks, typed, probes, eligibility, lane)}
    for block in blocks:
        if block['lane'] != lane:
            continue
        for k in (0, 6):
            for rotation in range(10):
                for arm in ARMS:
                    planned[f'worker{lane}'].add(key(dict(phase='defense', condition=f'{arm}:k{k}',
                        task_id=block['task_id'], seed=block['seed'], rotation=rotation)))
exams = read(DATA / 'exams.json')
shopping = read(DATA / 'washout.json')
exam_index = {(q['task_id'], q['family'], q['order']): q for q in exams}
check(len(exams) == len(exam_index) == 300, 'exam_fixed_300_pairs', len(exams))
families = collections.defaultdict(set)
for q in exams:
    families[q['task_id']].add(q['family'])
    gold = [c for c in q['candidates'] if c['kind'] == 'gold']
    synth = [c for c in q['candidates'] if c['synthetic']]
    check(len(q['candidates']) == 2 and len(gold) == len(synth) == 1,
          'exam_binary_pair', q['task_id'])
    check(gold[0]['price_float'] == synth[0]['price_float'], 'exam_price_equivalence', q['task_id'])
check(len(families) == 100 and all(v == {'geo', 'clone', 'reviews'} for v in families.values()),
      'exam_all_three_types', len(families))

for directory in sorted(OUT.iterdir()):
    if not directory.is_dir() or not directory.name.startswith(('worker', 'washout')):
        continue
    records = []
    for phase in ('main', 'probe', 'single', 'clone', 'defense', 'shopping', 'exam'):
        phase_rows = jsonlines(directory / (phase + '.jsonl'))
        for row in phase_rows:
            identity = row['case_key']
            check(identity not in all_rows, 'unique_formal_case', identity)
            all_rows[identity] = row
            check(row['phase'] == phase and key(row) == identity, 'case_identity', identity)
            budget = 6 if phase in ('exam', 'probe') else 30
            trajectory = row['trajectory']
            views = illegal = purchases = 0
            for i, event in enumerate(trajectory):
                action, error, warnings = parse_details(event['response'], row['candidate_count'], budget - views)
                check(bool(error) == (not event['executed']), 'raw_response_execution', identity)
                if error:
                    illegal += 1
                else:
                    act, index, confidence = action
                    check(event['action'] == f'{act}[{index}]', 'executed_action', identity)
                    views += act == 'view'
                    purchases += act == 'select'
                    check(not purchases or i == len(trajectory) - 1, 'purchase_terminates', identity)
                    if act == 'select':
                        check(confidence == row['confidence'], 'confidence_from_raw_response', identity)
                        check(row['chosen_position'] == index and row['chosen_cid'] == row['candidate_ids'][index - 1],
                              'chosen_candidate_matches_action', identity)
                check(event['remaining_views'] == budget - views, 'remaining_budget', identity)
            check(0 <= views <= budget and illegal <= 4 and views == row['effective_views']
                  and illegal == row['malformed'], 'budget_and_cumulative_retries', identity)
            check(row['valid'] == row['purchased'] == (purchases == 1), 'valid_means_purchase', identity)
            if row['valid']:
                check(isinstance(row['reward'], (int, float)) and math.isfinite(row['reward'])
                      and 0 <= row['reward'] <= 1, 'finite_purchase_reward', identity)
            else:
                check(all(row.get(f) is None for f in ('reward', 'success_full', 'success80', 'chosen_cid', 'regret')),
                      'failure_excluded_without_imputation', identity)
            check(row['confidence'] is None or (math.isfinite(row['confidence']) and 0 <= row['confidence'] <= 1),
                  'finite_confidence_or_missing', identity)
            check(row['candidate_count'] == len(set(row['candidate_ids'])), 'distinct_candidates', identity)
            if directory.name.startswith('worker'):
                check(identity in planned[directory.name], 'stateless_case_in_frozen_plan', identity)
            else:
                check(row['seed'] in ownership[directory.name], 'row_seed_owned_by_writer', identity)
            if row['origin'] == 'new':
                check(row['new_model_calls'] == len(trajectory) == len(row['request_sha256']),
                      'model_call_accounting', identity)
                check(digest(row['request_sha256']) == row['request_sequence_sha256'], 'request_sequence_hash', identity)
            records.append(row)
        if phase_rows:
            for row in (phase_rows[0], phase_rows[-1]):
                if row['origin'] == 'new':
                    samples[row['case_key']] = row
    by_directory[directory.name] = records
    defense_plan = directory / 'DEFENSE_PLAN_FROZEN.json'
    if any(r['phase'] == 'defense' for r in records):
        check(defense_plan.exists(), 'defense_plan_frozen_before_purchases', directory.name)
        if defense_plan.exists():
            frozen = read(defense_plan)
            index = {p['case_key']: p['definition_sha256'] for p in frozen['plans']}
            check(file_sha(directory / 'detector_requests.jsonl.gz') == frozen['detector_log_sha256'],
                  'frozen_detector_requests', directory.name)
            for row in records:
                if row['phase'] == 'defense':
                    check(row['input_sha256'] == index.get(row['case_key']), 'defense_matches_frozen_plan', row['case_key'])

for identity, row in all_rows.items():
    if row['origin'] != 'new':
        source = all_rows.get(row['source_case_key'])
        check(source is not None, 'reuse_has_retained_source', identity)
        if source is not None:
            check(source['origin'] == 'new' and source['input_sha256'] == row['input_sha256']
                  and source['backend_sha256'] == row['backend_sha256'] and digest(source) == row['source_result_sha256'],
                  'reuse_exact_input_backend_and_source_hash', identity)
        check(row['new_model_calls'] == 0, 'reuse_adds_no_model_calls', identity)

for name, seeds in ownership.items():
    directory = OUT / name
    records = by_directory.get(name, [])
    for seed in seeds:
        for group in ('M0', 'B0'):
            base = directory / f'seed{seed}'
            memory_path = base / f'memory_{group}.json'
            entries = read(memory_path)['entries'] if memory_path.exists() else []
            observations = [e for e in entries if e['type'] == 'observation']
            n = len(observations)
            expected = [('observation', t) for t in range(1, n + 1)]
            expected = [(kind, t) for _, t in expected for kind in (('observation', 'lesson') if t % 5 == 0 else ('observation',))]
            check([(e['type'], e['t']) for e in entries] == expected, 'memory_exact_observation_lesson_order', f'{name}:{seed}:{group}')
            check(n <= (80 if group == 'M0' else 40) and all(e['arm'] == group for e in entries),
                  'memory_group_and_length', f'{name}:{seed}:{group}')
            shops = {r['episode']: r for r in records if r['phase'] == 'shopping' and r['seed'] == seed and r['arm'] == group}
            for e in observations:
                row = shops.get(e['t'])
                if row is None:
                    deferred.append(f'memory advanced after row snapshot: {name}:{seed}:{group}:{e["t"]}')
                else:
                    check(e['data']['reward'] == row['reward'] and e['data']['gold_reward'] == row['gold_reward'],
                          'observation_matches_shopping_only', row['case_key'])
            for lesson in jsonlines(base / f'lesson_calls_{group}.jsonl'):
                t = lesson['t']
                recent = [e for e in entries if e['type'] == 'observation' and e['t'] <= t][-5:]
                if len(recent) < 5:
                    deferred.append(f'lesson ahead of memory snapshot: {name}:{seed}:{group}:{t}')
                    continue
                messages = [dict(role='user', content=LESSON_PROMPT.format(notes='\n'.join(f'- {e["text"]}' for e in recent)))]
                check(t % 5 == 0 and lesson['messages'] == messages and lesson['temperature'] == 0
                      and lesson['seed'] == seed * 10000 + t and lesson['max_tokens'] == 160,
                      'lesson_only_last_five_shops', f'{name}:{seed}:{group}:{t}')
                lessons_checked += 1
            for path in sorted(base.glob(f'checkpoint_{group}_*.json')):
                cp = int(path.stem.rsplit('_', 1)[1])
                snapshot = read(path)
                size = (40 if group == 'M0' else 0) + cp
                expected_entries = [e for e in entries if e['t'] <= size]
                check(cp in range(0, 41, 2) and snapshot['entries'] == expected_entries,
                      'checkpoint_full_memory_no_exam_entries', path)
                injected = context(snapshot['entries'])
                check(snapshot['injected_context'] == injected and snapshot['context_sha256'] == digest(injected),
                      'checkpoint_full_context_hash', path)
                check(sum(e['type'] == 'observation' for e in snapshot['entries']) == size
                      and sum(e['type'] == 'lesson' for e in snapshot['entries']) == size // 5,
                      'checkpoint_expected_memory_counts', path)
                snapshots[(name, seed, group, cp)] = injected
            selected = [r for r in records if r['seed'] == seed and r['arm'] == group]
            last_sample = set()
            for row in selected:
                if row['phase'] == 'exam':
                    cp = row['checkpoint']
                    memory = snapshots.get((name, seed, group, cp))
                    q = exam_index.get((row['task_id'], row['family'], row['rotation']))
                    check(q is not None and row['condition'] == f'{group}:cp{cp}:{row["family"]}', 'exam_fixed_question_identity', row['case_key'])
                    if memory is None:
                        deferred.append('checkpoint not in snapshot: ' + row['case_key'])
                        continue
                    plan = q
                    bucket = cp
                else:
                    t = row['episode']
                    pollution = group == 'M0' and t <= 40
                    plan = shopping[str(seed)]['pollution' if pollution else 'clean'][t - 1 if pollution or group == 'B0' else t - 41]
                    check(row['task_id'] == plan['task_id'] and row['rotation'] == plan['rotation']
                          and row['condition'] == f'{group}:{"pollution" if pollution else "clean"}',
                          'shopping_frozen_plan_and_order', row['case_key'])
                    memory = context([e for e in entries if e['t'] < t])
                    bucket = ('shop', t)
                case = {**row, 'block': dict(goal=plan['goal'])}
                check(digest(request_definition(case, plan['candidates'], COMMON_PROMPT, memory)) == row['input_sha256'],
                      'washout_exact_frozen_request_and_full_memory', row['case_key'])
                if row['origin'] == 'new' and bucket not in last_sample:
                    samples[row['case_key']] = row
                    last_sample.add(bucket)

for identity, row in samples.items():
    path = ROOT / row['request_log']
    archived = []
    try:
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                archived.append(json.loads(line))
    except (EOFError, OSError, json.JSONDecodeError) as error:
        check(False, 'completed_case_request_archive_readable', f'{identity}:{error}')
        continue
    check(len(archived) == len(row['trajectory']), 'complete_request_archive', identity)
    for i, record in enumerate(archived):
        payload = record['request']
        check('error' not in record and 'response' in record, 'successful_request_has_response', identity)
        check(digest(payload) == record['request_sha256'] == row['request_sha256'][i], 'actual_request_hash', identity)
        check(payload['model'] == MODEL and payload['revision'] == REVISION and payload['temperature'] == 0
              and payload['seed'] == 0 and payload['max_tokens'] == 300, 'actual_sampling_model_settings', identity)
        limit = 131072 if row['phase'] in ('shopping', 'exam') else 65536
        check(record['context_limit'] == limit and record['prompt_tokens'] + record['output_reserve'] <= limit,
              'actual_context_with_output_reserve', identity)
        check(record['response_text'] == row['trajectory'][i]['response'], 'response_archive_matches_trajectory', identity)
        system = payload['messages'][0]['content']
        if row['phase'] == 'exam':
            directory = next(name for name, seeds in ownership.items() if row['seed'] in seeds)
            memory = snapshots[(directory, row['seed'], row['arm'], row['checkpoint'])]
            check(system == SYSTEM + '\n' + COMMON_PROMPT + '\n' + memory, 'actual_exam_injects_full_checkpoint', identity)
        if i == 0:
            check([m['role'] for m in payload['messages']] == ['system', 'user'],
                  'fresh_dialogue_per_question', identity)
        elif i - 1 < len(archived):
            previous = archived[i - 1]['request']['messages']
            check(payload['messages'][:len(previous)] == previous and len(payload['messages']) == len(previous) + 2,
                  'within_question_history_retained', identity)

log_findings = []
patterns = re.compile(r'Traceback|\bERROR\b|OutOfMemory|CUDA error|EngineDead|context_overflow|\bFAILED\b|RuntimeError|\bException\b')
log_paths = list(OUT.glob('worker*/server.log')) + list(OUT.glob('washout*/server.log'))
for glob in ('v3-stateless-150037*', 'v3-stateless-150038*', 'v3-stateless7-150478.log',
             'v3-lane7-handoff-150477.log', 'v3-washout-150039*', 'v3-continue-150294.log',
             'v3-continue-150298.log', 'v3-extra-150292_*.log', 'v3-washout24-151018.log',
             'v3-washout24-151012.log', 'v3-scaled-analysis-151032.log'):
    log_paths += list((ROOT / '.runtime/slurm').glob(glob))
for path in sorted(set(log_paths)):
    with path.open(errors='replace') as stream:
        for number, line in enumerate(stream, 1):
            if patterns.search(line):
                log_findings.append(dict(path=str(path.relative_to(ROOT)), line=number, text=line.rstrip()[:500]))
failures = [str(p.relative_to(ROOT)) for p in OUT.glob('*/FAILED.json')]
timestamp = datetime.datetime.now(datetime.timezone.utc)
report = dict(timestamp_utc=timestamp.isoformat(), frozen_hashes_valid=True,
    rows=len(all_rows), rows_by_directory={k:len(v) for k,v in by_directory.items()},
    ownership=ownership, checks=dict(checks), sampled_complete_cases=len(samples),
    lessons_checked=lessons_checked, issues=issues, deferred_concurrent_writes=deferred,
    log_files_scanned=len(set(log_paths)), log_findings=log_findings[:100], failures=failures)
target = ROOT / '.runtime/v3_manual_checks'
target.mkdir(exist_ok=True)
(target / ('design_' + timestamp.strftime('%Y%m%dT%H%M%SZ') + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(target / 'design_latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
