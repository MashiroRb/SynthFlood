"""Tiny read-only progress inspection; no model or catalog loading."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
logroot=root/'.runtime/slurm'
failure=None
for path in [logroot/'expanded-prepare-143944.log',logroot/'expanded-summary-143946.log',
             *sorted(logroot.glob('expanded-run-143945_*.log'))]:
    if path.exists():
        with path.open('rb') as stream:
            stream.seek(0,2)
            stream.seek(max(0,stream.tell()-5000))
            tail=stream.read().decode(errors='replace')
        if 'Traceback (most recent call last)' in tail or 'CANCELLED AT' in tail:
            failure=str(path.relative_to(root))
manifest=root/'data/m1_expanded/manifest.json'
m=json.loads(manifest.read_text()) if manifest.exists() else {}
seeds={}
for seed in range(2030,2038):
    directory=root/f'results_m1_expanded/seed{seed}'
    path=directory/'m1_exams.csv'
    rows=max(0,sum(1 for _ in path.open())-1) if path.exists() else 0
    seeds[str(seed)]={'rows':rows,'complete':(directory/'COMPLETE.json').exists()}
summarylog=logroot/'expanded-summary-143946.log'
done=summarylog.exists() and 'EXPANDED_SUMMARY_COMPLETE' in summarylog.read_text()
print(json.dumps({'state':'failed' if failure else ('complete' if done else 'running'),
    'n_pairs':m.get('n_pairs'),'n_gold':m.get('n_gold_asins'),
    'expected_rows_per_seed':4*m['n_pairs']+32 if m else None,
    'seeds':seeds,'failed_log':failure}))
