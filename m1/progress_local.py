"""Cheap filesystem-only progress probe; no inference, Slurm calls or rate reads."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def count_rows(path):
    if not path.exists():
        return 0
    with path.open() as stream:
        return max(0,sum(1 for _ in stream)-1)


if __name__=='__main__':
    out=ROOT/'results_m1_v2'
    status={'diagnostic':count_rows(out/'diagnostic/m1_exams.csv'),
        'seeds':{str(seed):{'exams':count_rows(out/f'seed{seed}/m1_exams.csv'),
            'episodes':count_rows(out/f'seed{seed}/m1_episodes.csv')} for seed in range(2030,2038)},
        'state':'running'}
    final=ROOT/'audit_m1/FINAL_REPORT.md'
    if final.exists():
        status['state']='complete'
    else:
        diagnostic=out/'diagnostic/summary.json'
        if diagnostic.exists() and not json.loads(diagnostic.read_text())['stable']:
            status['state']='measurement_failed'
        logs=list((ROOT/'.runtime/slurm').glob('run-142566*'))+list((ROOT/'.runtime/slurm').glob('run-142567*'))
        logs+=list((ROOT/'.runtime/slurm').glob('summary-142569*'))
        logs+=list((ROOT/'.runtime/slurm').glob('explore-142573*'))
        logs+=list((ROOT/'.runtime/slurm').glob('final-report-142580*'))
        for path in logs:
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-12000))
                tail=stream.read().decode(errors='replace')
            if 'Traceback (most recent call last)' in tail or 'CANCELLED AT' in tail:
                status['state']='job_failed';status['failed_log']=str(path.relative_to(ROOT));break
    print(json.dumps(status,separators=(',',':')))
