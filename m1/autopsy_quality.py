"""Exploratory input-quality audit; never filter or alter the frozen main exam."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from synthflood.select_env import SelectEnv


def score(goal,candidate):
    env=SelectEnv(goal,[candidate],n_candidates=1)
    env.step('select[1]')
    value,info=env.reward()
    if not info:
        raise RuntimeError('Missing official reward details')
    return value


if __name__=='__main__':
    ctx=json.loads((ROOT/'data/m1_v2/context.json').read_text())
    original=json.loads((ROOT/'audit_m1/options_autopsy_v2.json').read_text())
    expected={(r['phase'],r['pair_idx']):r['with_options'] for r in original['rows']}
    rows=[]
    for phase in ('exam','parity'):
        for pi,clone in ctx[phase+'_clones'].items():
            asin=ctx['pairs'][int(pi)]['gold_asin']
            goal=ctx['goals_by_asin'][asin]
            gold={'item':ctx['by_asin'][asin],'price_float':ctx['product_prices'][asin],
                  'kind':'gold','synthetic':False}
            rg,rc=score(goal,gold),score(goal,clone)
            if abs(rc-expected[phase,int(pi)])>1e-12:
                raise RuntimeError('Official reward differs from the independent options autopsy')
            rows.append({'phase':phase,'pair_idx':int(pi),'gold_asin':asin,
                'gold_reward':rg,'clone_reward':rc,'gap_clone_minus_gold':rc-rg})
    summary={'scope':'Exploratory input quality, added after repeated-measurement diagnostic began; does not change the primary cohort or analysis.',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'context_sha256':hashlib.sha256((ROOT/'data/m1_v2/context.json').read_bytes()).hexdigest(),
        'n':len(rows),'clone_reward_ge_gold':sum(r['clone_reward']>=r['gold_reward']-1e-12 for r in rows),
        'gold_reward_below_one':sum(r['gold_reward']<1-1e-12 for r in rows),'rows':rows}
    summary['by_phase']={phase:{'n':sum(r['phase']==phase for r in rows),
        'clone_reward_ge_gold':sum(r['phase']==phase and r['clone_reward']>=r['gold_reward']-1e-12 for r in rows)}
        for phase in ('exam','parity')}
    (ROOT/'audit_m1/quality_autopsy_v2.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('EXPLORATORY_QUALITY',json.dumps({k:v for k,v in summary.items() if k!='rows'}),flush=True)
