"""Report all paired clean40 checkpoints without selecting seeds or times."""
import csv
import json

from washout40 import ROOT, OUT, SEEDS, CHECKPOINTS, FIELDS, read, validate_inputs, validate_results
from expanded_summary import rates
from summarize_v2 import estimate
from audit_figure6 import holm


def summarize():
    manifest = validate_inputs()
    quality = manifest['quality']
    cells, states, changes, hash_groups = [], [], [], {}
    for seed in SEEDS:
        directory = OUT / f'seed{seed}'
        if not read(directory / 'COMPLETE.json')['validated']:
            raise ValueError('Incomplete seed')
        measured = validate_results(directory, manifest, seed)
        indexed = {(r['arm'], int(r['checkpoint']), r['pair_idx']): r for r in measured if r['phase'] == 'parity'}
        for row in measured:
            hash_groups.setdefault(row['input_sha256'], set()).add(tuple(row[k] for k in FIELDS[:-1]))
        for cp in CHECKPOINTS:
            for arm in ('M0', 'B0'):
                raw = [indexed[arm, cp, pi] for pi in quality]
                cells.append({'seed': seed, 'arm': arm, 'checkpoint': cp, **rates(raw, quality),
                    'mean_reward': sum(float(r['reward']) for r in raw) / len(raw)})
            a, b = [read(directory / f'checkpoint_{arm}_{cp:02d}.json') for arm in ('M0', 'B0')]
            states.append({'seed': seed, 'checkpoint': cp,
                'same_injected_context': a['injected_context'] == b['injected_context'],
                'M0_entries': len(a['entries']), 'B0_entries': len(b['entries'])})
            towards = away = 0
            for pi in quality:
                ma, mb = [int(indexed[arm, cp, pi]['chose_clone']) for arm in ('M0', 'B0')]
                towards += ma > mb
                away += ma < mb
            changes.append({'seed': seed, 'checkpoint': cp, 'M0_clone_B0_nonclone': towards,
                'M0_nonclone_B0_clone': away, 'clone_indicator_disagreements': towards + away})
    inconsistent = sum(len(v) > 1 for v in hash_groups.values())
    if inconsistent:
        raise ValueError('Identical inputs produced different outcomes across seeds')
    lookup = {(c['seed'], c['arm'], c['checkpoint']): c for c in cells}
    effects = {weight: {str(cp): estimate([lookup[seed, 'M0', cp][weight] - lookup[seed, 'B0', cp][weight]
        for seed in SEEDS]) for cp in CHECKPOINTS} for weight in ('micro', 'macro')}
    corrected = holm({str(cp): effects['macro'][str(cp)]['sign_flip_two_sided_p'] for cp in CHECKPOINTS})
    summary = {'protocol': 'm1/WASHOUT40_PROTOCOL.md', 'seeds': SEEDS, 'checkpoints': CHECKPOINTS,
        'n_pairs': manifest['n_pairs'], 'n_gold_asins': manifest['n_gold_asins'],
        'effects_M0_minus_B0': effects, 'macro_all21_holm': corrected,
        'memory_states': states, 'paired_choice_changes': changes,
        'new_main_exams': manifest['new_main_exams_per_seed'] * len(SEEDS), 'new_sentinels': 32 * len(SEEDS),
        'new_clean_episodes': 80 * len(SEEDS), 'new_pollution_episodes': 0,
        'pollution_source': 'archived 40-episode measured M0 trajectories',
        'no_purchase_main': sum(c['no_purchase'] for c in cells), 'inconsistent_identical_inputs': inconsistent}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    for name, data in [('cells.csv', cells), ('choice_changes.csv', changes), ('memory_states.csv', states)]:
        with (OUT / name).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    lines = ['# 污染40轮后干净40轮：M0 / B0', '',
        'M0从既有污染40轮末期完整记忆继续；B0从空记忆开始。两臂每seed的40轮干净购物任务、候选商品和顺序相同。',
        '第0轮在任何干净购物前考试，之后每2轮完整考试；所有节点使用相同452题/305金品，考试不写记忆。',
        '污染经历复用既有实测，不冒充新增污染调用。第0轮和空记忆哨兵逐题通过原输入及结果核查。', '',
        '## 所有节点的平均结果', '',
        '|干净轮数|M0 clone率|B0 clone率|微平均差|金品等权差及95%轨迹区间|相同注入文本的seed数|',
        '|---:|---:|---:|---:|---:|---:|']
    for cp in CHECKPOINTS:
        averages = {a: sum(lookup[s, a, cp]['micro'] for s in SEEDS) / len(SEEDS) for a in ('M0', 'B0')}
        micro, macro = [effects[w][str(cp)] for w in ('micro', 'macro')]
        lo, hi = macro['bootstrap95']
        same = sum(s['checkpoint'] == cp and s['same_injected_context'] for s in states)
        lines.append(f"|{cp}|{averages['M0']:.2%}|{averages['B0']:.2%}|{100*micro['mean']:+.2f}pp|{100*macro['mean']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}]pp|{same}/8|")
    lines += ['', '## 全部种子', '', '|种子|干净轮数|M0|B0|M0−B0|', '|---:|---:|---:|---:|---:|']
    for seed in SEEDS:
        for cp in CHECKPOINTS:
            a, b = [lookup[seed, arm, cp]['micro'] for arm in ('M0', 'B0')]
            lines.append(f'|{seed}|{cp}|{a:.2%}|{b:.2%}|{100*(a-b):+.2f}pp|')
    lines += ['', '## 完整性与解释边界', '',
        f"新增主考试{summary['new_main_exams']}次、哨兵{summary['new_sentinels']}次、干净购物{summary['new_clean_episodes']}集；主考试未购买{summary['no_purchase_main']}次，保留分母。",
        '区间以8条seed轨迹重采样，条件于固定任务、文本池及后端；没有增加独立污染轨迹。金品等权21节点探索性p统一Holm，完整数值见summary.json。',
        '逐题向clone/离开clone的差异均报告在choice_changes.csv，净率相同不等于逐题选择相同。',
        '本研究测外部记忆读入对决策的影响，没有权重更新。旧记录退出最近三条读取窗口造成的收敛不能单独证明内在偏好消退。',
        '40轮是查看此前结果后指定的长度；不能选择显著节点证明强诱导。缺少同长度干净前经历辅助对照，污染特异性仍不能唯一归因。',
        'clone选择不等于官方奖励损失；逐格奖励和未购买见cells.csv。首次过阈值不是拟合半衰期，零差区间不能外推所有任务。',
        '所有作业通过Slurm执行，原始结果保留，未push。', '', '![每两轮考试曲线](washout40.png)']
    (OUT / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for arm, color in [('M0', '#0072B2'), ('B0', '#666666')]:
        for seed in SEEDS:
            axes[0].plot(CHECKPOINTS, [lookup[seed, arm, cp]['micro'] * 100 for cp in CHECKPOINTS], color=color, alpha=.15)
        axes[0].plot(CHECKPOINTS, [sum(lookup[s, arm, cp]['micro'] for s in SEEDS) / len(SEEDS) * 100
            for cp in CHECKPOINTS], color=color, marker='o', label=arm)
    estimates = [effects['macro'][str(cp)] for cp in CHECKPOINTS]
    axes[1].plot(CHECKPOINTS, [e['mean'] * 100 for e in estimates], marker='o', color='#0072B2')
    axes[1].fill_between(CHECKPOINTS, [e['bootstrap95'][0] * 100 for e in estimates],
        [e['bootstrap95'][1] * 100 for e in estimates], alpha=.2)
    axes[1].axhline(0, color='gray', linewidth=1)
    axes[0].set(ylabel='Clone choice (%)', title='452 fixed exam questions')
    axes[1].set(ylabel='M0 minus B0 (percentage points)', title='Gold-weighted mean and trajectory 95% interval')
    for ax in axes:
        ax.set_xlabel('Completed clean shopping episodes')
        ax.grid(alpha=.2)
    axes[0].legend(frameon=False)
    fig.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(OUT / f'washout40.{ext}', dpi=180, bbox_inches='tight')
    plt.close(fig)
    print('WASHOUT40_SUMMARY_COMPLETE', flush=True)


if __name__ == '__main__':
    summarize()
