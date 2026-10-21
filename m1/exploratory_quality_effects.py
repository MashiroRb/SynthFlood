"""Post-primary descriptive decomposition; no changes to registered tests."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    directory=ROOT/'results_m1_v2'
    primary=json.loads((directory/'summary.json').read_text())
    quality=json.loads((ROOT/'audit_m1/quality_autopsy_v2.json').read_text())
    manifest=json.loads((ROOT/'data/m1_v2/manifest.json').read_text())
    if quality['context_sha256']!=manifest['context_sha256']:
        raise RuntimeError('Quality audit and trial instrument differ')
    strata={phase:{'lower_reward':set(),'not_lower_reward':set()} for phase in ('exam','parity')}
    for row in quality['rows']:
        label='lower_reward' if row['clone_reward']<row['gold_reward']-1e-12 else 'not_lower_reward'
        strata[row['phase']][label].add(str(row['pair_idx']))
    cells=[]
    state_cells=[]
    global_inputs={}
    within_seed_inconsistent={}
    for seed in primary['seeds']:
        rows=list(csv.DictReader((directory/f'seed{seed}/m1_exams.csv').open()))
        local_inputs={}
        for row in rows:
            value=(row['chosen_kind'],row['chose_clone'],row['purchased'],row['reward'])
            local_inputs.setdefault(row['input_sha256'],set()).add(value)
            global_inputs.setdefault(row['input_sha256'],set()).add(value)
        within_seed_inconsistent[str(seed)]=sum(len(values)>1 for values in local_inputs.values())
        for checkpoint in (0,4,10,20):
            snapshots={arm:json.loads((directory/f'seed{seed}'/f'checkpoint_{arm}_{checkpoint:02d}.json').read_text()) for arm in ('M0','B0')}
            contexts={arm:snapshots[arm]['injected_context'] for arm in snapshots}
            windows={arm:[entry['text'] for entry in snapshots[arm]['entries'] if entry['type']=='observation'][-5:] for arm in snapshots}
            same_context=contexts['M0']==contexts['B0']
            same_window=windows['M0']==windows['B0']
            state_cells.append({'seed':seed,'checkpoint':checkpoint,'equal_injected_context':same_context,
                'equal_last_five_observations':same_window,'equal_effective_memory_state':same_context and same_window})
        for phase in ('exam','parity'):
            for checkpoint in (0,4,10,20):
                maps={arm:{r['pair_idx']:r for r in rows if r['arm']==arm and r['phase']==phase and int(r['checkpoint'])==checkpoint} for arm in ('M0','B0')}
                for label,indices in {'all':set(maps['M0']),**strata[phase]}.items():
                    if not indices:
                        continue
                    n=len(indices)
                    rates={arm:sum(int(maps[arm][pi]['chose_clone']) for pi in indices)/n for arm in maps}
                    regrets={arm:sum(1-float(maps[arm][pi]['reward']) for pi in indices)/n for arm in maps}
                    cells.append({'seed':seed,'phase':phase,'checkpoint':checkpoint,'stratum':label,'n':n,
                        'M0_clone_rate':rates['M0'],'B0_clone_rate':rates['B0'],
                        'clone_rate_difference':rates['M0']-rates['B0'],
                        'M0_recorded_regret':regrets['M0'],'B0_recorded_regret':regrets['B0'],
                        'regret_difference':regrets['M0']-regrets['B0']})
    means={}
    for phase in ('exam','parity'):
        means[phase]={}
        for label in ('all','lower_reward','not_lower_reward'):
            selected=[c for c in cells if c['phase']==phase and c['stratum']==label and c['checkpoint']==20]
            means[phase][label]={key:sum(c[key] for c in selected)/len(selected)
                for key in ('clone_rate_difference','regret_difference')}
    output={'scope':'Exploratory, declared after diagnostic began; descriptive only, no new p-values or confirmatory claims.',
        'context_sha256':manifest['context_sha256'],
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'reward_note':'Recorded CSV rewards rounded to 3 decimals; nonpurchases retained with zero reward.',
        'mean_endpoint_effects':means,'cells':cells,'memory_state_comparisons':state_cells,
        'within_seed_inconsistent_inputs':within_seed_inconsistent,
        'cross_seed_inconsistent_inputs':sum(len(values)>1 for values in global_inputs.values())}
    (directory/'exploratory_quality_effects.json').write_text(json.dumps(output,indent=2)+'\n')
    with (directory/'exploratory_quality_cells.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(cells[0]));writer.writeheader();writer.writerows(cells)
    print('EXPLORATORY_EFFECTS',json.dumps(means),flush=True)
