"""Restore byte-exact large analysis files and original compressed request logs."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results_protocol_v3_20261024_relaxed_v1'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def restore_file(target, source, expected):
    if target.exists():
        if digest(target) != expected:
            raise ValueError('Refusing to overwrite different file: ' + str(target))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + '.restore-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        if digest(Path(temporary)) != expected:
            raise ValueError('Restored bytes failed SHA256: ' + str(target))
        # link() atomically refuses a concurrent writer, rather than replacing it.
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--requests', action='store_true')
    args = parser.parse_args()
    specs = json.loads((ROOT / 'publication_v3/large_files.json').read_text())
    for spec in specs:
        with gzip.open(ROOT / spec['archive'], 'rb') as source:
            restore_file(ROOT / spec['path'], source, spec['sha256'])
    for lane in range(8):
        target = OUT / 'analysis_scaled' / f'worker{lane}'
        relative = f'../worker{lane}'
        if target.is_symlink():
            if target.resolve() != (OUT / f'worker{lane}').resolve():
                raise ValueError('Conflicting analysis symlink: ' + str(target))
        elif target.exists():
            raise ValueError('Refusing to replace analysis path: ' + str(target))
        else:
            target.symlink_to(relative, target_is_directory=True)
    if args.requests:
        directory = OUT / 'request_archives'
        if not (directory / 'COMPLETE.json').exists():
            raise ValueError('Complete original request bundles are local-only and are not included in this Git archive.')
        done = json.loads((directory / 'COMPLETE.json').read_text())
        if digest(directory / 'members.jsonl') != done['member_manifest_sha256']:
            raise ValueError('Request member manifest checksum mismatch')
        members = {}
        with (directory / 'members.jsonl').open() as source:
            for line in source:
                spec = json.loads(line)
                if spec['path'] in members:
                    raise ValueError('Duplicate request member')
                members[spec['path']] = spec
        seen = set()
        for spec in done['archives']:
            archive = directory / spec['path']
            if digest(archive) != spec['sha256']:
                raise ValueError('Request archive checksum mismatch: ' + str(archive))
            process = subprocess.Popen(['zstd', '-q', '-d', '-c', str(archive)], stdout=subprocess.PIPE)
            try:
                with tarfile.open(fileobj=process.stdout, mode='r|') as source:
                    for member in source:
                        target = (ROOT / member.name).resolve()
                        expected = members.get(member.name)
                        if (not member.isfile() or not target.is_relative_to(OUT.resolve())
                                or expected is None or expected['archive'] != archive.name
                                or member.name in seen or member.size != expected['size']):
                            raise ValueError('Unexpected or unsafe archive member: ' + member.name)
                        with source.extractfile(member) as payload:
                            restore_file(target, payload, expected['sha256'])
                        seen.add(member.name)
                # Drain tar padding before waiting for the decompressor.
                with open(os.devnull, 'wb') as sink:
                    shutil.copyfileobj(process.stdout, sink)
            except BaseException:
                process.terminate()
                raise
            finally:
                process.stdout.close()
                status = process.wait()
            if status != 0:
                raise ValueError('zstd decompression failed')
            print('Verified/restored', archive.name, flush=True)
        if len(seen) != done['files'] or seen != members.keys():
            raise ValueError('Incomplete request restoration')
    print('Archive restoration verified; no model or statistical analysis was run.')


if __name__ == '__main__':
    main()
