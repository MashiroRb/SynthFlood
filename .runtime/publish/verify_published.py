"""Verify the approved code, inputs and formal results already in Git."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path.cwd()
tree = {}
for entry in subprocess.check_output(['git', 'ls-tree', '-rz', 'HEAD']).split(b'\0'):
    if entry:
        metadata, name = entry.split(b'\t', 1)
        tree[name.decode()] = metadata.decode().split()[2]
with (ROOT / 'publication_v3/files.jsonl').open() as source:
    specs = [json.loads(line) for line in source]
for spec in specs:
    path = ROOT / spec['path']
    size = path.stat().st_size
    assert size == spec['bytes'] and size < 100 * 1024 * 1024, spec['path']
    blob = hashlib.sha1(f'blob {size}\0'.encode())
    raw = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            blob.update(block)
            raw.update(block)
    assert raw.hexdigest() == spec['sha256'], spec['path']
    assert tree[spec['path']] == blob.hexdigest(), spec['path']
from protocol_v3.common import validate
validate()
csv_path = ROOT / 'results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/all_formal_records.csv'
with csv_path.open() as source:
    keys = [r['case_key'] for r in csv.DictReader(source)]
assert len(keys) == len(set(keys)) == 189480
report = dict(validated=True, formal_records=189480, archived_files_verified=len(specs),
              frozen_hashes_valid=True, git_blob_bytes_match_sources=True,
              commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
(ROOT / '.runtime/publish/PUBLISHED_VERIFIED.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
