"""Supplementary post-run diagnostics; never modifies frozen experiment files."""
import collections
import csv
import json
import math
import re
from pathlib import Path

from paired_sweep.common import ROOT, OUT, DATA, validate_sources
from paired_sweep.analyze import estimate
from paired_sweep.defenses import visible_number
from synthflood.select_env import product_fields


def brief(rows):
    n = len(rows)
    return dict(n=n, reward=sum(r['reward'] for r in rows)/n,
        success=sum(r['success_full'] for r in rows)/n,
        synthetic_share=sum(r['chosen_is_synthetic'] for r in rows)/n,
        no_purchase=sum(not r['purchased'] for r in rows),
        malformed_episodes=sum(r['malformed']>0 for r in rows),
        forced_episodes=sum(r['malformed']>=2 for r in rows),
        malformed_actions=sum(r['malformed'] for r in rows))


def main():
    manifest = validate_sources()
    assert json.loads((OUT/'COMPLETE.json').read_text())['validated']
    allrows=[]; sentinel_rows=[]; server_errors=[]
    for lane in range(8):
        directory=OUT/f'worker{lane}'
        for phase in ('main','defense'):
            allrows.extend(json.loads(s) for s in (directory/f'{phase}.jsonl').read_text().splitlines())
        sentinel_rows.extend(json.loads(s) for s in (directory/'sentinels.jsonl').read_text().splitlines())
        for line in (directory/'server.log').read_text(errors='replace').splitlines():
            if re.search(r'\bERROR\b|Traceback|CUDA out of memory|RuntimeError|Exception:',line):
                server_errors.append(dict(lane=lane,text=line))
    index={(r['seed'],r['task_id'],r['k'],r['rotation'],r['arm']):r for r in allrows}
    cells=collections.defaultdict(list); seeds=collections.defaultdict(list)
    for r in allrows:
        cells[r['arm'],r['k']].append(r)
        seeds[r['seed'],r['arm'],r['k']].append(r)
    result={'manifest_sha_check':True,'rows':len(allrows),'quality_by_cell':[],
        'seed_cells':[], 'sentinels_passed':len(sentinel_rows),'server_errors':server_errors,
        'new_only_quality':brief([r for r in allrows if r['origin']=='new']),
        'main_quality':brief([r for r in allrows if r['phase']=='main']),
        'supplementary_only':'All additional comparisons/sensitivity checks are post hoc, not the frozen primary analysis.'}
    for (arm,k),rows in sorted(cells.items()):
        result['quality_by_cell'].append(dict(arm=arm,k=k,**brief(rows)))
    for (seed,arm,k),rows in sorted(seeds.items()):
        result['seed_cells'].append(dict(seed=seed,arm=arm,k=k,**brief(rows)))
    # Matched exclusion is only sensitivity analysis; never replace primary estimates.
    comparisons=[('none',k,'none',0) for k in (2,4,6)]
    comparisons += [(arm,k,ref,k) for k in (0,6) for arm,ref in (
        ('provenance','none'),('detector_struct','none'),('detector_text','none'),
        ('detector_struct','random_struct'),('detector_text','random_text'),
        ('provenance_order','none'),('provenance_badge','none'))]
    effects={}
    for arm,k,ref,refk in comparisons:
        full=collections.defaultdict(list);clean=collections.defaultdict(list);removed=0
        for task in manifest['eligible_task_ids']:
            for seed in (1,2):
                for rotation in range(10):
                    a=index[seed,task,k,rotation,arm];b=index[seed,task,refk,rotation,ref]
                    full[task].append(a['reward']-b['reward'])
                    if a['malformed']==0 and b['malformed']==0:
                        clean[task].append(a['reward']-b['reward'])
                    else:removed+=1
        effects[f'{arm}:k{k}_minus_{ref}:k{refk}']={
            'all':estimate([sum(v)/len(v) for v in full.values()]),
            'exclude_either_malformed':estimate([sum(v)/len(v) for v in clean.values()]),
            'removed_matched_pairs':removed,'tasks_retained':len(clean)}
    result['posthoc_reward_comparisons']=effects
    # Actual rating/review fields shown to the agent, by occurrence in task/seed blocks.
    fields=collections.defaultdict(collections.Counter);ratingvals=collections.defaultdict(collections.Counter)
    gold={}
    for lane in range(8):
        blocks=json.loads((DATA/f'lane{lane}.json').read_text())
        for block in blocks:
            gold[block['seed'],block['task_id']]=block['base'][0]['cid']
            for c in block['base']+block['synthetics']:
                group='synthetic' if c['synthetic'] else 'real_including_gold'
                f=product_fields(c['item']);counts=fields[group];counts['n']+=1
                for field in ('rating','nrev'):
                    try:val=float(f[field]);valid=math.isfinite(val)
                    except (TypeError,ValueError):valid=False
                    counts[field+'_numeric']+=valid
                    counts[field+'_positive']+=valid and val>0
                ratingvals[group][str(f['rating'])]+=1
    result['visible_fields']={g:dict(c) for g,c in fields.items()}
    result['rating_values']={g:dict(c) for g,c in ratingvals.items()}
    result['same_final_input_vs_reference']=[]
    for arm,ref in [('ppr_0.5','ppr_1.0'),('ppr_0.5','ppr_2.0'),('ppr_0.5','ppr_4.0'),
                    ('ppr_6.0','ppr_8.0'),('reviewtrust','none'),('provenance','ppr_0.5')]:
        for k in (0,6):
            rows=cells[arm,k]
            result['same_final_input_vs_reference'].append(dict(arm=arm,reference=ref,k=k,n=len(rows),
                identical=sum(r['post_sha256']==index[r['seed'],r['task_id'],k,r['rotation'],ref]['post_sha256'] for r in rows)))
    positions=collections.defaultdict(list);layouts=collections.defaultdict(list)
    for r in allrows:
        if r['arm']!='none':continue
        g=gold[r['seed'],r['task_id']]
        rank=r['post_ids'].index(g)+1
        positions[r['k'],rank].append(r)
        layouts[r['seed'],r['task_id'],r['k']].append(r)
    result['main_by_gold_position']=[dict(k=k,gold_position=rank,**brief(rows))
        for (k,rank),rows in sorted(positions.items())]
    result['main_choice_changes_across_rotations']=[dict(k=k,blocks=196,
        changed=sum(len({r['chosen_cid'] for r in v})>1 for key,v in layouts.items() if key[2]==k)) for k in (0,2,4,6)]
    for arm in ('detector_struct','detector_text','random_struct','random_text'):
        for k in (0,6):
            rows=cells[arm,k]
            result.setdefault('filter_retention',[]).append(dict(arm=arm,k=k,
                mean_candidates=sum(r['n_candidates_after'] for r in rows)/len(rows),
                fallback=sum(bool(r['defense_metadata']['fallback']) for r in rows),
                distribution=dict(collections.Counter(r['n_candidates_after'] for r in rows))))
    output=ROOT/'audit_paired_n98'
    (output/'quality_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for name in ('quality_by_cell','seed_cells','main_by_gold_position'):
        with (output/f'{name}.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(result[name][0]));writer.writeheader();writer.writerows(result[name])
    print(json.dumps({k:result[k] for k in ('rows','sentinels_passed','server_errors','new_only_quality','main_quality','visible_fields','filter_retention','main_choice_changes_across_rotations')},ensure_ascii=False),flush=True)
    print('POSTRUN_AUDIT_COMPLETE',flush=True)


if __name__=='__main__':
    main()
