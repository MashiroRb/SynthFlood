"""Post-run independent descriptive checks; no inference or primary re-estimation."""
import collections
import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results_m1_expanded'


def read(path):
    return json.loads(path.read_text())


def render(entries):
    return ('Your experience notes from earlier shopping sessions:\n' +
            '\n'.join(f"- [{e['type']}] {e['text']}" for e in entries[-3:])) if entries else ''


def at(entries, cp):
    return [e for e in entries if e['t']<1000+cp]


def effective(entries):
    return (render(entries),[e['text'] for e in entries if e['type']=='observation'][-5:])


def rate(rows):
    return sum(int(r['chose_clone']) for r in rows)/len(rows)


def macro(rows, quality):
    groups=collections.defaultdict(list)
    for row in rows:
        groups[quality[row['pair_idx']]['gold_asin']].append(int(row['chose_clone']))
    return statistics.mean(statistics.mean(v) for v in groups.values())


def main():
    manifest=read(ROOT/'data/m1_expanded/manifest.json')
    summary=read(OUT/'summary.json')
    quality=manifest['quality']
    old36=set(manifest['old36'])
    records=[];all_outcomes={};empty_cells=[];failures=[]
    no_purchase=[];quality_effects=[]
    for seed in manifest['seeds']:
        directory=OUT/f'seed{seed}'
        rows=list(csv.DictReader((directory/'m1_exams.csv').open()))
        keys=[(r['arm'],r['phase'],r['checkpoint'],r['pair_idx']) for r in rows]
        assert len(keys)==len(set(keys))==4*manifest['n_pairs']+32
        assert len(list(csv.DictReader((directory/'m1_episodes.csv').open())))==20
        states={arm:read(directory/f'checkpoint_{arm}_20.json')['entries'] for arm in ('M0','B0')}
        zero={arm:read(directory/f'checkpoint_{arm}_00.json') for arm in ('M0','B0')}
        assert zero['B0']['entries']==[] and zero['B0']['injected_context']==''
        assert sum(e['type']=='observation' for e in states['B0'])==20
        assert sum(e['type']=='observation' for e in states['M0'])==40
        assert all(e['t']>=1000 for e in states['B0'])
        assert all(e['arm']=='B0' for e in states['B0'])
        for arm in ('M0','B0'):
            assert render(at(states[arm],0))==zero[arm]['injected_context']
            assert render(states[arm])==read(directory/f'checkpoint_{arm}_20.json')['injected_context']
        equality=[effective(at(states['M0'],cp))==effective(at(states['B0'],cp)) for cp in range(21)]
        injection=[render(at(states['M0'],cp))==render(at(states['B0'],cp)) for cp in range(21)]
        permanent=next((cp for cp in range(21) if all(equality[cp:])),None)
        mainrows=[r for r in rows if r['phase']=='parity']
        def cell(arm,cp):
            return [r for r in mainrows if r['arm']==arm and int(r['checkpoint'])==cp]
        for arm in ('M0','B0'):
            for cp in (0,20):
                assert len(cell(arm,cp))==manifest['n_pairs']
        endpoints=[{r['pair_idx']:(r['chose_clone'],r['chosen_kind'],r['reward'],r['purchased'],r['input_sha256'])
                    for r in cell(arm,20)} for arm in ('M0','B0')]
        assert endpoints[0]==endpoints[1]
        empty_cells.append({r['pair_idx']:(r['chose_clone'],r['input_sha256']) for r in cell('B0',0)})
        records.append({'seed':seed,'old36_M0_c0':rate([r for r in cell('M0',0) if r['pair_idx'] in old36]),
            'all_M0_c0':rate(cell('M0',0)),'all_B0_c0':rate(cell('B0',0)),
            'macro_c0_difference':macro(cell('M0',0),quality)-macro(cell('B0',0),quality),
            'M0_entries':len(states['M0']),'B0_entries':len(states['B0']),
            'full_histories_equal':states['M0']==states['B0'],
            'injected_context_equal_by_clean_episode':injection,
            'effective_state_equal_by_clean_episode':equality,
            'effective_state_permanent_agreement_from':permanent})
        for r in rows:
            result=tuple(r[k] for k in ('chose_clone','chosen_kind','reward','purchased'))
            all_outcomes.setdefault(r['input_sha256'],set()).add(result)
            if r['phase']=='parity' and r['purchased']=='0':
                no_purchase.append({'seed':seed,**r})
        for cp in (0,20):
            bad=lambda r:quality[r['pair_idx']]['clone_reward']<quality[r['pair_idx']]['gold_reward']
            a,b=[[r for r in cell(arm,cp) if bad(r)] for arm in ('M0','B0')]
            regret=lambda rr:statistics.mean(quality[r['pair_idx']]['gold_reward']-float(r['reward']) for r in rr)
            quality_effects.append({'seed':seed,'checkpoint':cp,'n_lower_reward_pairs':len(a),
                'lower_reward_clone_micro_difference':rate(a)-rate(b),
                'lower_reward_clone_macro_difference':macro(a,quality)-macro(b,quality),
                'lower_reward_regret_difference':regret(a)-regret(b)})
    assert all(c==empty_cells[0] for c in empty_cells)
    assert all(len(v)==1 for v in all_outcomes.values())
    assert abs(statistics.mean(r['macro_c0_difference'] for r in records)-summary['acquisition_all_gold_macro_clean0']['mean'])<1e-12
    dispersion={}
    for name in ('old36_M0_c0','all_M0_c0'):
        values=[r[name] for r in records]
        dispersion[name]={'mean':statistics.mean(values),'min':min(values),'max':max(values),
                          'range':max(values)-min(values),'sample_sd':statistics.stdev(values)}
    result={'checks_passed':True,'post_run_descriptive_review':True,'dispersion':dispersion,
            'seed_records':records,'no_purchase':no_purchase,'quality_strata_exploratory':quality_effects,
            'review_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'manifest_sha256':hashlib.sha256((ROOT/'data/m1_expanded/manifest.json').read_bytes()).hexdigest()}
    (OUT/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    old,new=[dispersion[k] for k in ('old36_M0_c0','all_M0_c0')]
    lines=['# 扩大考试后的独立结果核查','',
           '本次只核查已有数据并补充描述统计，不修改冻结协议、原始结果或主分析，不增加模型调用。','',
           f"同一M0初始记忆：原36题种子跨度 {old['range']*100:.2f}pp、样本标准差 {old['sample_sd']*100:.2f}pp；全452题跨度 {new['range']*100:.2f}pp、样本标准差 {new['sample_sd']*100:.2f}pp。",
           '八个B0的clean0记忆均为空，452题逐题输入与选择完全一致。',
           '逐题检查通过：每种子1808次正式考试及32次哨兵测量；B0只有20集干净交互；M0读取原有轨迹，无新污染生成。',
           '原36题逐题复测一致性的检查已在主作业及汇总中通过；全题的相同输入均无购买结果不一致。','',
           '|种子|M0最终条目数|B0最终条目数|完整历史相同|有效状态持续一致起点（干净集数）|',
           '|---|---:|---:|---|---:|']
    for r in records:
        lines.append(f"|{r['seed']}|{r['M0_entries']}|{r['B0_entries']}|{r['full_histories_equal']}|{r['effective_state_permanent_agreement_from']}|")
    lines += ['', '有效状态指实际注入的最近三条文本及下次提炼可用的最近五条观察。完整历史不同但有效状态相同，支持状态收敛的解释，未发现将同一笔记复制给两组的情况。',
              '上述持续一致起点是从原始记忆条目按时间重建的描述性核查，不是这些中间点新增的考试结果，不等同于偏好半衰期。',
              f"正式考试有 {len(no_purchase)} 次未购买，明细在review.json；分母保留，不冒充金品选择。",'',
              '质量分层为事后探索性描述，不新增确认性p值。官方评分较低克隆的选择差与记录奖励损失差见review.json。',
              '主结论应使用冻结分析：初始小幅正向差异，末期差值为零。不是模型权重发生变化的证据，也不外推到新任务池、其他后端或历史协议。']
    (OUT/'REVIEW.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'checks_passed':True,'dispersion':dispersion,
        'persistent_state_agreement':[r['effective_state_permanent_agreement_from'] for r in records]},indent=2))


if __name__=='__main__':
    main()
