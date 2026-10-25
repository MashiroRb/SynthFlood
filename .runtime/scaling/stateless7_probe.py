"""Read-only process evidence for isolating a waiting batch shell."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from protocol_v3.common import OUT,validate,write

validate()
processes=[]
for path in Path('/proc').glob('[0-9]*'):
    try:
        if path.stat().st_uid!=os.getuid():continue
        environment=dict(part.split(b'=',1) for part in (path/'environ').read_bytes().split(b'\0') if b'=' in part)
        if environment.get(b'SLURM_JOB_ID')!=b'150046':continue
        argv=[p.decode(errors='replace') for p in (path/'cmdline').read_bytes().split(b'\0') if p]
        status=dict(line.split(':',1) for line in (path/'status').read_text().splitlines() if ':' in line)
        processes.append(dict(pid=int(path.name),ppid=int(status['PPid']),state=status['State'].strip(),argv=argv[:10]))
    except (FileNotFoundError,PermissionError,ProcessLookupError):continue
record=dict(node=os.environ.get('SLURMD_NODENAME'),probe_job=os.environ['SLURM_JOB_ID'],
    old_job=150046,old_array_element='150037_1',worker7_exists=(OUT/'worker7').exists(),
    worker1_complete=(OUT/'worker1/COMPLETE.json').exists(),processes=processes,frozen_hashes_valid=True)
write(ROOT/'.runtime/scaling/stateless7_probe.json',record)
print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)
