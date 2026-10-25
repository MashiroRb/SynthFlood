import datetime,json,os,signal,subprocess,sys,time,urllib.request,hashlib
from pathlib import Path
from mem24_common import ordered_devices

ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from protocol_v3.common import validate
shard=int(sys.argv[1]);B=ROOT/f'.runtime/scaling/mem24_washout{shard}'
plan=json.loads((B/'plan.json').read_text());D=ROOT/f'results_protocol_v3_20261024_relaxed_v1/washout{shard}'
assert os.environ['SLURMD_NODENAME']==plan['node'];validate()
assert hashlib.sha256((D/'hardware.json').read_bytes()).hexdigest()==plan['hardware_sha256']
code='import torch,json; print(json.dumps([str(torch.cuda.get_device_properties(i).uuid) for i in range(torch.cuda.device_count())]))'
actual=json.loads(subprocess.check_output([sys.executable,'-c',code],text=True))
print('MEM24_ALLOCATED_GPUS',actual,'EXPECTED',plan['gpu_uuids'],flush=True)
env=os.environ.copy();env.update(plan['server_env'])
env['CUDA_VISIBLE_DEVICES']=ordered_devices(actual,plan['gpu_uuids'],os.environ['CUDA_VISIBLE_DEVICES'])
for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):env.pop(name,None)
env['SYNTHFLOOD_API_BASE']=f"http://127.0.0.1:{plan['port']}/v1"
cg=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::')[-1].lstrip('/')
while not cg.name.startswith('job_'):cg=cg.parent
limit=int((cg/'memory.max').read_text());assert limit==24*1024**3
print('MEM24_SAME_PHYSICAL_GPUS_VERIFIED',plan['gpu_uuids'],'limit',limit,flush=True)
server=None
try:
    with (D/'server.log').open('w') as log:
        server=subprocess.Popen(plan['server_argv'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(180):
        if server.poll() is not None:raise RuntimeError('Model service exited during startup')
        try:
            with opener.open(env['SYNTHFLOOD_API_BASE']+'/models',timeout=2) as response:payload=json.load(response)
            if payload.get('data'):break
        except Exception:time.sleep(2)
    else:raise RuntimeError('Local model readiness timeout')
    (B/'READY.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job=os.environ['SLURM_JOB_ID'],memory_limit=limit,gpu_uuids=plan['gpu_uuids'],hardware_sha256=plan['hardware_sha256'])))
    print('MEM24_SERVER_READY_RESUMING_EXISTING_RESULTS',flush=True)
    subprocess.run([sys.executable,'-u','.runtime/scaling/resume_washout.py','--shard',str(shard),'--seeds',*[str(s) for s in plan['seeds']]],env=env,check=True)
    done=json.loads((D/'COMPLETE.json').read_text());assert done['validated'] and done['seeds']==plan['seeds']
    validate();(B/'COMPLETE.json').write_text(json.dumps(done));print('MEM24_ALL_ASSIGNED_SEEDS_COMPLETE',flush=True)
finally:
    if server is not None and server.poll() is None:
        os.killpg(server.pid,signal.SIGTERM)
        try:server.wait(timeout=15)
        except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL)
