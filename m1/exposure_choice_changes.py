"""Exploratory paired-choice changes; rate cancellation is not no behavior change."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'results_m1_exposure_length'


def rows(path):
    return list(csv.DictReader(path.open()))


def index(data,arm,cp):
    return {r['pair_idx']:r for r in data if r['phase']=='parity' and r['arm']==arm and int(r['checkpoint'])==cp}


def changes(a,b):
    if set(a)!=set(b) or len(a)!=452:
        raise ValueError('Need exactly452 matched pairs')
    more=sum(a[k]['chose_clone']=='1' and b[k]['chose_clone']=='0' for k in a)
    less=sum(a[k]['chose_clone']=='0' and b[k]['chose_clone']=='1' for k in a)
    return {'n_pairs':len(a),'toward_clone':more,'away_from_clone':less,
            'binary_clone_flips':more+less,
            'purchase_category_changes':sum(a[k]['chosen_kind']!=b[k]['chosen_kind'] for k in a),
            'net_clone_rate_difference':(more-less)/len(a)}


def main():
    records=[]
    for seed in range(2030,2038):
        previous=rows(ROOT/f'results_m1_expanded/seed{seed}/m1_exams.csv')
        empty=index(previous,'B0',0);old=index(previous,'M0',0)
        records.append({'seed':seed,'length':20,'versus_empty':changes(old,empty),
                        'source':'existing measured expanded study'})
        directory=OUTPUT/f'seed{seed}'
        if (directory/'COMPLETE.json').exists():
            current=rows(directory/'m1_exams.csv')
            for length in (40,80):
                cell=index(current,'M0',length)
                records.append({'seed':seed,'length':length,'versus_empty':changes(cell,empty),
                                'versus_same_seed20':changes(cell,old),'source':'new measured length study'})
    result={'exploratory_descriptive_only':True,'no_additional_p_values':True,'records':records,
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'choice_changes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# 逐题变化与总选择率抵消','',
        '这是补充的描述性核查，不修改冻结主分析，不新增确认性p值。所有方向均报告。',
        '相同clone率不代表逐题选择相同；toward/away在总率上可抵消。','',
        '|种子|污染轮数|从非克隆转向克隆|从克隆转向非克隆|clone二元选择翻转总数|净选择率差|',
        '|---|---:|---:|---:|---:|---:|']
    for record in records:
        c=record['versus_empty']
        lines.append(f"|{record['seed']}|{record['length']}|{c['toward_clone']}|{c['away_from_clone']}|{c['binary_clone_flips']}|{c['net_clone_rate_difference']*100:+.2f}pp|")
    lines+=['','非克隆包含金品及未购买；精确购买类别的变化数另存JSON。',
            '这些差异测量固定记忆输入对固定试卷的行为作用；没有同长度干净经验辅助对照，不能仅凭变化就声称污染特异的偏好形成。']
    (OUTPUT/'CHOICE_CHANGES.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
