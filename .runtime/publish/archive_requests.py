"""Archive original gzip request files byte-for-byte, without touching originals."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path.cwd()
SOURCE = ROOT / 'results_protocol_v3_20261024_relaxed_v1'
DEST = SOURCE / 'request_archives'
DEST.mkdir(exist_ok=True)
LIMIT = 32 * 1024 * 1024

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

manifest_path = DEST / 'members.jsonl'
bundles = []
with manifest_path.open('w') as manifest:
    for directory in sorted(SOURCE.iterdir()):
        source = directory / 'requests'
        if not source.is_dir() or directory.name == 'analysis_scaled':
            continue
        files = sorted(p for p in source.iterdir() if p.is_file() and not p.is_symlink())
        batches = []
        batch = []
        size = 0
        for path in files:
            if batch and size + path.stat().st_size > LIMIT:
                batches.append(batch)
                batch = []
                size = 0
            batch.append(path)
            size += path.stat().st_size
        if batch:
            batches.append(batch)
        for index, batch in enumerate(batches):
            target = DEST / f'{directory.name}-requests-{index:03}.tar.zst'
            assert not target.exists(), f'Refusing overwrite: {target}'
            with target.open('wb') as output:
                compressor = subprocess.Popen(['zstd', '-q', '-6', '--long=27', '-T1', '-c'], stdin=subprocess.PIPE, stdout=output)
                try:
                    with tarfile.open(fileobj=compressor.stdin, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                        for path in batch:
                            rel = str(path.relative_to(ROOT))
                            digest = sha(path)
                            archive.add(path, arcname=rel, recursive=False)
                            manifest.write(json.dumps(dict(path=rel, size=path.stat().st_size, sha256=digest, archive=target.name)) + '\n')
                finally:
                    compressor.stdin.close()
                assert compressor.wait() == 0
            assert target.stat().st_size < 90 * 1024 * 1024
            bundles.append(dict(path=target.name, bytes=target.stat().st_size, sha256=sha(target), members=len(batch)))
            print(json.dumps(bundles[-1]), flush=True)
report = dict(format='Original files in streaming POSIX tar compressed with zstd; no recompression of gzip members',
              source=str(SOURCE.relative_to(ROOT)), files=sum(b['members'] for b in bundles),
              archives=bundles, member_manifest_sha256=sha(manifest_path))
(DEST / 'COMPLETE.json').write_text(json.dumps(report, indent=2) + '\n')
print('ARCHIVE_COMPLETE', report['files'], sum(b['bytes'] for b in bundles), flush=True)
