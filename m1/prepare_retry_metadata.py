"""Record an operational launcher repair without regenerating frozen inputs."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'data/m1_v2/manifest.json'
backup=path.with_name('manifest.before-git-archive-fix.json')
if not backup.exists():
    shutil.copy2(path,backup)
manifest=json.loads(path.read_text())
new=hashlib.sha256((ROOT/'m1/slurm/run.sbatch').read_bytes()).hexdigest()
old=manifest['run_script_sha256']
if new!=old:
    manifest.setdefault('operational_retries',[]).append({
        'failed_job':142515,'reason':'GPU node lacks git; failure before model launch',
        'change':'Copy precomputed git diff; use standard-library HTTP readiness probe on minimal GPU nodes',
        'old_run_script_sha256':old,'new_run_script_sha256':new,
        'inference_parameters_changed':False,'input_context_changed':False})
    manifest['run_script_sha256']=new
manifest['operational_source_sha256']={'m1/server_ready.py':hashlib.sha256((ROOT/'m1/server_ready.py').read_bytes()).hexdigest()}
temporary=path.with_suffix('.tmp')
temporary.write_text(json.dumps(manifest,indent=2)+'\n')
temporary.replace(path)
print('RUNTIME_METADATA_UPDATED; original input context retained',manifest['context_sha256'])
