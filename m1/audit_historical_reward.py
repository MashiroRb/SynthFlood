"""Recover an exact options-only score counterfactual when gold reward is 1.

Original trajectories are immutable: correcting a reward after the fact does
not regenerate the memories that were written using the erroneous reward.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNS={'seed1':'results_m1','seed2':'results_m1_s2','seed2b':'results_m1_s2b'}


if __name__=='__main__':
    output={'scope':'Exploratory options-only counterfactual for released exposure rewards; not a replay of the resulting memories.',
        'certificate':'The generator inherits gold variant options. A gold counterfactual reward of 1 certifies those options fully satisfy the same goal. Restore only the missing option term using released reward components.',
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'runs':{}}
    for name,folder in RUNS.items():
        path=ROOT/folder/'m1_reward_autopsy.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        synthetic=[r for r in rows if r['chosen_kind'].startswith('synthetic')]
        certified=[];uncertified=[]
        for r in synthetic:
            if abs(r['gold_cf']-1)>1e-12:
                uncertified.append({'arm':r['arm'],'ep':r['ep'],'reason':'Gold reward below 1; original option match not certified'})
                continue
            info=r['rinfo']
            w=info.get('w_option',0.0)
            restored=r['reward']+info['r_type']*w*(1-info.get('r_option',0.0))
            if restored>1+1e-9:
                raise ValueError('Invalid corrected score')
            certified.append({'arm':r['arm'],'ep':r['ep'],'old_reward':r['reward'],
                'options_restored_reward':min(1.0,restored),'gold_reward':r['gold_cf'],
                'option_weight':w,'type_factor':info['r_type']})
        result={'synthetic_purchases':len(synthetic),'certified_n':len(certified),
            'uncertified':uncertified,'original_reward_ge_gold':sum(r['reward']>=r['gold_cf']-1e-12 for r in synthetic),
            'original_mean_gap_all':sum(r['reward']-r['gold_cf'] for r in synthetic)/len(synthetic),
            'rows':certified,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        if certified:
            result['original_reward_ge_gold_certified']=sum(r['old_reward']>=r['gold_reward']-1e-12 for r in certified)
            result['restored_reward_ge_gold_certified']=sum(r['options_restored_reward']>=r['gold_reward']-1e-12 for r in certified)
            result['old_mean_gap_certified']=sum(r['old_reward']-r['gold_reward'] for r in certified)/len(certified)
            result['restored_mean_gap_certified']=sum(r['options_restored_reward']-r['gold_reward'] for r in certified)/len(certified)
        output['runs'][name]=result
        print(name,json.dumps({k:v for k,v in result.items() if k not in ('rows','uncertified','input_sha256')}),flush=True)
    (ROOT/'audit_m1/historical_options_counterfactual.json').write_text(json.dumps(output,indent=2)+'\n')
