"""Task-cluster summaries; rotations and environment seeds remain repeated measures."""
import collections
import csv
import json
import math

from .common import ROOT, DATA, OUT, LANES, ARMS, COUNTS, read, write, file_sha, validate_sources
from .worker import validate_lane


def estimate(values):
    import numpy as np
    values = np.asarray(values, dtype=float)
    random = np.random.default_rng(2027)
    bootstrap = values[random.integers(0, len(values), size=(20000,len(values)))].mean(axis=1)
    observed = abs(values.mean())
    flips = random.choice((-1.,1.), size=(20000,len(values)))
    null = abs((flips * values).mean(axis=1))
    return {'n_tasks':len(values), 'mean':float(values.mean()),
        'bootstrap95':[float(v) for v in np.quantile(bootstrap,[.025,.975])],
        'sign_flip_p':float((1 + (null >= observed - 1e-12).sum()) / 20001),
        'conditional_on':'98 selected goals, archived text pool, environment seeds1/2 and recorded hardware blocks'}


def holm(results):
    highest = 0.; adjusted = {}
    for rank, (name,result) in enumerate(sorted(results.items(),key=lambda pair:pair[1]['sign_flip_p'])):
        highest = max(highest,(len(results)-rank)*result['sign_flip_p'])
        adjusted[name] = min(1.,highest)
    return adjusted


def metrics(rows):
    from synthflood.metrics import ece
    confidences = [(r['confidence'],float(r['success_full'])) for r in rows if r['confidence'] is not None]
    return {'rows':len(rows), 'reward':sum(r['reward'] for r in rows)/len(rows),
        'regret':sum(1-r['reward'] for r in rows)/len(rows),
        'gold_gap':sum(r['gold_reward']-r['reward'] for r in rows)/len(rows),
        'success':sum(r['success_full'] for r in rows)/len(rows),
        'success80':sum(r['success80'] for r in rows)/len(rows),
        'synthetic_share':sum(r['chosen_is_synthetic'] for r in rows)/len(rows),
        'no_purchase':sum(not r['purchased'] for r in rows),
        'confidence_n':len(confidences),
        'confidence':sum(c for c,_ in confidences)/len(confidences) if confidences else None,
        'ece5':ece([c for c,_ in confidences],[y for _,y in confidences],5) if confidences else None,
        'new_model_calls':sum(r['new_model_calls'] for r in rows),
        'new_episodes':sum(r['origin']=='new' for r in rows)}


