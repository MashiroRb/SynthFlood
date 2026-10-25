import csv,json
from pathlib import Path
D=Path('.runtime/v3_seed_summaries/20261024T195755Z')
fields=['seed','phase','condition','planned','valid','excluded','purchase_failure_rate','reward','success_rate','synthetic_choice_rate',
    'confidence_n','confidence_missing','confidence','confidence_sample_success','ece5','n_independent_tasks','source_report']
rows=[]
for seed in (1,2):
    source=D/f'defense_seed{seed}.json';report=json.loads(source.read_text())
    assert report['complete'] and report['rows']==report['planned_rows']==29400
    for condition,cell in {**report['none_controls'],**report['cells']}.items():
        rows.append(dict(seed=seed,phase='main_control' if condition.startswith('none:') else 'defense',condition=condition,
            source_report=str(source),**{k:cell.get(k) for k in fields if k in cell}))
assert len(rows)==64
path=D/'defense_seed_summary.csv'
with path.open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
print(json.dumps(dict(csv=str(path),summary_rows=len(rows),defense_records=58800,controls='Same-seed main experiment; not additional independent samples'),ensure_ascii=False))
