"""One-shot summaries of complete seeds/groups, with explicit completeness gates."""
import argparse
import collections
import csv
import datetime
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from protocol_v3.common import DATA, OUT, read, digest, validate, ARMS
from protocol_v3.plans import key, cases
from protocol_v3.analyze import describe

parser = argparse.ArgumentParser()
parser.add_argument('--include-complete-groups', action='store_true')
args = parser.parse_args()
manifest = validate()
ownership = read(ROOT / '.runtime/scaling/scaling_manifest.json')['ownership']
exams = read(DATA / 'exams.json')
shopping = read(DATA / 'washout.json')
timestamp = datetime.datetime.now(datetime.timezone.utc)
directory = ROOT / '.runtime/v3_seed_summaries' / timestamp.strftime('%Y%m%dT%H%M%SZ')
directory.mkdir(parents=True)
inventory = []
complete_seeds = []
reports = []
experiment_inventory = []
complete_experiments = []


def load_rows(path):
    if not path.exists():
        return []
    records = []
    with path.open() as stream:
        for line in stream:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                if line.endswith('\n'):
                    raise
    return records


def fmt(value, percent=False):
    if value is None:
        return '缺失'
    return f'{value:.2%}' if percent else f'{value:.4f}'


def summary_rows(records):
    result = describe(records)
    result['purchase_failure_rate'] = result['excluded'] / max(1, len(records))
    result['confidence_missing'] = result['valid'] - result['confidence_n']
    if not result['confidence_n']:
        result['ece5'] = None
    return result


