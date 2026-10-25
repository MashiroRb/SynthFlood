"""Prepare a byte-preserving publication list and scan only new artifacts."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

ROOT = Path.cwd()
WORK = ROOT / '.runtime/publish'
OUT = ROOT / 'results_protocol_v3_20261024_relaxed_v1'
PAT = (ROOT.parent / 'PAT.txt').read_bytes().strip()
PATTERNS = [re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}'), re.compile(rb'github_pat_[A-Za-z0-9_]{25,}'),
            re.compile(rb'hf_[A-Za-z0-9]{20,}'), re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]

def check(data, name):
    if (PAT and PAT in data) or any(p.search(data) for p in PATTERNS):
        raise ValueError('Potential credential in new artifact (value suppressed): ' + name)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

paths = set()
def add(path):
    if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts and path.suffix != '.pyc':
        paths.add(path)

for name in ('protocol_v3', 'data/protocol_v3_20261024_relaxed_v1', 'data/paired_n98_ratingfix_v2',
             'audit_dose_positions', 'audit_exam_v3_20261023', 'audit_paired_n98',
             'audit_protocol_v3_live_20261024', 'audit_washout40_logs', 'publication_v3'):
    for path in (ROOT / name).rglob('*'):
        add(path)
for name in ('CONTINUOUS_MONITOR_20261024.md', 'SCALING_20261024.md', 'V3_RUN_STATUS_2026-10-23.md', 'm1/LOCAL_RUNBOOK.md', '.gitattributes', '.gitignore'):
    add(ROOT / name)
for path in OUT.rglob('*'):
    rel = path.relative_to(OUT)
    if ('requests' in rel.parts or 'request_archives' in rel.parts or path.suffix == '.lock'
        or (rel.parts[0] == 'analysis_scaled' and path.name == 'exam.jsonl')):
        continue
    add(path)
# Preserve the source of adopted QA/generation evidence and the stopped strict pilot.
for base in sorted(ROOT.glob('results_protocol_v3_20261023*')):
    for path in base.rglob('*'):
        if path.suffix != '.lock':
            add(path)
for path in (ROOT / '.runtime/scaling').rglob('*'):
    if 'last_requests' not in path.parts and not (path.name in ('exam.jsonl', 'shopping.jsonl', 'resume_events.jsonl')) and path.suffix != '.lock':
        add(path)
for path in (ROOT / '.runtime/v3_manual_checks').glob('*'):
    add(path)
for name in ('manual_v3_check.py', 'manual_v3_window.py', 'manual_v3_design_audit.py',
             'manual_v3_seed_summary.py', 'export_v3_final_results.py', 'export_defense_summary.py',
             'summarize_completed_wash_seed.py', 'host_memory_diagnose.py', 'host_memory_findings_20261025.md',
             'protocol_v3_current_jobs.json', 'v3_monitor_config.json', 'protocol-v3-relaxed-v1-source.tar.gz',
             'environment.txt', 'WebShop/web_agent_site/engine/goal.py', 'WebShop/web_agent_site/engine/normalize.py',
             'slurm/v3-final-verify.sbatch', 'slurm/v3-final-exports.sbatch', 'slurm/v3-design-audit.sbatch',
             'publish/archive_requests.py', 'publish/archive_requests.sbatch', 'publish/archive_fast.py',
             'publish/archive_fast.sbatch', 'publish/prepare.py', 'publish/prepare.sbatch'):
    add(ROOT / '.runtime' / name)
# Retain original inference/server logs referenced by the final design audit.
for path in (ROOT / '.runtime/slurm').glob('v3-*.log'):
    add(path)

large = []
for path in sorted((OUT / 'analysis_scaled').glob('washout*/exam.jsonl')):
    target = path.with_suffix('.jsonl.gz')
    if not target.exists():
        with path.open('rb') as source, target.open('wb') as output:
            with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0, compresslevel=6) as archive:
                shutil.copyfileobj(source, archive, 1024 * 1024)
    with gzip.open(target, 'rb') as source:
        restored = hashlib.file_digest(source, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(source.read()).hexdigest()
    expected = sha(path)
    assert restored == expected
    large.append(dict(path=str(path.relative_to(ROOT)), archive=str(target.relative_to(ROOT)), sha256=expected, bytes=path.stat().st_size))
    add(target)
(ROOT / 'publication_v3/large_files.json').write_text(json.dumps(large, indent=2) + '\n')
add(ROOT / 'publication_v3/large_files.json')

from protocol_v3.common import validate
validate()
specs = []
for path in sorted(paths):
    rel = str(path.relative_to(ROOT))
    assert path.stat().st_size < 100 * 1024 * 1024, rel
    data = path.read_bytes()
    check(data, rel)
    if path.name.endswith('.tar.gz'):
        with tarfile.open(path, 'r:gz') as archive:
            for member in archive:
                if member.isfile():
                    check(archive.extractfile(member).read(), rel + ':' + member.name)
    elif path.suffix == '.gz':
        with gzip.open(path, 'rb') as source:
            check(source.read(), rel + ':decompressed')
    specs.append(dict(path=rel, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
manifest = ROOT / 'publication_v3/files.jsonl'
with manifest.open('w') as output:
    for spec in specs:
        output.write(json.dumps(spec) + '\n')
add(manifest)
(WORK / 'base-files.txt').write_text(''.join(str(p.relative_to(ROOT)) + '\n' for p in sorted(paths)))
report = dict(validated=True, selected_files=len(paths), selected_bytes=sum(s['bytes'] for s in specs),
              frozen_hashes_valid=True, credential_scan='passed; values never logged', large_files=large)
(WORK / 'PREPARED.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
