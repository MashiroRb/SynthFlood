"""Validate seed ownership and feed all retained results to the frozen analysis."""
import collections
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from protocol_v3.common import OUT,validate,read,write,digest,append
from resume_core import read_rows

manifest=validate()
ownership=read(ROOT/'.runtime/scaling/scaling_manifest.json')['ownership']
merged=OUT/'analysis_scaled'
merged.mkdir(exist_ok=True)
for lane in range(8):
    source=OUT/f'worker{lane}'
    assert (source/'COMPLETE.json').exists()
    target=merged/source.name
    if not target.exists():target.symlink_to(source,target_is_directory=True)
all_keys=set();counts=collections.Counter();provenance=[]
for parity in range(2):
    target=merged/f'washout{parity}';target.mkdir(exist_ok=True)
    sources=[name for name,seeds in ownership.items() if seeds[0]%2==parity]
    for phase in ('exam','shopping'):
        output=target/(phase+'.jsonl')
        if output.exists():raise RuntimeError('Refusing to overwrite merged formal rows')
        for name in sources:
            directory=OUT/name
            done=read(directory/'COMPLETE.json')
            assert done['validated'] and done['seeds']==ownership[name]
            records=read_rows(directory/(phase+'.jsonl'))
            for seed in ownership[name]:
                selected=[r for r in records if r['seed']==seed]
                assert len(selected)==(12600 if phase=='exam' else 120),(name,seed,phase,len(selected))
            for row in records:
                assert row['seed'] in ownership[name]
                assert row['case_key'] not in all_keys
                all_keys.add(row['case_key']);counts[phase]+=1
                append(output,row)
            provenance.append(dict(source=str((directory/(phase+'.jsonl')).relative_to(ROOT)),
                rows=len(records),seeds=ownership[name]))
    write(target/'COMPLETE.json',dict(validated=True,seeds=[s for name in sources for s in ownership[name]]))
assert dict(counts)==dict(exam=100800,shopping=960),counts
write(merged/'scaling_provenance.json',dict(ownership=ownership,sources=provenance,
    preserved_completed_results=True,unique_memory_cases=len(all_keys),parent_manifest=digest(manifest)))
from protocol_v3 import analyze
analyze.OUT=merged
analyze.analyze()
write(OUT/'SCALED_COMPLETE.json',dict(validated=True,analysis=str(merged.relative_to(ROOT))))
