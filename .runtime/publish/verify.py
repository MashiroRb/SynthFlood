"""Verify every archive member without extracting or rerunning experiments."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path.cwd()
OUT = ROOT / 'results_protocol_v3_20261024_relaxed_v1'
ARCHIVES = OUT / 'request_archives'

def stream_sha(source):
    h = hashlib.sha256()
    for block in iter(lambda: source.read(1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()

def sha(path):
    with path.open('rb') as source:
        return stream_sha(source)

done = json.loads((ARCHIVES / 'COMPLETE.json').read_text())
assert sha(ARCHIVES / 'members.jsonl') == done['member_manifest_sha256']
members = {}
with (ARCHIVES / 'members.jsonl').open() as source:
    for line in source:
        spec = json.loads(line)
        assert spec['path'] not in members
        members[spec['path']] = spec

def verify_archive(spec):
    archive = ARCHIVES / spec['path']
    assert archive.stat().st_size == spec['bytes'] and sha(archive) == spec['sha256']
    seen = set()
    process = subprocess.Popen(['zstd', '-q', '-d', '-c', str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as source:
            for entry in source:
                expected = members[entry.name]
                assert entry.isfile() and entry.name not in seen
                assert expected['archive'] == archive.name and expected['size'] == entry.size
                assert (ROOT / entry.name).resolve().is_relative_to(OUT.resolve())
                with source.extractfile(entry) as payload:
                    assert stream_sha(payload) == expected['sha256']
                seen.add(entry.name)
        with open('/dev/null', 'wb') as sink:
            shutil.copyfileobj(process.stdout, sink)
    finally:
        process.stdout.close()
        assert process.wait() == 0
    assert len(seen) == spec['members']
    print('VERIFIED', spec['path'], len(seen), flush=True)
    return seen

with ThreadPoolExecutor(max_workers=4) as executor:
    groups = list(executor.map(verify_archive, done['archives']))
seen = set()
for group in groups:
    assert not seen.intersection(group)
    seen.update(group)
assert seen == members.keys() and len(seen) == done['files']
with (ROOT / 'publication_v3/files.jsonl').open() as source:
    file_specs = [json.loads(line) for line in source]
for spec in file_specs:
    path = ROOT / spec['path']
    assert path.stat().st_size == spec['bytes'] and sha(path) == spec['sha256'], spec['path']
    assert path.stat().st_size < 100 * 1024 * 1024
for spec in json.loads((ROOT / 'publication_v3/large_files.json').read_text()):
    with gzip.open(ROOT / spec['archive'], 'rb') as source:
        assert stream_sha(source) == spec['sha256']

from protocol_v3.common import validate
validate()
summary = json.loads((OUT / 'analysis_scaled/summary.json').read_text())
assert sum(summary['counts'].values()) == 189480
with (OUT / 'analysis_scaled/exports/all_formal_records.csv').open() as source:
    keys = [row['case_key'] for row in csv.DictReader(source)]
assert len(keys) == len(set(keys)) == 189480

# Exercise restoration of a real member into an isolated temporary directory,
# including the refusal to overwrite differing bytes.
module_spec = importlib.util.spec_from_file_location('v3_restore', ROOT / 'publication_v3/restore.py')
restore = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(restore)
spec = next(iter(members.values()))
original = ROOT / spec['path']
with tempfile.TemporaryDirectory(dir=ROOT / '.runtime/publish') as temporary:
    target = Path(temporary) / 'request.jsonl.gz'
    with original.open('rb') as source:
        restore.restore_file(target, source, spec['sha256'])
    assert target.read_bytes() == original.read_bytes()
    target.write_bytes(b'different existing result')
    try:
        with original.open('rb') as source:
            restore.restore_file(target, source, spec['sha256'])
    except ValueError:
        pass
    else:
        raise AssertionError('Restoration overwrote an existing different file')

report = dict(validated=True, formal_records=189480, request_members=len(seen),
              request_archives=len(done['archives']), ordinary_files=len(file_specs),
              frozen_hashes_valid=True, all_archive_members_byte_exact=True,
              restoration_sample_passed=True, existing_file_protection_passed=True)
(ROOT / '.runtime/publish/VERIFIED.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
