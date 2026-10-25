import json
from pathlib import Path

def cancel_target(job):
    if job != 150049:
        raise ValueError('Only the exact washout0 GPU allocation is authorized')
    return '150039_0'

def verify_devices(actual, expected):
    if actual != expected:
        raise ValueError('GPU identities/order changed; refuse server restart')

def verify_prefix(before, after):
    if not after.startswith(before):
        raise ValueError('Completed results changed')

def proc(pid):
    p=Path('/proc')/str(pid)
    fields=(p/'stat').read_text().split(') ',1)[1].split()
    return dict(pid=int(pid),ppid=int(fields[1]),state=fields[0],start=fields[19],
        argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x],
        env=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x))

def descendants(root, processes):
    found={root}
    while True:
        expanded=found|{p['pid'] for p in processes if p['ppid'] in found}
        if expanded==found:return found
        found=expanded
