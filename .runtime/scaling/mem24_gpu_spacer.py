"""Temporary GPU allocation only to preserve the original two physical GPUs.
No model is loaded and no inference is requested; exits once replacement ready.
"""
import json,os,time
from pathlib import Path
import torch
B=Path('.runtime/scaling/mem24_washout0')
plan=json.loads((B/'plan.json').read_text())
actual=[str(torch.cuda.get_device_properties(i).uuid) for i in range(torch.cuda.device_count())]
assert len(actual)==1 and actual[0] not in plan['gpu_uuids'],actual
record=dict(job=os.environ['SLURM_JOB_ID'],temporary_gpu=actual,expected_model_gpus=plan['gpu_uuids'])
(B/'SPACER.json').write_text(json.dumps(record));print(json.dumps(record),flush=True)
for _ in range(120):
    if (B/'READY.json').exists():break
    time.sleep(2)
print('TEMPORARY_GPU_RELEASED',flush=True)
