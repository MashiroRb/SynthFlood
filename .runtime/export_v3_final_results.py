"""Export completed frozen analysis to flat CSV; no inference or new estimators."""
import collections,csv,json,sys
from pathlib import Path
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from protocol_v3.common import OUT,validate,read
from protocol_v3.analyze import describe
validate();marker=read(OUT/'SCALED_COMPLETE.json');assert marker['validated']
A=ROOT/marker['analysis'];done=read(A/'COMPLETE.json');assert done['validated'] and done['formal_records']==189480
summary=read(A/'summary.json');assert sum(summary['counts'].values())==189480
E=A/'exports';E.mkdir(exist_ok=True)
def export(name,rows,fields):
    with (E/name).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    return dict(path=str((E/name).relative_to(ROOT)),rows=len(rows))
metrics=['planned','valid','excluded','n_independent_tasks','reward','success_rate','synthetic_choice_rate',
    'confidence_n','confidence_missing','confidence','confidence_sample_success','ece5','new_model_calls']
def flat(cell):
    value={k:cell.get(k) for k in metrics}
    value['confidence_missing']=cell['valid']-cell['confidence_n']
    return value
cells=[]
for key,cell in sorted(summary['cells'].items()):
    phase,condition=key.split('|',1)
    cells.append(dict(summary_key=key,phase=phase,condition=condition,derived=phase.endswith('_pooled'),**flat(cell)))
outputs=[export('all_condition_summary.csv',cells,['summary_key','phase','condition','derived',*metrics])]
comparisons=[]
for key,result in sorted(summary['comparisons'].items()):
    family='primary' if key in summary['primary_comparisons'] else 'direct' if key in summary['direct_comparisons'] else 'exploratory' if key in summary['exploratory_comparisons'] else 'outside_adjusted_families'
    ci=result.get('ci95') or [None,None]
    comparisons.append(dict(comparison_key=key,adjustment_family=family,ci95_low=ci[0],ci95_high=ci[1],**{k:v for k,v in result.items() if k!='ci95'}))
outputs.append(export('paired_comparisons.csv',comparisons,['comparison_key','adjustment_family','metric','n_pairs','n_tasks','effect','ci95_low','ci95_high','p','holm_p','unmatched_left','unmatched_right','invalid_or_metric_missing_pairs']))
checkpoints=[]
for key,cell in summary['cells'].items():
    if not key.startswith('exam_pooled|'):continue
    group,cp,family=key.split('|',1)[1].split(':')
    checkpoints.append(dict(group=group,checkpoint=int(cp[2:]),family=family,**flat(cell)))
assert len(checkpoints)==168
outputs.append(export('washout_all_checkpoints.csv',checkpoints,['group','checkpoint','family',*metrics]))
records=[]
for parity in (0,1):
    for phase in ('exam','shopping'):
        with (A/f'washout{parity}'/(phase+'.jsonl')).open() as stream:
            records.extend(json.loads(line) for line in stream)
assert len(records)==101760 and len({r['case_key'] for r in records})==101760
record_fields=['case_key','phase','condition','seed','task_id','rotation','family','arm','group','checkpoint','episode','k',
    'valid','purchased','exclusion_reason','chosen_kind','chosen_cid','chosen_is_synthetic','reward','gold_reward','success_full',
    'regret','confidence','input_sha256','backend_sha256','origin','source_case_key','source_result_sha256','new_model_calls','request_log']
seen=set();formal_count=0
with (E/'all_formal_records.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=record_fields,extrasaction='ignore');writer.writeheader()
    def emit(row):
        global formal_count
        assert row['case_key'] not in seen;seen.add(row['case_key'])
        writer.writerow(row);formal_count+=1
    for lane in range(8):
        for phase in ('main','probe','single','clone','defense'):
            with (A/f'worker{lane}'/(phase+'.jsonl')).open() as source:
                for line in source:emit(json.loads(line))
    for row in records:emit(row)
assert formal_count==len(seen)==189480
outputs.append(dict(path=str((E/'all_formal_records.csv').relative_to(ROOT)),rows=formal_count))
by_group=collections.defaultdict(list);by_cp=collections.defaultdict(list)
for row in records:
    by_group[(row['seed'],row['arm'],row['phase'])].append(row)
    if row['phase']=='exam':by_cp[(row['seed'],row['arm'],row['checkpoint'])].append(row)
groups=[];coverage=[]
for seed in range(2030,2038):
    for group in ('M0','B0'):
        exams=by_group[(seed,group,'exam')];shops=by_group[(seed,group,'shopping')]
        assert len(exams)==6300 and len(shops)==(80 if group=='M0' else 40)
        stat=describe(exams)
        groups.append(dict(seed=seed,group=group,shopping_planned=len(shops),shopping_valid=sum(r['valid'] for r in shops),**flat(stat)))
    for cp in range(0,41,2):
        def index(group):return {tuple(r[k] for k in ('task_id','seed','rotation','backend_sha256','family')):r for r in by_cp[(seed,group,cp)]}
        left=index('M0');right=index('B0');assert len(left)==len(right)==300
        common=left.keys()&right.keys()
        coverage.append(dict(seed=seed,checkpoint=cp,backend_matched_pairs=len(common),
            valid_purchase_pairs=sum(left[k]['valid'] and right[k]['valid'] for k in common),
            valid_confidence_pairs=sum(left[k]['valid'] and right[k]['valid'] and left[k]['confidence'] is not None and right[k]['confidence'] is not None for k in common),
            unmatched_M0=len(left.keys()-right.keys()),unmatched_B0=len(right.keys()-left.keys())))
outputs.append(export('washout_seed_group_summary.csv',groups,['seed','group','shopping_planned','shopping_valid',*metrics]))
outputs.append(export('washout_pair_coverage.csv',coverage,['seed','checkpoint','backend_matched_pairs','valid_purchase_pairs','valid_confidence_pairs','unmatched_M0','unmatched_B0']))
(E/'README.md').write_text('''# Final frozen-analysis CSV exports

All189480 formal records completed. Files export existing frozen statistics; no new inference, imputation, or estimator is introduced.

- all_condition_summary.csv: formal-condition cells plus explicitly marked derived pooled cells. Do not add derived cells to formal counts.
- paired_comparisons.csv: existing task-cluster confidence intervals, p-values and the original multiple-comparison families; missing values remain blank.
- all_formal_records.csv: all189480 unique formal case rows with raw reported confidence, purchase outcome and reuse/backend provenance; missing values remain blank. Reused records are logical conditions, not new independent samples.
- washout_all_checkpoints.csv: all21 checkpoints, both groups, all and three individual product families.
- washout_seed_group_summary.csv: all8 seeds; exam metrics exclude final purchase failures, confidence metrics require an actual valid report.
- washout_pair_coverage.csv: explicit strict same-backend pairing coverage per seed/checkpoint.

Seed2033 changed one physical4090 during its earlier host-OOM recovery. Its early M0/B0 strict-backend pairs are absent/reduced. The24GiB migrations preserved their immediately preceding hardware/backend identities. Never rewrite provenance or treat a changing paired cohort as a fixed panel.

Repeated rotations, environment seeds and exams are within-task repeats. The frozen analysis resamples/sign-flips entire tasks. B0 has no pre-exposure shopping, so a group contrast alone does not isolate pollution from general prior experience. Current exam prices remain exactly aligned with gold; the proposed75–95% revision was not applied.
''')
report=dict(validated=True,formal_records=189480,counts=summary['counts'],outputs=outputs)
(E/'COMPLETE.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