def summarize(phase):
    manifest = validate_sources()
    allrows = []
    for lane in range(LANES):
        marker = 'MAIN_COMPLETE.json' if phase=='main' else 'COMPLETE.json'
        if not read(OUT/f'worker{lane}'/marker)['validated']:
            raise ValueError('Incomplete worker')
        allrows.extend(validate_lane(lane,'main'))
        if phase=='defense':
            allrows.extend(validate_lane(lane,'defense'))
    expected = manifest['main_rows'] + (manifest['defense_rows'] if phase=='defense' else 0)
    if len(allrows)!=expected:
        raise ValueError('Unexpected global row count')
    index = {(r['seed'],r['task_id'],r['k'],r['rotation'],r['arm']):r for r in allrows}
    if len(index)!=expected:
        raise ValueError('Duplicate global keys')
    grouped = collections.defaultdict(list)
    task_cells = collections.defaultdict(list)
    hardware = collections.defaultdict(list)
    for row in allrows:
        grouped[row['arm'],row['k']].append(row)
        task_cells[row['task_id'],row['arm'],row['k']].append(row['reward'])
        hardware[row['backend_sha256'],row['arm'],row['k']].append(row)
    task_means = {key:sum(vals)/len(vals) for key,vals in task_cells.items()}
    cells = [{'arm':arm,'k':k,**metrics(rows)} for (arm,k),rows in sorted(grouped.items())]
    effects = {}
    if phase=='main':
        for k in COUNTS[1:]:
            effects[f'k{k}_minus_k0'] = estimate([task_means[t,'none',k]-task_means[t,'none',0] for t in manifest['eligible_task_ids']])
        primary = {'k6_minus_k0':effects['k6_minus_k0']}
    else:
        for arm in ARMS:
            for k in (0,6):
                # Validate shared hardware, exact pre-defense candidate input and task.
                for row in grouped[arm,k]:
                    base=index[row['seed'],row['task_id'],k,row['rotation'],'none']
                    if row['pre_sha256']!=base['pre_sha256'] or row['backend_sha256']!=base['backend_sha256']:
                        raise ValueError('Unmatched baseline or hardware')
                effects[f'{arm}:k{k}'] = estimate([task_means[t,arm,k]-task_means[t,'none',k] for t in manifest['eligible_task_ids']])
        primary = {name:effects[name] for name in ('provenance:k6','detector_struct:k6')}
    summary = {'phase':phase,'protocol':'paired_sweep/PROTOCOL.md','n_tasks':98,
        'seeds':[1,2], 'rotations':10,'rows':len(allrows),'cells':cells,'effects':effects,
        'primary':primary,'primary_holm':holm(primary),
        'exploratory_holm':holm({name:e for name,e in effects.items() if name not in primary}),
        'options_policy':manifest['options_policy'],
        'origin_counts':dict(collections.Counter(r['origin'] for r in allrows)),
        'hardware_groups': [{'backend_sha256':backend,'arm':arm,'k':k,**metrics(rows)}
            for (backend,arm,k),rows in hardware.items()]}
    write(OUT/f'{phase}_summary.json',summary)
    with (OUT/f'{phase}_cells.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(cells[0])); writer.writeheader();writer.writerows(cells)
    lines=[f'# N98 {phase}结果','',
        '两个环境seed和十种排列均为任务内重复。按98个任务聚类，固定缓存文本池；未修复options。',
        '排序防御接收十种冻结输入，排序后不再轮转；所有防御与主剂量的同一输入/后端参考匹配。','',
        '|方法|污染槽位k|奖励|成功率|合成购买率|未购买|新评测单元|', '|---|---:|---:|---:|---:|---:|---:|']
    for c in cells:
        lines.append(f"|{c['arm']}|{c['k']}|{c['reward']:.4f}|{c['success']:.2%}|{c['synthetic_share']:.2%}|{c['no_purchase']}|{c['new_episodes']}|")
    lines += ['', '|配对奖励差|均值|95%任务区间|原始符号翻转p|','|---|---:|---:|---:|']
    for name,e in effects.items():
        lo,hi=e['bootstrap95']
        lines.append(f"|{name}|{e['mean']:+.4f}|[{lo:+.4f},{hi:+.4f}]|{e['sign_flip_p']:.5f}|")
    lines += ['', '主要比较Holm结果：'+json.dumps(summary['primary_holm']),
        '其它比较完整报告并单独Holm，见JSON。未购买保留分母。原始数据与已冻结方案不覆盖。',
        '复用记录不是新调用，不增加独立样本。硬件条件按任务区组记录，全部条件在同一持续GPU服务配对；不得据此声称所有型号逐输入相同。',
        '本轮改变了位置控制、统一提示和部分防御对照规则，不是旧协议逐字节复现。原文本检测阈值为既有Qwen评分下的固定15，不能宣称重新校准或复现GPT2检测器。',
        f'![结果]({phase}.png)']
    (OUT/f'{phase}_REPORT.md').write_text('\n'.join(lines)+'\n')
    plot(summary)
    print('PAIRED_SUMMARY_COMPLETE',phase,len(allrows),flush=True)


def plot(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    phase=summary['phase']; lookup={(c['arm'],c['k']):c for c in summary['cells']}
    if phase=='main':
        fig,axes=plt.subplots(1,3,figsize=(12,3.5))
        for metric,label in [('success','Success'),('regret','Regret')]:
            axes[0].plot(COUNTS,[lookup['none',k][metric] for k in COUNTS],marker='o',label=label)
        axes[0].legend(frameon=False)
        axes[1].plot(COUNTS,[lookup['none',k]['synthetic_share'] for k in COUNTS],marker='o')
        axes[1].set_ylabel('Synthetic purchase share')
        for metric,label in [('confidence','Confidence'),('ece5','ECE (5 bins)')]:
            axes[2].plot(COUNTS,[lookup['none',k][metric] for k in COUNTS],marker='o',label=label)
        axes[2].legend(frameon=False)
        for ax in axes:
            ax.set_xlabel('Contaminated slots (out of 10)');ax.set_xticks(COUNTS);ax.grid(alpha=.2)
        fig.suptitle('N98: fixed replacements, ten cyclic layouts, two environment seeds')
    else:
        fig,axes=plt.subplots(1,2,figsize=(12,8),sharey=True)
        for ax,k in zip(axes,(0,6)):
            es=[summary['effects'][f'{arm}:k{k}'] for arm in ARMS]
            values=np.array([e['mean'] for e in es]); lows=np.array([e['bootstrap95'][0] for e in es]); highs=np.array([e['bootstrap95'][1] for e in es])
            ax.errorbar(values,np.arange(len(ARMS)),xerr=[values-lows,highs-values],fmt='o',capsize=2)
            ax.axvline(0,color='gray',linewidth=1);ax.set_title(f'k={k}: paired reward gain');ax.grid(alpha=.2)
        axes[0].set_yticks(np.arange(len(ARMS)),ARMS);axes[0].invert_yaxis()
    fig.tight_layout()
    for ext in ('png','pdf'):
        fig.savefig(OUT/f'{phase}.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('main','defense'))
    summarize(p.parse_args().phase)