for name, seeds in ownership.items():
    source = OUT / name
    records = load_rows(source / 'shopping.jsonl') + load_rows(source / 'exam.jsonl')
    identities = [r['case_key'] for r in records]
    assert len(set(identities)) == len(identities), f'Duplicate cases in {name}'
    for seed in seeds:
        groups = {}
        seed_records = [r for r in records if r['seed'] == seed]
        for group in ('M0', 'B0'):
            chosen = [r for r in seed_records if r['arm'] == group]
            expected = set()
            for cp in range(0, 41, 2):
                for q in exams:
                    expected.add(key(dict(phase='exam', condition=f'{group}:cp{cp}:{q["family"]}',
                        task_id=q['task_id'], seed=seed, rotation=q['order'])))
            for phase in (('pollution', 'clean') if group == 'M0' else ('clean',)):
                for plan in shopping[str(seed)][phase]:
                    expected.add(key(dict(phase='shopping', condition=f'{group}:{phase}',
                        task_id=plan['task_id'], seed=seed, rotation=plan['rotation'])))
            actual = {r['case_key'] for r in chosen}
            assert actual <= expected, f'Unexpected cases {name}:{seed}:{group}'
            done = actual == expected
            n_exam = sum(r['phase'] == 'exam' for r in chosen)
            completed_cps = [cp for cp in range(0, 41, 2)
                if sum(r['phase'] == 'exam' and r['checkpoint'] == cp for r in chosen) == 300]
            if done:
                memory = read(source / f'seed{seed}' / f'memory_{group}.json')['entries']
                assert sum(e['type'] == 'observation' for e in memory) == (80 if group == 'M0' else 40)
                assert sum(e['type'] == 'lesson' for e in memory) == (16 if group == 'M0' else 8)
                checkpoint = read(source / f'seed{seed}' / f'checkpoint_{group}_40.json')
                assert checkpoint['entries'] == memory
            info = dict(group=group, complete=done, rows=len(chosen), planned_rows=len(expected),
                exam_rows=n_exam, shopping_rows=len(chosen)-n_exam, completed_checkpoints=completed_cps)
            groups[group] = dict(info=info, records=chosen)
        full = all(v['info']['complete'] for v in groups.values())
        inventory.append(dict(seed=seed, directory=name, complete=full,
            groups={g:v['info'] for g,v in groups.items()}))
        if full:
            complete_seeds.append(seed)
        targets = ('M0', 'B0') if full else tuple(g for g,v in groups.items()
            if args.include_complete_groups and v['info']['complete'])
        if not targets:
            continue
        report = dict(seed=seed, scope='complete_seed' if full else 'complete_group_only',
            complete_seed=full, source_directory=name, timestamp_utc=timestamp.isoformat(),
            manifest_sha256=digest(manifest), groups={})
        for group in targets:
            chosen = groups[group]['records']
            shops = [r for r in chosen if r['phase'] == 'shopping']
            questions = [r for r in chosen if r['phase'] == 'exam']
            cells = {}
            for cp in range(0, 41, 2):
                for family in ('all', 'geo', 'clone', 'reviews'):
                    cell = [r for r in questions if r['checkpoint'] == cp and (family == 'all' or r['family'] == family)]
                    assert len(cell) == (300 if family == 'all' else 100)
                    cells[f'cp{cp}:{family}'] = summary_rows(cell)
            report['groups'][group] = dict(shopping={phase:summary_rows([r for r in shops
                if r['condition'] == f'{group}:{phase}']) for phase in ('pollution', 'clean')
                if any(r['condition'] == f'{group}:{phase}' for r in shops)},
                exam_all=summary_rows(questions), checkpoints=cells)
        if full:
            comparisons = {}
            for cp in range(0, 41, 2):
                for family in ('all', 'geo', 'clone', 'reviews'):
                    indexes = []
                    for group in ('M0', 'B0'):
                        subset = [r for r in groups[group]['records'] if r['phase'] == 'exam'
                            and r['checkpoint'] == cp and (family == 'all' or r['family'] == family)]
                        index = {tuple(r[k] for k in ('task_id','seed','rotation','backend_sha256','family')):r for r in subset}
                        assert len(index) == len(subset)
                        indexes.append(index)
                    common = indexes[0].keys() & indexes[1].keys()
                    metrics = {}
                    for metric in ('reward','success_full','chosen_is_synthetic','confidence','regret'):
                        differences = [float(indexes[0][k][metric])-float(indexes[1][k][metric])
                            for k in common if all(ix[k]['valid'] and ix[k].get(metric) is not None for ix in indexes)]
                        metrics[metric] = dict(n_pairs=len(differences),M0_minus_B0=sum(differences)/len(differences) if differences else None)
                    comparisons[f'cp{cp}:{family}'] = metrics
            report['paired_M0_minus_B0'] = comparisons
        (directory / f'seed{seed}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        lines = [f'# Seed {seed} 汇总', '',
            ('M0、B0两组均完整完成。' if full else '阶段性汇总：仅下列组完整完成；另一组未完成，不能解释为完整seed或两组对照结论。'), '',
            '失败购买从奖励、成功率、合成选择率分子和分母中排除；confidence与ECE仅使用有效报告。重复考试为同100目标任务，不能视为6300个独立任务。单seed结果仅供阶段性描述。', '',
            '实际每2轮考试一次：0、2、…、40，共21个检查点。下表仅摘录0、10、20、30、40；同目录CSV和趋势图包含全部检查点。', '',
            '|组|检查点|有效/计划|平均奖励|完全满足要求|合成选择率|平均confidence|有效confidence数|ECE5|',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for group, values in report['groups'].items():
            for cp in (0, 10, 20, 30, 40):
                cell = values['checkpoints'][f'cp{cp}:all']
                lines.append(f'|{group}|{cp}|{cell["valid"]}/{cell["planned"]}|{fmt(cell["reward"])}|{fmt(cell["success_rate"],True)}|{fmt(cell["synthetic_choice_rate"],True)}|{fmt(cell["confidence"])}|{cell["confidence_n"]}|{fmt(cell["ece5"])}|')
        if full:
            lines += ['', '同题配对差值 M0−B0，仅使用双方均完成购买的配对；confidence还要求双方报告有效。', '',
                '|检查点|奖励差|有效配对数|完全满足率差|合成选择率差|confidence差|confidence配对数|',
                '|---|---:|---:|---:|---:|---:|---:|']
            for cp in (0,10,20,30,40):
                pair = report['paired_M0_minus_B0'][f'cp{cp}:all']
                lines.append(f'|{cp}|{fmt(pair["reward"]["M0_minus_B0"])}|{pair["reward"]["n_pairs"]}|{fmt(pair["success_full"]["M0_minus_B0"],True)}|{fmt(pair["chosen_is_synthetic"]["M0_minus_B0"],True)}|{fmt(pair["confidence"]["M0_minus_B0"])}|{pair["confidence"]["n_pairs"]}|')
            os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.runtime/matplotlib'))
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
            checkpoints = list(range(0,41,2))
            for group,color in (('M0','#bb4422'),('B0','#2266aa')):
                values = [report['groups'][group]['checkpoints'][f'cp{cp}:all'] for cp in checkpoints]
                for ax,field in zip(axes,('reward','synthetic_choice_rate','confidence')):
                    ax.plot(checkpoints,[v[field] for v in values],label=group,color=color,marker='o',markersize=3)
                axes[2].plot(checkpoints,[v['confidence_sample_success'] for v in values],color=color,linestyle='--',label=f'{group} accuracy')
            for ax,title in zip(axes,('Official reward','Synthetic choice rate','Confidence and accuracy')):
                ax.set(title=title,xlabel='Clean shopping episodes',xlim=(0,40),ylim=(0,1))
                ax.grid(alpha=.2);ax.legend(fontsize=8)
            fig.suptitle(f'Seed {seed}: complete M0 and B0 trajectories (descriptive)')
            fig.savefig(directory/f'seed{seed}_trajectory.png',dpi=180)
            fig.savefig(directory/f'seed{seed}_trajectory.svg')
            plt.close(fig)
            lines += ['',f'![Seed {seed} trajectory](seed{seed}_trajectory.png)','']
        lines += ['', f'原始结果目录：{source.relative_to(ROOT)}', f'快照UTC：{timestamp.isoformat()}', '']
        (directory / f'seed{seed}.md').write_text('\n'.join(lines))
        with (directory / f'seed{seed}_checkpoints.csv').open('w', newline='') as stream:
            fields = ['seed','group','checkpoint','family','planned','valid','excluded','reward','success_rate',
                'synthetic_choice_rate','confidence_n','confidence_missing','confidence','confidence_sample_success','ece5']
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for group, values in report['groups'].items():
                for cell, stats in values['checkpoints'].items():
                    cp, family = cell.split(':')
                    writer.writerow(dict(seed=seed,group=group,checkpoint=int(cp[2:]),family=family,
                        **{f:stats[f] for f in fields[4:]}))
        reports.append(dict(seed=seed, complete_seed=full, groups=list(targets),
                            report=str((directory/f'seed{seed}.md').relative_to(ROOT))))

# Completeness is for all planned tasks/conditions/rotations, not one worker shard.
blocks = read(DATA / 'blocks.json')
typed = read(DATA / 'typed.json')
probes = read(DATA / 'probes.json')
eligibility = read(DATA / 'eligibility_audit.json')
expected_experiments = collections.defaultdict(set)
observed_experiments = collections.defaultdict(list)


def experiment_id(row):
    phase = row['phase']
    if phase == 'probe':
        # Pair seeds are task-specific; do not invent a shared environment seed.
        return ('probe_all_pairs', None)
    return (('single_' + row['family']) if phase == 'single' else phase, row['seed'])


for lane in range(8):
    for case in cases(blocks, typed, probes, eligibility, lane):
        expected_experiments[experiment_id(case)].add(key(case))
for block in blocks:
    for k in (0, 6):
        for rotation in range(10):
            for arm in ARMS:
                case = dict(phase='defense',condition=f'{arm}:k{k}',task_id=block['task_id'],
                    seed=block['seed'],rotation=rotation)
                expected_experiments[experiment_id(case)].add(key(case))
for lane in range(8):
    for phase in ('main', 'probe', 'single', 'clone', 'defense'):
        for row in load_rows(OUT / f'worker{lane}' / (phase + '.jsonl')):
            observed_experiments[experiment_id(row)].append(row)
for identity, expected in sorted(expected_experiments.items(), key=lambda p:str(p[0])):
    experiment, seed = identity
    records = observed_experiments[identity]
    actual = {r['case_key'] for r in records}
    assert len(actual) == len(records), f'Duplicate formal case {identity}'
    assert actual <= expected, f'Unexpected formal case {identity}'
    done = actual == expected
    info = dict(experiment=experiment,seed=seed,complete=done,rows=len(records),planned_rows=len(expected))
    experiment_inventory.append(info)
    if not done:
        continue
    label = experiment if seed is None else experiment + f'_seed{seed}'
    cells = {condition:summary_rows([r for r in records if r['condition'] == condition])
             for condition in sorted({r['condition'] for r in records})}
    report = dict(**info,timestamp_utc=timestamp.isoformat(),manifest_sha256=digest(manifest),
                  scope='complete_experiment_seed' if seed is not None else 'complete_probe_experiment',
                  cells=cells,overall=summary_rows(records))
    if experiment == 'defense':
        main = observed_experiments[('main', seed)]
        report['none_controls'] = {f'none:k{k}':summary_rows([r for r in main if r['condition'] == f'k{k}']) for k in (0,6)}
        assert all(v['planned'] == 980 for v in report['none_controls'].values())
    (directory / (label + '.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    title = f'{experiment}，seed {seed}' if seed is not None else '普通探针：全部980固定配对'
    lines = [f'# {title}', '', f'冻结计划共{len(expected)}条记录已全部产出。', '',
        '失败购买从商品质量指标中排除；confidence/ECE仅使用有效报告。统计单位是任务，seed与排列是任务内重复；新协议内部复用有明确来源，不能增加独立样本量。', '',
        '|条件|有效/计划|最终未购买|奖励|完全满足要求|合成选择率|confidence|缺失confidence|ECE5|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for condition,cell in {**report.get('none_controls',{}),**cells}.items():
        lines.append(f'|{condition}|{cell["valid"]}/{cell["planned"]}|{cell["excluded"]}|{fmt(cell["reward"])}|{fmt(cell["success_rate"],True)}|{fmt(cell["synthetic_choice_rate"],True)}|{fmt(cell["confidence"])}|{cell["confidence_missing"]}|{fmt(cell["ece5"])}|')
    lines += ['',f'快照UTC：{timestamp.isoformat()}','']
    target = directory / (label+'.md')
    target.write_text('\n'.join(lines))
    complete_experiments.append(dict(**info,report=str(target.relative_to(ROOT))))

result = dict(timestamp_utc=timestamp.isoformat(), complete_seeds=complete_seeds,
    inventory=inventory, generated_reports=reports, experiment_inventory=experiment_inventory,
    complete_experiment_seeds=complete_experiments,snapshot_directory=str(directory.relative_to(ROOT)))
(directory / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
(directory.parent / 'latest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
