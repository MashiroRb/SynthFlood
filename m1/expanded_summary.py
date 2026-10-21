"""Full-pool parity analysis with original B0 timeline and gold-level weighting."""
import argparse
import collections
import csv
import json
from pathlib import Path

from expanded_parity import ROOT, DATA, RESULTS, SEEDS, CHECKPOINTS, read, validate_inputs, validate_run
from summarize_v2 import estimate


def rates(rows, quality):
    if not rows:
        raise ValueError('Cannot report an empty cell')
    groups = collections.defaultdict(list)
    for row in rows:
        groups[quality[row['pair_idx']]['gold_asin']].append(int(row['chose_clone']))
    return {'n_pairs': len(rows), 'n_gold_asins': len(groups),
            'micro': sum(int(r['chose_clone']) for r in rows)/len(rows),
            'macro': sum(sum(v)/len(v) for v in groups.values())/len(groups),
            'no_purchase': sum(r['purchased']=='0' for r in rows)}


def self_test():
    q = {'0': {'gold_asin':'A'}, '1': {'gold_asin':'A'},
         '2': {'gold_asin':'A'}, '3': {'gold_asin':'B'}}
    rows = [{'pair_idx':str(i), 'chose_clone':str(int(i<3)), 'purchased':'1'} for i in range(4)]
    result = rates(rows,q)
    assert result['micro'] == .75 and result['macro'] == .5
    assert result['n_gold_asins'] == 2
    rows[-1]['purchased']='0'
    assert rates(rows,q)['no_purchase']==1 and rates(rows,q)['micro']==.75
    print('EXPANDED_ANALYSIS_SELF_TESTS_PASSED', flush=True)


