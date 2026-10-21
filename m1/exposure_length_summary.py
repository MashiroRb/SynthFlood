"""Trajectory-level duration effects; all lengths retained, no washout claims."""
import collections
import csv
import json
from pathlib import Path

from exposure_length import ROOT,DATA,OUT,SEEDS,LENGTHS,read,validate_inputs,validate_results
from expanded_summary import rates
from summarize_v2 import estimate
from audit_figure6 import holm


def summarize():
    manifest=validate_inputs();quality=manifest['quality'];old36=set(manifest['old36'])
    cells=[];baseline={};outcomes={};exposure=[];new_no_purchase=0
    for seed in SEEDS:
        directory=OUT/f'seed{seed}'
        if not read(directory/'COMPLETE.json')['validated']:
            raise ValueError('Incomplete trajectory')
        rows=validate_results(directory,manifest,seed)
        old=list(csv.DictReader((ROOT/f'results_m1_expanded/seed{seed}/m1_exams.csv').open()))
        twenty=[r for r in old if r['arm']=='M0' and r['phase']=='parity' and r['checkpoint']=='0']
        reference=[r for r in old if r['arm']=='B0' and r['phase']=='parity' and r['checkpoint']=='0']
        baseline[seed]=rates(reference,quality)
        for r in rows+twenty+reference:
            outcome=tuple(r[k] for k in ('chosen_kind','chose_clone','reward','purchased'))
            outcomes.setdefault(r['input_sha256'],set()).add(outcome)
        new_no_purchase+=sum(r['purchased']=='0' for r in rows if r['phase']=='parity')
        for length in LENGTHS:
            selected=twenty if length==20 else [r for r in rows if r['phase']=='parity' and int(r['checkpoint'])==length]
            if len(selected)!=manifest['n_pairs']:
                raise ValueError('Wrong exam size')
            for subset in ('all','old36','added'):
                raw=[r for r in selected if subset=='all' or ((r['pair_idx'] in old36)==(subset=='old36'))]
                refs=[r for r in reference if subset=='all' or ((r['pair_idx'] in old36)==(subset=='old36'))]
                measured=rates(raw,quality);control=rates(refs,quality)
                cells.append({'seed':seed,'exposure_length':length,'subset':subset,
                    'origin':'previously_measured' if length==20 else 'newly_measured',**measured,
                    'micro_minus_empty':measured['micro']-control['micro'],
                    'macro_minus_empty':measured['macro']-control['macro']})
        episodes=list(csv.DictReader((directory/'m1_episodes.csv').open()))
        for block,lo,hi in [('21-40',20,40),('41-80',40,80)]:
            blockrows=[r for r in episodes if lo<=int(r['ep_idx'])<hi]
            exposure.append({'seed':seed,'block':block,'n':len(blockrows),
                'synthetic_purchase_rate':sum(int(r['chose_synthetic']) for r in blockrows)/len(blockrows),
                'mean_reward':sum(float(r['reward']) for r in blockrows)/len(blockrows),
                'mean_gold_cf':sum(float(r['gold_reward_cf']) for r in blockrows)/len(blockrows)})
    if any(len(v)>1 for v in outcomes.values()):
        raise ValueError('Same actual input has inconsistent outcomes')
    table={(r['seed'],r['exposure_length'],r['subset']):r for r in cells}
    effects={};increments={}
    for subset in ('all','old36','added'):
        effects[subset]={weight:{str(length):estimate([table[seed,length,subset][weight+'_minus_empty'] for seed in SEEDS])
                                for length in LENGTHS} for weight in ('micro','macro')}
    for length in (40,80):
        increments[str(length)+'_minus_20']=estimate([table[seed,length,'all']['macro']-table[seed,20,'all']['macro'] for seed in SEEDS])
    adjusted=holm({name:r['sign_flip_two_sided_p'] for name,r in increments.items()})
    result={'protocol':'m1/EXPOSURE_LENGTH_PROTOCOL.md','seeds':SEEDS,'lengths':list(LENGTHS),
        'n_pairs':manifest['n_pairs'],'n_gold_asins':manifest['n_gold_asins'],
        'effects_minus_empty':effects,'increments_macro':increments,'increments_holm':adjusted,
        'new_shopping_episodes':60*len(SEEDS),'new_main_exams':2*manifest['n_pairs']*len(SEEDS),
        'new_sentinel_exams':32*len(SEEDS),'new_no_purchase':new_no_purchase,
        'old20_and_empty_reused':True,'inconsistent_inputs':0,'exposure_blocks':exposure}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'cells.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(cells[0]));writer.writeheader();writer.writerows(cells)
    lines=['# 延长污染暴露：20 / 40 / 80轮','',
        '本轮是看到前次结果后的探索性后续实验。八个原种子全部保留，使用60个新购物目标，原20轮前缀和452题考试保持不变。',
        '20轮与空记忆基线复用已有实测数据；40/80轮为新增实测。没有新增独立种子，没有权重训练，没有新增洗脱阶段。','',
        '|种子|空记忆B0|污染20轮|污染40轮|污染80轮|','|---|---:|---:|---:|---:|']
    for seed in SEEDS:
        values=[baseline[seed]['micro']]+[table[seed,length,'all']['micro'] for length in LENGTHS]
        lines.append(f'|{seed}|'+'|'.join(f'{v:.2%}' for v in values)+'|')
    lines+=['','按题等权（微平均）与先金品内平均、再金品等权（宏平均）均报告。以下区间以8条轨迹重采样，条件于固定题目与文本池。','',
        '|暴露轮数|相对空记忆：微平均差|相对空记忆：宏平均差及95%区间|',
        '|---|---:|---:|']
    for length in LENGTHS:
        a,b=[effects['all'][weight][str(length)] for weight in ('micro','macro')]
        lines.append(f"|{length}|{a['mean']*100:+.2f}pp|{b['mean']*100:+.2f}pp [{b['bootstrap95'][0]*100:+.2f}, {b['bootstrap95'][1]*100:+.2f}]|")
    lines+=['','延长轮数是否增强偏移，需直接比较同一轨迹40/80轮与20轮，而不是仅与空记忆比较。','',
        '|比较（宏平均）|差值及95%区间|两项Holm校正p|','|---|---:|---:|']
    for name,r in increments.items():
        lines.append(f"|{name}|{r['mean']*100:+.2f}pp [{r['bootstrap95'][0]*100:+.2f}, {r['bootstrap95'][1]*100:+.2f}]|{adjusted[name]:.5f}|")
    lines+=['',f"新增考试未购买 {new_no_purchase} 次，保留分母。相同输入购买结果不一致数为0；完整记忆、20轮前缀、长度和逐题完整性检查通过。",'',
        '## 解释边界','',
        '最近三条注入、最近五条观察提炼的机制保持不变，延长轮数不保证累积更强偏好。只展示所有预定长度，不根据最有利结果选择结论。',
        '新任务同时扩充内容覆盖，不能把变化唯一解释为固定文本池上的时长效应。本轮只有空记忆基线，缺少同样长的干净经验辅助对照，不能据此独立识别污染特异效应。',
        '5pp仅为实际效应量参照。即便相对空记忆显著，也应检查相对20轮是否增强；如果未增强，不应继续延长到出现显著结果为止。',
        '本轮没有运行后续洗脱，不能据此报告洗脱速度或半衰期。保留评分修复、中性事实观察、教训温度0与固定后端，仍非历史协议精确复现。',
        '全部通过Slurm执行，原始结果保留，未push。','',
        '![暴露长度结果](exposure_length.png)']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for seed in SEEDS:
        axes[0].plot(LENGTHS,[100*table[seed,length,'all']['micro'] for length in LENGTHS],marker='o',label=str(seed),alpha=.75)
        axes[1].plot(LENGTHS,[100*table[seed,length,'all']['macro_minus_empty'] for length in LENGTHS],marker='o',alpha=.75)
    axes[0].axhline(100*baseline[SEEDS[0]]['micro'],color='black',ls='--',label='Empty memory')
    axes[0].set(ylabel='Parity clone choice (%)',title='All452 pairs; same trajectories')
    axes[1].axhline(0,color='black',ls='--');axes[1].axhline(5,color='gray',ls=':')
    axes[1].set(ylabel='Difference from empty memory (pp)',title='Equal weighting of gold ASINs')
    for ax in axes:
        ax.set(xlabel='Polluted shopping episodes',xticks=LENGTHS);ax.grid(alpha=.2)
    axes[0].legend(ncol=3,fontsize=7,frameon=False)
    fig.tight_layout()
    for ext in ('png','pdf'):
        fig.savefig(OUT/f'exposure_length.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    print(json.dumps({'increments':increments,'holm':adjusted},indent=2)+'\nLENGTH_SUMMARY_COMPLETE',flush=True)


if __name__=='__main__':
    summarize()
