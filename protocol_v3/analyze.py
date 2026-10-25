"""Audit every planned row and analyze valid, correctly matched task clusters."""
import collections
import math

from .common import *


def describe(records):
    valid=[r for r in records if r['valid']]
    confidence=[r for r in valid if r['confidence'] is not None]
    def mean(field, group=valid):
        values=[float(r[field]) for r in group if r.get(field) is not None]
        return sum(values)/len(values) if values else None
    from synthflood.metrics import ece
    return dict(planned=len(records),valid=len(valid),excluded=len(records)-len(valid),
        exclusion_reasons=dict(collections.Counter(r['exclusion_reason'] for r in records if not r['valid'])),
        n_independent_tasks=len({r['task_id'] for r in valid}),
        reward=mean('reward'),success_rate=mean('success_full'),regret=mean('regret'),
        synthetic_choice_rate=mean('chosen_is_synthetic'),
        purchase_distribution=dict(collections.Counter(r['chosen_kind'] for r in valid)),
        confidence_n=len(confidence),confidence=mean('confidence',confidence),
        confidence_sample_success=mean('success_full',confidence),
        ece5=ece([r['confidence'] for r in confidence],[r['success_full'] for r in confidence],5) if confidence else None,
        new_model_calls=sum(r['new_model_calls'] for r in records),
        origins=dict(collections.Counter(r['origin'] for r in records)))


def paired(left,right,metric='reward',exam=False):
    def pairing_key(r):
        return tuple(r[k] for k in ('task_id','seed','rotation','backend_sha256')) + ((r['family'],) if exam else ())
    a={pairing_key(r):r for r in left}
    b={pairing_key(r):r for r in right}
    assert len(a)==len(left) and len(b)==len(right),'Duplicate pairing keys'
    groups=collections.defaultdict(list)
    for k in a.keys()&b.keys():
        x,y=a[k],b[k]
        if x['valid'] and y['valid'] and x.get(metric) is not None and y.get(metric) is not None:
            groups[x['task_id']].append(float(x[metric])-float(y[metric]))
    n=sum(map(len,groups.values()))
    if not n:
        return dict(metric=metric,n_pairs=0,n_tasks=0,effect=None,ci95=None,p=None)
    import numpy as np
    # Ratio of sums retains the actual valid paired-record estimand while
    # resampling/sign-flipping entire tasks, including all internal repeats.
    sums=np.array([sum(v) for v in groups.values()])
    counts=np.array([len(v) for v in groups.values()])
    random=np.random.default_rng(20261023)
    boot=[]; null=[]
    for start in range(0,20000,1000):
        ix=random.integers(len(sums),size=(1000,len(sums)))
        boot.extend((sums[ix].sum(axis=1)/counts[ix].sum(axis=1)).tolist())
        signs=random.choice([-1,1],size=(1000,len(sums)))
        null.extend(((signs*sums).sum(axis=1)/counts.sum()).tolist())
    effect=float(sums.sum()/counts.sum())
    return dict(metric=metric,n_pairs=n,n_tasks=len(groups),effect=effect,
        ci95=[float(x) for x in np.quantile(boot,[.025,.975])],
        p=(sum(abs(v)>=abs(effect)-1e-12 for v in null)+1)/20001,
        unmatched_left=len(a.keys()-b.keys()),unmatched_right=len(b.keys()-a.keys()),
        invalid_or_metric_missing_pairs=len(a.keys()&b.keys())-n)


def holm(comparisons,names):
    names=sorted([n for n in names if comparisons[n]['p'] is not None],key=lambda n:comparisons[n]['p'])
    previous=0
    for i,n in enumerate(names):
        previous=max(previous,min(1.,comparisons[n]['p']*(len(names)-i)))
        comparisons[n]['holm_p']=previous


