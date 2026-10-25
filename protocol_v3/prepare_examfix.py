"""Keep N98 shopping fixed; prepare an outcome-independent official exam reservoir."""
import collections
import copy
import random
import shutil

from .common import *


def prepare():
    if (DATA/'manifest.json').exists() or (DATA/'exam_reservoir.json').exists():
        raise RuntimeError('Refusing to overwrite completed examfix preparation')
    # A failed CPU preparation can be rerun only before any reservoir is
    # finalized or QA/model requests exist. Its Slurm log remains preserved.
    if (OUT/'preflight'/'LAUNCH.json').exists():
        raise RuntimeError('Refusing preparation after model QA has begun')
    DATA.mkdir(parents=True,exist_ok=True)
    copied=('blocks.json','typed.json','probes.json','selected_raw.json','washout.json',
            'eligibility_audit.json','prepared.json','input_validation.json','sampling.json')
    for name in copied:
        shutil.copyfile(OLD_DATA/name,DATA/name)
        assert file_sha(DATA/name)==file_sha(OLD_DATA/name)
    shutil.copyfile(OLD_DATA/'exam_targets.json',DATA/'previous_exam_targets.json')
    human=read(ROOT/'data/official/items_human_ins.json')
    blocks=read(DATA/'blocks.json')
    forbidden={b['goal']['asin'] for b in blocks}
    goals={b['task_id']:b['goal'] for b in blocks if b['seed']==1}
    slots=list(goals.values())
    rng('exam_category_slots',20261023).shuffle(slots)
    slots+=rng('exam_extra_slots',20261023).sample(slots,2)
    from paired_sweep.freeze import array_items,pricing_values
    raws=[];prices={};seen=set();price_rng=random.Random(2027)
    for raw in array_items(ROOT/'data/official/items_shuffle.json'):
        a=raw['asin']
        if a=='nan' or len(a)>10 or a in seen:
            continue
        seen.add(a)
        values=pricing_values(raw.get('pricing'))
        price=values[0] if len(values)==1 else price_rng.uniform(*values)
        if a in human and a not in forbidden and any(x.get('instruction_attributes') for x in human[a]):
            raws.append(raw);prices[a]=round(price,2)
    del seen
    write(DATA/'exam_reservoir_raw.json',raws)
    from synthflood.ws_loader import load_products
    _,products,_,_=load_products(str(DATA/'exam_reservoir_raw.json'),
        str(ROOT/'data/official/items_ins_v2.json'),str(ROOT/'data/official/items_human_ins.json'))
    from synthflood.select_env import SelectEnv
    from web_agent_site.engine.goal import get_human_goals
    random.seed(20261023)
    all_goals=get_human_goals(list(products.values()),prices)
    by_asin=collections.defaultdict(list)
    for g in all_goals:
        by_asin[g['asin']].append(g)
    available=list(by_asin)
    rng('examfix_reservoir',20261023).shuffle(available)
    selected=[];matching=[]
    # Ten full, deterministic passes over the 100 category slots give an
    # ordered reservoir of up to1000 targets, before any model QA response.
    for cycle in range(10):
        for slot,g in enumerate(slots):
            fine=[a for a in available if products[a]['product_category']==g['product_category']]
            coarse=[a for a in available if products[a]['category']==g['category']]
            pool=fine or coarse or available
            if not pool:
                break
            a=pool[0];available.remove(a);selected.append(a)
            matching.append(dict(asin=a,cycle=cycle,slot=slot,desired=g['product_category'],
                actual=products[a]['product_category'],match='fine' if fine else 'coarse' if coarse else 'global'))
    reservoir=[]
    for i,a in enumerate(selected):
        goal=copy.deepcopy(rng('exam_instruction',20261023,a).choice(by_asin[a]))
        item=copy.deepcopy(products[a]);item['Price']=f'${prices[a]:.2f}';item['price']=prices[a]
        gold=dict(cid='real:'+a,item=item,kind='gold',synthetic=False,price_float=prices[a],
                  source_u=uniform('source',20261023,i,a))
        env=SelectEnv(goal,[copy.deepcopy(gold)],n_candidates=1);env.step('select[1]')
        reward=env.reward()[0]
        reservoir.append(dict(reservoir_index=i,task_id=i,goal=goal,gold=gold,gold_reward=reward))
    write(DATA/'exam_reservoir.json',reservoir)
    write(DATA/'exam_reservoir_sampling.json',dict(seed=20261023,category_slots=[g['product_category'] for g in slots],
        coarse_slots=[g['category'] for g in slots],matching=matching,passes=10,forbidden_targets=sorted(forbidden),
        copied_unchanged={n:file_sha(DATA/n) for n in copied},
        previous_input_directory=str(OLD_DATA.relative_to(ROOT)),
        previous_target_sha256=file_sha(OLD_DATA/'exam_targets.json'),
        policy='Fixed ordered reservoir before QA; no selection based on synthetic generation or shopping outcomes'))
    print('EXAMFIX_RESERVOIR_PREPARED',len(reservoir),flush=True)


if __name__=='__main__':
    prepare()