def summarize():
    manifest = validate_inputs()
    cells, states, hash_groups = [], [], {}
    for seed in SEEDS:
        directory = RESULTS/f'seed{seed}'
        if not read(directory/'COMPLETE.json')['validated']:
            raise ValueError('Incomplete seed')
        rows = validate_run(directory, manifest, seed)
        for row in rows:
            outcome=tuple(row[k] for k in ('chosen_kind','chose_clone','reward','purchased'))
            hash_groups.setdefault(row['input_sha256'],set()).add(outcome)
        for arm in ('M0','B0'):
            for cp in CHECKPOINTS:
                selected = [r for r in rows if r['arm']==arm and r['phase']=='parity' and int(r['checkpoint'])==cp]
                for subset in ('all','old36','added'):
                    raw = [r for r in selected if subset=='all' or ((r['pair_idx'] in manifest['old36']) == (subset=='old36'))]
                    cells.append({'seed':seed,'arm':arm,'checkpoint':cp,'subset':subset,**rates(raw,manifest['quality'])})
        for cp in CHECKPOINTS:
            a,b=[read(directory/f'checkpoint_{arm}_{cp:02d}.json') for arm in ('M0','B0')]
            states.append({'seed':seed,'checkpoint':cp,'same_injected_context':a['injected_context']==b['injected_context']})
    inconsistent=sum(len(outcomes)>1 for outcomes in hash_groups.values())
    if inconsistent:
        raise ValueError(f'{inconsistent} inconsistent identical inputs across seeds')
    lookup={(r['seed'],r['arm'],r['checkpoint'],r['subset']):r for r in cells}
    effects={}
    for subset in ('all','old36','added'):
        effects[subset]={}
        for weight in ('micro','macro'):
            effects[subset][weight]={str(cp):estimate([
                lookup[seed,'M0',cp,subset][weight]-lookup[seed,'B0',cp,subset][weight]
                for seed in SEEDS]) for cp in CHECKPOINTS}
    summary={'protocol':'m1/EXPANDED_PARITY_PROTOCOL.md','n_pairs':manifest['n_pairs'],
             'n_gold_asins':manifest['n_gold_asins'],'seeds':SEEDS,
             'primary_all_gold_macro_clean20':effects['all']['macro']['20'],
             'acquisition_all_gold_macro_clean0':effects['all']['macro']['0'],
             'effects':effects,'memory_states':states,'inconsistent_identical_inputs':inconsistent,
             'no_purchase_main':sum(r['no_purchase'] for r in cells if r['subset']=='all'),
             'total_main_exams':manifest['n_pairs']*4*len(SEEDS),
             'sentinel_exams':32*len(SEEDS),
             'B0_shopping_episodes':20*len(SEEDS),'M0_shopping_source':'existing v2 frozen states; no new shopping',
             'quality_clone_ge_gold':sum(q['clone_reward']>=q['gold_reward'] for q in manifest['quality'].values())}
    (RESULTS/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    with (RESULTS/'cells.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(cells[0]));writer.writeheader();writer.writerows(cells)
    exclusions=collections.Counter(reason for row in manifest['dispositions'] for reason in row['excluded_reasons'])
    primary=summary['primary_all_gold_macro_clean20']
    acq=summary['acquisition_all_gold_macro_clean0']
    interval=lambda value:f"{100*value['mean']:+.2f}pp，95%轨迹区间 [{100*value['bootstrap95'][0]:+.2f}, {100*value['bootstrap95'][1]:+.2f}]pp"
    lines=['# 全量可用平价题补跑：原 B0 时间线','',
           f"使用 {manifest['n_pairs']} 道题、{manifest['n_gold_asins']} 个金品，旧36题全部保留。467个原始pair的排除原因计数（原因可重叠）：{dict(exclusions)}。逐题原因见 data/m1_expanded/manifest.json。",
           'B0从空记忆直接执行20集相同干净购物；M0读取先前污染20集/干净20集的只读快照。考试与购物任务分开，考试不写记忆。',
           '本轮不再使用v2的“20集干净前阶段”B0。M0的原36题输入及选择全部与v2逐题一致；新B0起点与v2空记忆PRE一致。',
           '仍使用修复的价格/options、中性事实观察、教训温度0和固定服务后端，不能声称是历史协议精确复现。','',
           '## 全题逐种子选择率（pair微平均）','',
           '|种子|M0 clean0|B0 clean0|M0 clean20|B0 clean20|', '|---|---:|---:|---:|---:|']
    for seed in SEEDS:
        values=[lookup[seed,arm,cp,'all']['micro'] for cp in CHECKPOINTS for arm in ('M0','B0')]
        lines.append(f'|{seed}|'+ '|'.join(f'{v:.2%}' for v in values)+'|')
    lines += ['', '## 金品等权主分析','',
              '同一金品多道题先平均，再对金品等权；区间仍以8条轨迹重采样，条件于当前固定题目池。',
              f"诱导结束 clean0：{interval(acq)}；符号翻转 p={acq['sign_flip_two_sided_p']:.5f}。",
              f"主要终点 clean20：{interval(primary)}；符号翻转 p={primary['sign_flip_two_sided_p']:.5f}。",
              '符号翻转需要零假设下符号可交换；少量固定种子和固定任务不支持对所有场景的普遍结论。', '',
              '## 扩大题集的影响','',
              '|题集|clean0微平均差|clean0金品等权差|clean20微平均差|clean20金品等权差|',
              '|---|---:|---:|---:|---:|']
    for subset in ('old36','added','all'):
        values=[effects[subset][weight][str(cp)]['mean'] for cp in CHECKPOINTS for weight in ('micro','macro')]
        lines.append('|'+subset+'|'+'|'.join(f'{v*100:+.2f}pp' for v in values)+'|')
    lines += ['', '这个对比使用本轮相同M0/B0记忆；它区分题集影响，不把原v2不同B0的表格直接相减。',
              f"主考试未购买 {summary['no_purchase_main']} 次，留在分母并单独标记。相同输入跨种子有 {inconsistent} 个不一致。",
              f"clean20有 {sum(s['checkpoint']==20 and s['same_injected_context'] for s in states)}/8 对M0/B0的实际注入文本相同。",
              f"官方奖励上不劣于金品的克隆有 {summary['quality_clone_ge_gold']}/{manifest['n_pairs']}，所以克隆选择不等同于奖励损失。",
              '', '## 解释边界','',
              '增加题目扩大的是每条固定记忆状态的考试覆盖，不增加独立污染轨迹；不保证消除种子差异或使M0高于B0。',
              '如果clean0未显示稳定正向差异，不能将clean20相近称为成功诱导后的洗脱。若差值全零导致退化区间，也不代表未知任务/文本池没有不确定性。',
              '题目来自现有缓存，有RA1重用与生成缺题；排除按身份和缓存可用性确定，没有按本轮结果筛选。未新增污染文本。',
              '全部经Slurm执行，原结果保留，没有push。', '',
              '![扩大考试结果](expanded_parity.png)']
    (RESULTS/'REPORT.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4),sharey=True)
    for ax,cp in zip(axes,CHECKPOINTS):
        for arm,color in [('M0','#0072B2'),('B0','#666666')]:
            ax.plot(SEEDS,[lookup[seed,arm,cp,'all']['micro'] for seed in SEEDS],marker='o',label=arm,color=color)
        ax.set(title=f'Clean {cp}: all {manifest["n_pairs"]} eligible pairs',xlabel='Trajectory seed',ylim=(0,1),xticks=SEEDS)
        ax.tick_params(axis='x',rotation=45);ax.grid(alpha=.2)
    axes[0].set_ylabel('Parity clone choice');axes[0].legend(frameon=False)
    fig.suptitle('B0 starts empty; M0 states reused without changing memory')
    fig.tight_layout()
    for ext in ('png','pdf'):
        fig.savefig(RESULTS/f'expanded_parity.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    print(json.dumps({'primary':primary,'acquisition':acq},indent=2)+'\nEXPANDED_SUMMARY_COMPLETE',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    self_test() if args.self_test else summarize()
