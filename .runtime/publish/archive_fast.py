"""Continue only publication packaging; original inference artifacts stay intact."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path.cwd()
SOURCE = ROOT / 'results_protocol_v3_20261024_relaxed_v1'
DEST = SOURCE / 'request_archives'
LIMIT = 32 * 1024 * 1024
PAT = (ROOT.parent / 'PAT.txt').read_bytes().strip()
PATTERNS = [re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}'), re.compile(rb'github_pat_[A-Za-z0-9_]{25,}'),
            re.compile(rb'hf_[A-Za-z0-9]{20,}'), re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
previous = {}
for line in (ROOT / '.runtime/publish/archive-151382.log').read_text().splitlines():
    if line.startswith('{'):
        record = json.loads(line)
        previous[record['path']] = record
old_members = {}
with (DEST / 'members.jsonl').open() as stream:
    for line in stream:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record['archive'] in previous:
            old_members.setdefault(record['archive'], []).append(record)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def scan(data, path):
    plain = gzip.decompress(data) if path.name.endswith('.gz') else data
    if (PAT and PAT in plain) or any(pattern.search(plain) for pattern in PATTERNS):
        raise ValueError('Potential credential (value suppressed): ' + str(path.relative_to(ROOT)))

tasks = []
for directory in sorted(SOURCE.iterdir()):
    source = directory / 'requests'
    if not source.is_dir() or directory.name == 'analysis_scaled':
        continue
    files = sorted(p for p in source.iterdir() if p.is_file() and not p.is_symlink())
    batches = []
    batch = []
    size = 0
    for path in files:
        length = path.stat().st_size
        if batch and size + length > LIMIT:
            batches.append(batch)
            batch = []
            size = 0
        batch.append((path, length))
        size += length
    if batch:
        batches.append(batch)
    for index, batch in enumerate(batches):
        tasks.append((f'{directory.name}-requests-{index:03}.tar.zst', batch))

def package(task):
    name, batch = task
    target = DEST / name
    members = []
    reused = name in previous
    if reused:
        assert sha(target) == previous[name]['sha256']
        assert len(old_members[name]) == len(batch)
        expected = {r['path']: r for r in old_members[name]}
    else:
        # Only an incomplete publication bundle can exist here, never an experiment file.
        target.unlink(missing_ok=True)
        output = target.open('wb')
        compressor = subprocess.Popen(['zstd', '-q', '-1', '-T1', '-c'], stdin=subprocess.PIPE, stdout=output)
        archive = tarfile.open(fileobj=compressor.stdin, mode='w|', format=tarfile.PAX_FORMAT)
    try:
        for path, length in batch:
            data = path.read_bytes()
            assert len(data) == length
            scan(data, path)
            record = dict(path=str(path.relative_to(ROOT)), size=length,
                          sha256=hashlib.sha256(data).hexdigest(), archive=name)
            members.append(record)
            if reused:
                assert expected[record['path']] == record
            else:
                info = tarfile.TarInfo(record['path'])
                info.size = length
                info.mode = 0o644
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
    finally:
        if not reused:
            archive.close()
            compressor.stdin.close()
            assert compressor.wait() == 0
            output.close()
    assert target.stat().st_size < 90 * 1024 * 1024
    result = dict(path=name, bytes=target.stat().st_size, sha256=sha(target), members=len(batch))
    print(json.dumps(dict(**result, reused_packaging=reused, credential_scan='passed')), flush=True)
    return result, members

with ThreadPoolExecutor(max_workers=4) as executor:
    packed = list(executor.map(package, tasks))
manifest = DEST / 'members.jsonl'
with manifest.open('w') as output:
    for _, members in packed:
        for member in members:
            output.write(json.dumps(member) + '\n')
bundles = [bundle for bundle, _ in packed]
report = dict(format='Original gzip bytes in POSIX tar, compressed with zstd',
              source=str(SOURCE.relative_to(ROOT)), files=sum(b['members'] for b in bundles),
              archives=bundles, member_manifest_sha256=sha(manifest), credential_scan='passed')
(DEST / 'COMPLETE.json').write_text(json.dumps(report, indent=2) + '\n')
print('ARCHIVE_COMPLETE', report['files'], sum(b['bytes'] for b in bundles), flush=True)
