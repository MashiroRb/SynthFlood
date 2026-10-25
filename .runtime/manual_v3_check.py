"""One-shot assistant statistics: final purchase completion, never browsing repetition."""
import collections
import datetime
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
config = json.loads((root / '.runtime/v3_monitor_config.json').read_text())
counts = collections.Counter()
groups = collections.defaultdict(collections.Counter)
reasons = collections.defaultdict(collections.Counter)
incomplete = 0
examples = []


def rates(c):
    n = c.get('new_evaluations', 0)
    valid = c.get('valid', 0)
    failed = n - valid
    assert c.get('purchase_failure', 0) == failed
    return dict(new_evaluations=n, valid=valid, purchase_failures=failed,
        purchase_failure=failed / max(1, n),
        missing_confidence=c.get('missing_confidence', 0) / max(1, valid),
        confidence_mean=c.get('confidence_sum', 0) / max(1, c.get('confidence_reports', 0)),
        confidence_report_success=c.get('confidence_success_sum', 0) / max(1, c.get('confidence_reports', 0)))


for directory in sorted((root / config['result_directory']).iterdir()):
    if not directory.is_dir() or not directory.name.startswith(('worker', 'washout')):
        continue
    for phase in ('main', 'probe', 'single', 'clone', 'defense', 'shopping', 'exam'):
        path = directory / (phase + '.jsonl')
        if not path.exists():
            continue
        with path.open() as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    if not line.endswith('\n'):
                        incomplete += 1
                        continue
                    raise
                counts['logical_rows'] += 1
                if row['origin'] != 'new':
                    continue
                assert row['valid'] == row['purchased']
                failed = not row['purchased']
                c = collections.Counter(new_evaluations=1, valid=int(row['purchased']), purchase_failure=int(failed))
                c['missing_confidence'] = int(row['valid'] and row.get('confidence') is None)
                if row['valid'] and row.get('confidence') is not None:
                    c.update(confidence_reports=1, confidence_sum=row['confidence'],
                             confidence_success_sum=int(bool(row['success_full'])))
                scopes = ['all', 'memory' if phase in ('shopping', 'exam') else 'stateless',
                          'phase:' + phase, 'writer:' + directory.name]
                counts.update(c)
                for scope in scopes[1:]:
                    groups[scope].update(c)
                if failed:
                    reason = row.get('exclusion_reason') or 'no_legal_purchase'
                    for scope in scopes:
                        reasons[scope][reason] += 1
                    if len(examples) < 20:
                        examples.append(dict(case_key=row['case_key'], reason=reason,
                            effective_views=row['effective_views'], malformed=row['malformed']))

from protocol_v3.common import validate
validate()
report = dict(schema_version=2, timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    monitoring_policy='Final legal purchase completion; no repeated-browsing or intermediate-format behavior statistics',
    counts=counts, rates={'all': rates(counts), **{k: rates(v) for k, v in groups.items()}},
    purchase_failure_reasons=dict(reasons), incomplete_lines=incomplete, examples=examples,
    source_input_hashes_valid=True,
    failures=[str(p.relative_to(root)) for p in (root / config['result_directory']).glob('*/FAILED.json')])
directory = root / '.runtime/v3_manual_checks'
directory.mkdir(exist_ok=True)
path = directory / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(directory / 'latest.json').write_text(path.read_text())
summary = [report['timestamp_utc'], f'logical={counts["logical_rows"]}; new={counts["new_evaluations"]}; purchased={counts["valid"]}; final_no_purchase={counts["purchase_failure"]}']
for name in ('all', 'memory', 'stateless'):
    values = report['rates'].get(name, rates(collections.Counter()))
    summary.append(f'{name}: final_no_purchase={values["purchase_failures"]}/{values["new_evaluations"]}={values["purchase_failure"]:.4%}; missing_conf={values["missing_confidence"]:.4%}; confidence={values["confidence_mean"]:.4f}; reward_success={values["confidence_report_success"]:.4f}; failure_reasons={dict(reasons[name])}')
summary.append(f'hashes_valid=True; failures={report["failures"]}')
(directory / 'summary.txt').write_text('\n'.join(summary) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
