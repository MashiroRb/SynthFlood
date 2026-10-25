"""Compare assistant snapshots by final purchase outcome, including older snapshots."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
directory=root/'.runtime/v3_manual_checks'
paths=sorted(directory.glob('[0-9]*Z.json'))
if len(paths)<2:
    print('No previous manual snapshot');raise SystemExit(0)
before,after=[json.loads(p.read_text()) for p in paths[-2:]]
lines=[f'window={before["timestamp_utc"]} -> {after["timestamp_utc"]}']
windows={}
for scope,new in after['rates'].items():
    if scope not in before['rates']:continue
    old=before['rates'][scope]
    n=new['new_evaluations']-old['new_evaluations']
    valid=new['valid']-old['valid']
    failed=n-valid
    missing=round(new['missing_confidence']*new['valid'])-round(old['missing_confidence']*old['valid'])
    assert 0<=failed<=n and 0<=missing<=valid
    windows[scope]=dict(new_evaluations=n,valid=valid,purchase_failures=failed,
        purchase_failure=failed/max(1,n),missing_confidence=missing/max(1,valid))
    if scope in ('all','memory','stateless'):
        lines.append(f'{scope}: final_no_purchase={failed}/{n}={failed/max(1,n):.4%}; missing_confidence={missing}/{valid}={missing/max(1,valid):.4%}')
report=dict(from_utc=before['timestamp_utc'],to_utc=after['timestamp_utc'],rates=windows)
(directory/'window.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(directory/'window.txt').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines),flush=True)
