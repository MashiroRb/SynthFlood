"""Check that Git retained the exact archived file bytes, without printing data."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path.cwd()
tree = {}
for entry in subprocess.check_output(['git', 'ls-tree', '-rz', 'HEAD']).split(b'\0'):
    if not entry:
        continue
    metadata, name = entry.split(b'\t', 1)
    mode, kind, oid = metadata.decode().split()
    tree[name.decode()] = oid
with (ROOT / 'publication_v3/files.jsonl').open() as source:
    specs = [json.loads(line) for line in source]
directory = ROOT / 'results_protocol_v3_20261024_relaxed_v1/request_archives'
done = json.loads((directory / 'COMPLETE.json').read_text())
specs += [dict(path=str((directory / s['path']).relative_to(ROOT)), sha256=s['sha256']) for s in done['archives']]
extras = ['publication_v3/files.jsonl'] + [str((directory / name).relative_to(ROOT)) for name in ('COMPLETE.json', 'VERIFIED.json', 'members.jsonl')]
specs += [dict(path=name) for name in extras]
for spec in specs:
    path = ROOT / spec['path']
    size = path.stat().st_size
    assert size < 100 * 1024 * 1024, spec['path']
    blob = hashlib.sha1(f'blob {size}\0'.encode())
    raw = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            blob.update(block)
            raw.update(block)
    assert tree[spec['path']] == blob.hexdigest(), spec['path']
    assert spec.get('sha256', raw.hexdigest()) == raw.hexdigest(), spec['path']
assert subprocess.run(['git', 'diff', '--quiet']).returncode == 0
assert subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0
report = dict(validated=True, checked_git_blobs=len(specs), git_preserves_original_bytes=True,
              tracked_worktree_clean=True, commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
(ROOT / '.runtime/publish/GIT_VERIFIED.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
