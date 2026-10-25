import hashlib
import json
from pathlib import Path
import os

ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'protocol_v3/slurm/launch.sh'
text=source.read_text()
text=text.replace("if [ -e \"$OUTDIR/LAUNCH.json\" ]; then echo 'Refusing duplicate launcher'; exit 1; fi",'''
mkdir -p "$OUTDIR/attempts/$SLURM_JOB_ID"
exec 9>"$OUTDIR/LAUNCH.lock"
flock -n 9 || { echo 'Another launcher owns this output'; exit 1; }
for state in LAUNCH.json hardware.json FAILED.json; do
    if [ -e "$OUTDIR/$state" ]; then cp "$OUTDIR/$state" "$OUTDIR/attempts/$SLURM_JOB_ID/prior-$state"; fi
done
if [ -e "$OUTDIR/FAILED.json" ]; then mv "$OUTDIR/FAILED.json" "$OUTDIR/attempts/$SLURM_JOB_ID/recovered-failure.json"; fi
''')
old='.runtime/venv/bin/python -m "protocol_v3.$MODE" "$INDEX"'
new='.runtime/venv/bin/python -u .runtime/scaling/resume_washout.py --shard "$INDEX" --seeds $V3_EXTRA_SEEDS'
assert text.count(old)==1;text=text.replace(old,new)
text=text.replace('cp .runtime/protocol-v3-relaxed-v1-source.tar.gz "$OUTDIR/code-snapshot.tar.gz"',
    'cp .runtime/protocol-v3-relaxed-v1-source.tar.gz "$OUTDIR/code-snapshot.tar.gz"\n    cp "$OUTDIR/hardware.json" "$OUTDIR/attempts/$SLURM_JOB_ID/hardware.json"\n    cp .runtime/scaling/scaling_manifest.json "$OUTDIR/attempts/$SLURM_JOB_ID/scaling_manifest.json"')
(ROOT/'.runtime/scaling/launch_extra.sh').write_text(text)
ownership={'washout0':[2030,2032],'washout1':[2031,2033],
    'washout2':[2034,2036],'washout3':[2035,2037]}
manifest=dict(parent_manifest_sha256=hashlib.sha256((ROOT/'data/protocol_v3_20261024_relaxed_v1/manifest.json').read_bytes()).hexdigest(),
    ownership=ownership,additional_gpu=2,total_gpu_limit=12,a800_limit=3,
    unchanged_frozen_sources=True,experiment_rules_unchanged=True,
    continuation_method='Pause only the old client; preserve original Slurm allocation and vLLM server; resume completed cases and request prefixes',
    source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'.runtime/scaling').iterdir() if p.suffix in ('.py','.sbatch','.sh')})
(ROOT/'.runtime/scaling/scaling_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('SCALING_MANIFEST_FROZEN',ownership,flush=True)
