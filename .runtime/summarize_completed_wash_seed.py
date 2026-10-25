"""One-shot CPU export for explicitly requested completed seeds; no model calls."""
import csv,json,sys
from pathlib import Path
latest=json.loads(Path('.runtime/v3_seed_summaries/latest.json').read_text())
D=Path(latest['snapshot_directory'])
fields=['seed','group','planned','valid','excluded','reward','success_rate','synthetic_choice_rate','confidence_n','confidence_missing','confidence','confidence_sample_success','ece5']
for seed in map(int,sys.argv[1:]):
    report=json.loads((D/f'seed{seed}.json').read_text());assert report['complete_seed']
    brief={'seed':seed,'snapshot_utc':report['timestamp_utc'],'source':str(D/f'seed{seed}.json'),'groups':{}}
    rows=[]
    for group,data in report['groups'].items():
        cell=data['exam_all'];row=dict(seed=seed,group=group,**{k:cell[k] for k in fields if k in cell});rows.append(row)
        brief['groups'][group]=dict(exam=row,shopping={p:{k:v[k] for k in ('planned','valid','excluded')} for p,v in data['shopping'].items()},
            endpoints={str(cp):{k:data['checkpoints'][f'cp{cp}:all'][k] for k in ('valid','excluded','reward','success_rate','synthetic_choice_rate','confidence')} for cp in (0,40)})
    brief['strict_pairs']={str(cp):report['paired_M0_minus_B0'][f'cp{cp}:all'] for cp in (0,40)}
    csvpath=D/f'seed{seed}_group_summary.csv'
    with csvpath.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    brief['group_csv']=str(csvpath);brief['checkpoint_csv']=str(D/f'seed{seed}_checkpoints.csv')
    (D/f'seed{seed}_brief.json').write_text(json.dumps(brief,ensure_ascii=False,indent=2))
    print(json.dumps(brief,ensure_ascii=False,indent=2))
