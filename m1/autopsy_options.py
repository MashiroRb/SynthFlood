"""CPU-only reward ablation for the candidate-conversion options bug."""
import copy
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from synthflood.select_env import SelectEnv


if __name__=='__main__':
    ctx=json.loads((ROOT/'data/m1_v2/context.json').read_text())
    rows=[]
    for phase in ('exam','parity'):
        for pi,clone in ctx[phase+'_clones'].items():
            asin=ctx['pairs'][int(pi)]['gold_asin']
            goal=ctx['goals_by_asin'][asin]
            without=copy.deepcopy(clone)
            without['item'].pop('options',None)
            values={}
            for label,candidate in [('with_options',clone),('without_options',without)]:
                env=SelectEnv(goal,[candidate],n_candidates=1)
                env.step('select[1]')
                reward,info=env.reward()
                if not info:
                    raise RuntimeError('Official reward returned no details; cannot certify reward ablation')
                values[label]=reward
            rows.append({'phase':phase,'pair_idx':int(pi),'gold_asin':asin,
                         'n_goal_options':len(goal.get('goal_options',[])),**values})
    output={'note':'Ablation on frozen v2 instrument, not exact historical reward reconstruction.',
            'rows':rows,'pairs_affected':sum(r['with_options']!=r['without_options'] for r in rows),
            'mean_reward_loss_from_dropping_options':sum(r['with_options']-r['without_options'] for r in rows)/len(rows)}
    (ROOT/'audit_m1/options_autopsy_v2.json').write_text(json.dumps(output,indent=2)+'\n')
    print('OPTION_AUTOPSY',output['pairs_affected'],'/',len(rows),output['mean_reward_loss_from_dropping_options'],flush=True)
