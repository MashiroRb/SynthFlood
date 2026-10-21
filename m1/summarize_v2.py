"""Predeclared trajectory-level v2 analysis; fail on any missing replicate."""
import csv
import itertools
import json
import random
from pathlib import Path

from audit_figure6 import holm
from validate_v2 import validate_inputs, validate_results

ROOT = Path(__file__).resolve().parents[1]


def percentile(values, q):
    values = sorted(values)
    at = q * (len(values) - 1)
    i = int(at)
    return values[i] + (values[min(i+1,len(values)-1)]-values[i])*(at-i)


def estimate(values):
    n = len(values)
    mean = sum(values) / n
    rng = random.Random(2027)
    draws = [sum(rng.choice(values) for _ in values)/n for _ in range(20000)]
    observed = abs(sum(values))
    null = [abs(sum(s*v for s,v in zip(signs,values))) for signs in itertools.product((-1,1),repeat=n)]
    return {'n_trajectories':n, 'values':values, 'mean':mean,
            'bootstrap95':[percentile(draws,.025),percentile(draws,.975)],
            'bootstrap90':[percentile(draws,.05),percentile(draws,.95)],
            'sign_flip_two_sided_p':sum(value>=observed-1e-12 for value in null)/len(null),
            'conditional_on':'Fixed goals, exam candidates, exposure text pool and frozen backend; seed-level randomization only.'}


def summarize():
    validate_inputs(ROOT)
    manifest=json.loads((ROOT/'data/m1_v2/manifest.json').read_text())
    all_cells={}
    long_rows=[]
    for seed in manifest['seeds']:
        directory=ROOT/f'results_m1_v2/seed{seed}'
        validate_results(ROOT,directory)
        rows=list(csv.DictReader((directory/'m1_exams.csv').open()))
        cells={}
        for phase in ('exam','parity'):
            for arm in ('M0','B0','M2'):
                for cp in (0,4,10,20):
                    raw=[r for r in rows if r['phase']==phase and r['arm']==arm and int(r['checkpoint'])==cp]
                    selected=[int(r['chose_clone']) for r in raw]
                    rate=sum(selected)/len(selected)
                    cells[phase,arm,cp]=rate
                    long_rows.append({'seed':seed,'phase':phase,'arm':arm,'checkpoint':cp,'clones':sum(selected),'n':len(selected),'rate':rate,
                                      'no_purchase':sum(r['purchased']=='0' for r in raw)})
        all_cells[seed]=cells
    difference=lambda phase,cp,a='M0',b='B0': [c[phase,a,cp]-c[phase,b,cp] for c in all_cells.values()]
    summary={'protocol':'m1/PRE_REG_M1_V2.md','seeds':manifest['seeds'],
             'primary_parity20_M0_minus_B0':estimate(difference('parity',20)),
             'parity_difference_in_differences_20_minus_0':estimate([c['parity','M0',20]-c['parity','B0',20]-c['parity','M0',0]+c['parity','B0',0] for c in all_cells.values()]),
             'secondary':{name:estimate(values) for name,values in {
                 'parity0_M0_B0':difference('parity',0),
                 'exam0_M0_B0':difference('exam',0),
                 'exam20_M0_B0':difference('exam',20),
                 'parity0_M0_M2':difference('parity',0,'M0','M2')}.items()},
             'instrument':manifest}
    summary['secondary_holm']=holm({name:result['sign_flip_two_sided_p'] for name,result in summary['secondary'].items()})
    summary['no_purchase_episodes']=sum(row['no_purchase'] for row in long_rows)
    lo,hi=summary['primary_parity20_M0_minus_B0']['bootstrap90']
    summary['meets_predeclared_practical_equivalence_interval']=lo>-.05 and hi<.05
    output=ROOT/'results_m1_v2'
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    with (output/'trajectory_cells.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(long_rows[0]));writer.writeheader();writer.writerows(long_rows)
    result=summary['primary_parity20_M0_minus_B0']
    (output/'REPORT.md').write_text('\n'.join([
        '# M1 v2 补跑结果','',
        f"完成 {len(all_cells)} 条独立随机轨迹，每条含 B0/M0/M2；所有预设种子均纳入。",
        f"主要终点：平价 clean20 的 M0−B0 均值 {result['mean']*100:.2f} 个百分点；轨迹 bootstrap 95% 区间 [{result['bootstrap95'][0]*100:.2f}, {result['bootstrap95'][1]*100:.2f}]；符号翻转双侧 p={result['sign_flip_two_sided_p']:.5f}。",'',
        '统计单位是轨迹；当前区间对固定任务、文本池与后端条件化。符号翻转检验要求差值在零假设下符号可交换。',
        f"全部正式考试中未完成购买 {summary['no_purchase_episodes']} 次；分母保留这些题，未购买不等同于选择金品，各格计数见 CSV。",
        f"预设 ±5pp 实际等价判据：{'满足' if summary['meets_predeclared_practical_equivalence_interval'] else '不满足，不能据此声称已证明偏好完全消退'}。",'',
        '此实验配平经验量、修复价格和 options、使用中性观察记录及新的固定服务后端，属于修正协议的补跑，不是历史仪器的逐字节重现。',
        '所有空记忆 M2 的跨检查点选择一致性检查均通过。完整逐轨迹曲线、次级检验和输入哈希见 trajectory_cells.csv 与 summary.json。','']) )
    print(json.dumps(summary['primary_parity20_M0_minus_B0'],indent=2),flush=True)


if __name__=='__main__':
    summarize()
