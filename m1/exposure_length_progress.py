"""Read-only lightweight Slurm output progress for this exposure-length run."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
logroot=root/'.runtime/slurm'
failure=None
logs=[logroot/'length-prepare-144291.log',logroot/'length-summary-144293.log',
      *sorted(logroot.glob('length-run-144292_*.log'))]
for path in logs:
    if not path.exists():
        continue
    with path.open('rb') as stream:
        stream.seek(0,2);stream.seek(max(0,stream.tell()-6000))
        tail=stream.read().decode(errors='replace')
    if any(token in tail for token in ('Traceback (most recent call last)','CANCELLED AT','oom-kill','Out Of Memory','DUE TO TIME LIMIT')):
        failure=str(path.relative_to(root))
manifest=root/'data/m1_exposure_length/manifest.json'
try:
    m=json.loads(manifest.read_text()) if manifest.exists() else {}
except json.JSONDecodeError:
    m={}
seeds={}
for seed in range(2030,2038):
    directory=root/f'results_m1_exposure_length/seed{seed}'
    counts={}
    for name,key in [('m1_exams.csv','exams'),('m1_episodes.csv','new_exposure_episodes')]:
        path=directory/name
        counts[key]=max(0,sum(1 for _ in path.open())-1) if path.exists() else 0
    counts['complete']=(directory/'COMPLETE.json').exists()
    seeds[str(seed)]=counts
summarylog=logroot/'length-summary-144293.log'
done=summarylog.exists() and 'LENGTH_SUMMARY_COMPLETE' in summarylog.read_text()
print(json.dumps({'state':'failed' if failure else ('complete' if done else 'running'),
    'n_pairs':m.get('n_pairs'),'selected_new_tasks':len(m.get('selected_new_goal_indices',[])),
    'expected_exams_per_seed':2*m['n_pairs']+32 if m else None,
    'seeds':seeds,'failed_log':failure}))