def analyze():
    manifest=validate()
    assert all((OUT/f'worker{i}'/'COMPLETE.json').exists() for i in range(8))
    assert all((OUT/f'washout{i}'/'COMPLETE.json').exists() for i in range(2))
    records=[]
    for i in range(8):
        for phase in ('main','probe','single','clone','defense'):
            records+=rows(OUT/f'worker{i}'/(phase+'.jsonl'))
    for i in range(2):
        for phase in ('exam','shopping'):
            records+=rows(OUT/f'washout{i}'/(phase+'.jsonl'))
    assert len({r['case_key'] for r in records})==len(records),'Duplicate formal case'
    counts=collections.Counter(r['phase'] for r in records)
    assert dict(counts)==manifest['planned'],(counts,manifest['planned'])
    cells=collections.defaultdict(list)
    for r in records:
        assert r['valid']==r['purchased']
        if not r['valid']:
            assert r['reward'] is None and r['exclusion_reason']
        cells[r['phase']+'|'+r['condition']].append(r)
    summaries={k:describe(v) for k,v in cells.items()}
    comparisons={}
    def add(name,a,b,exam=False):
        for metric in ('reward','success_full','chosen_is_synthetic','regret','confidence'):
            comparisons[name+'|'+metric]=paired(a,b,metric,exam)
    for k in (2,4,6):
        add(f'main:k{k}-k0',cells[f'main|k{k}'],cells['main|k0'])
    for f in FAMILIES:
        add(f'single:{f}:polluted-clean',cells[f'single|{f}:k4'],cells[f'single|{f}:k0'])
    for c in ('price100','rating','joint','price90','price80','price70'):
        add(f'clone:{c}-original',cells[f'clone|{c}'],cells['clone|original'])
    for k in (0,6):
        for arm in ARMS:
            add(f'defense:{arm}-none:k{k}',cells[f'defense|{arm}:k{k}'],cells[f'main|k{k}'])
        for detector,control in [('detector_struct','random_struct'),('detector_text','random_text')]:
            add(f'defense:{detector}-{control}:k{k}',cells[f'defense|{detector}:k{k}'],cells[f'defense|{control}:k{k}'])
    exam_records=[r for r in records if r['phase']=='exam']
    shopping_records=[r for r in records if r['phase']=='shopping']
    for cp in range(0,41,2):
        for family in ('all',)+FAMILIES:
            selected=[r for r in exam_records if r['checkpoint']==cp and (family=='all' or r['family']==family)]
            for group in ('M0','B0'):
                summaries[f'exam_pooled|{group}:cp{cp}:{family}']=describe([r for r in selected if r['group']==group])
            add(f'washout:M0-B0:cp{cp}:{family}',[r for r in selected if r['group']=='M0'],
                [r for r in selected if r['group']=='B0'],exam=True)
    # Ordinary probes: overall plus actual sampled type groups.
    probe_records=[r for r in records if r['phase']=='probe']
    summaries['probe_pooled|all']=describe(probe_records)
    # Freeze the same two primary defenses as prior N98 and explicitly add
    # detector-vs-matched-random direct contrasts as their own comparison family.
    primary=[f'defense:{a}-none:k6|reward' for a in ('provenance','detector_struct')]
    direct=[f'defense:{a}-{b}:k6|reward' for a,b in [('detector_struct','random_struct'),('detector_text','random_text')]]
    holm(comparisons,primary)
    holm(comparisons,direct)
    exploratory=[n for n in comparisons if n not in primary+direct and n!='main:k6-k0|reward']
    holm(comparisons,exploratory)
    write(OUT/'summary.json',dict(cells=summaries,comparisons=comparisons,counts=dict(counts),
        primary_comparisons=primary,direct_comparisons=direct,exploratory_comparisons=exploratory,
        independence='Task; all environment seeds, rotations, checkpoint and family repeats stay within task',
        inference='20000 task cluster ratio bootstrap; task-level sign flips; seed20261023'))
    text=['# 新协议实验结果','',f'正式计划记录 {len(records)} 条；有效 {sum(r["valid"] for r in records)} 条。失败均保留日志并排除正式指标分母。',
          '', '|条件|计划|有效|排除|奖励|成功率|合成选择率|置信度有效数|ECE5|','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(x):
        return 'N/A' if x is None else f'{x:.4f}'
    for name,s in sorted(summaries.items()):
        text.append(f'|{name}|{s["planned"]}|{s["valid"]}|{s["excluded"]}|{fmt(s["reward"])}|{fmt(s["success_rate"])}|{fmt(s["synthetic_choice_rate"])}|{s["confidence_n"]}|{fmt(s["ece5"])}|')
    text+=['','B0 无前置购物；组间差异不能单独识别污染相对于一般既往经验的特异效应。',
           '类型单类任务集不同；其原始均值差不能当作任务完全匹配的类型因果比较。',
           '完整配对数量、任务聚类区间、显著性及排除原因见 summary.json。']
    (OUT/'REPORT.md').write_text('\n'.join(text)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6,4))
    for group in ('M0','B0'):
        cps=list(range(0,41,2))
        ys=[summaries[f'exam_pooled|{group}:cp{cp}:all']['synthetic_choice_rate'] for cp in cps]
        ax.plot(cps,ys,marker='o',label=group)
    ax.set(xlabel='Completed clean shopping rounds',ylabel='Synthetic choice rate')
    ax.legend();fig.tight_layout()
    fig.savefig(OUT/'washout.png',dpi=200);fig.savefig(OUT/'washout.pdf');plt.close(fig)
    write(OUT/'COMPLETE.json',dict(validated=True,formal_records=len(records),manifest_sha256=file_sha(DATA/'manifest.json')))


if __name__=='__main__':
    analyze()
