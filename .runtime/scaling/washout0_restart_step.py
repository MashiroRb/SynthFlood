import json,os,sys
from pathlib import Path
import torch
from washout0_restart_common import verify_devices
root=Path.cwd();sys.path.insert(0,str(root));plan=json.loads(Path(sys.argv[1]).read_text())
actual=[str(torch.cuda.get_device_properties(i).uuid) for i in range(torch.cuda.device_count())]
verify_devices(actual,plan['gpu_uuids'])
from protocol_v3.common import validate
validate()
print('ORIGINAL_GPU_IDENTITIES_AND_FROZEN_PROTOCOL_VERIFIED',flush=True)
env=os.environ.copy()
for k,v in plan['server_env'].items():
    if not k.startswith('SLURM_') and k!='CUDA_VISIBLE_DEVICES':env[k]=v
os.execvpe(plan['server_argv'][0],plan['server_argv'],env)
