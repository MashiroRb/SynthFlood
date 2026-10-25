import datetime,fcntl,hashlib,json,os,signal,shutil,subprocess,sys,time,urllib.request
from pathlib import Path
from washout0_restart_common import proc,descendants,cancel_target
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from protocol_v3.common import validate
D=ROOT/'results_protocol_v3_20261024_relaxed_v1/washout0'
B=ROOT/'.runtime/scaling/washout0_inplace_restart';B.mkdir(exist_ok=True)
CLIENT=int(os.environ['V3_NEW_CLIENT'])
def command(args):
    result=subprocess.run(args,text=True,capture_output=True,check=True)
    return result.stdout.strip()
def record(phase,**extra):
    value=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),phase=phase,
        controller=os.environ['SLURM_JOB_ID'],client=CLIENT,original_gpu_job=150049,**extra)
    (B/'state.json').write_text(json.dumps(value,indent=2));print(json.dumps(value),flush=True)
def running(job):return bool(command(['squeue','-h','-j',str(job),'-o','%i']))

try:
    assert os.environ['SLURMD_NODENAME']=='aias-compute-01'
    validate();assert running(150049) and running(150294)
    held=command(['scontrol','show','job',str(CLIENT),'-o'])
    assert 'JobState=PENDING' in held and 'JobHeldUser' in held
    ps=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if p.stat().st_uid==os.getuid():ps.append(proc(int(p.name)))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    byid={p['pid']:p for p in ps}
    servers=[p for p in ps if p['env'].get('SLURM_JOB_ID')=='150049'
        and 'vllm.entrypoints.openai.api_server' in p['argv']
        and 'protocol_v3/slurm/launch.sh' in byid.get(p['ppid'],{}).get('argv',[])]
    oldclients=[p for p in ps if p['env'].get('SLURM_JOB_ID')=='150294'
        and '.runtime/scaling/resume_washout.py' in p['argv']]
    assert len(servers)==len(oldclients)==1,(servers,oldclients)
    server=servers[0];assert '18049' in server['argv']
    tree=descendants(server['pid'],ps)
    assert server['ppid'] not in tree
    assert all(byid[p]['env'].get('SLURM_JOB_ID')=='150049' for p in tree)
    hw=json.loads((D/'hardware.json').read_text())
    assert hw['tensor_parallel_size']==2 and hw['context']==131072
    # Persist only execution-related variables, never the full inherited environment.
    safe_vars={'SYNTHFLOOD_ROOT','SYNTHFLOOD_DATA_DIR','SYNTHFLOOD_STRICT_REWARD','SYNTHFLOOD_API_BASE',
        'WEBSHOP_REPO','HF_HUB_OFFLINE','HF_HOME','HF_HUB_CACHE','TRANSFORMERS_OFFLINE','TRANSFORMERS_CACHE',
        'VLLM_CACHE_ROOT','TRITON_CACHE_DIR','TORCHINDUCTOR_CACHE_DIR','TORCHINDUCTOR_FX_GRAPH_CACHE',
        'TORCHINDUCTOR_FORCE_DISABLE_CACHES','OMP_NUM_THREADS','PATH','LD_LIBRARY_PATH','XDG_CACHE_HOME'}
    env={k:v for k,v in server['env'].items() if k in safe_vars}
    plan=dict(server_argv=server['argv'],server_env=env,gpu_uuids=[x['uuid'] for x in hw['devices']],
        server_tree=[{k:byid[p][k] for k in ('pid','ppid','state','start','argv')} for p in tree],
        old_client={k:oldclients[0][k] for k in ('pid','ppid','state','start','argv')},hardware_sha256=hashlib.sha256((D/'hardware.json').read_bytes()).hexdigest())
    (B/'plan.json').write_text(json.dumps(plan,indent=2));record('PREPARED')
    command(['scancel','150294'])
    for _ in range(60):
        if not running(150294):break
        time.sleep(1)
    assert not running(150294)
    with (D/'RESUME.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for name in ('shopping.jsonl','exam.jsonl','resume_events.jsonl','server.log','hardware.json','LAUNCH.json','CLIENT_HANDOFF.json'):
            if (D/name).exists():shutil.copy2(D/name,B/name)
        for sd in D.glob('seed*'):
            if sd.is_dir():shutil.copytree(sd,B/sd.name,dirs_exist_ok=True)
    record('CLIENT_RETIRED_AND_RESULTS_PRESERVED')
    # Kill only this exact model-server tree. The waiting launch shell and its
    # stopped original client keep the original allocation and GPU identities.
    for sig in (signal.SIGTERM,signal.SIGKILL):
        for pid in tree:
            try:
                now=proc(pid)
                if now['start']==byid[pid]['start'] and now['state']!='Z':os.kill(pid,sig)
            except (FileNotFoundError,ProcessLookupError):pass
        time.sleep(5 if sig==signal.SIGTERM else 1)
    for pid in tree:
        try:assert proc(pid)['state']=='Z'
        except FileNotFoundError:pass
    assert running(150049)
    record('OLD_SERVER_RETIRED_ALLOCATION_PRESERVED')
    env=os.environ.copy()
    for k in list(env):
        if k.startswith('SLURM_') or k=='CUDA_VISIBLE_DEVICES':env.pop(k)
    args=['srun','--jobid=150049','--overlap','--exact','--nodes=1','--ntasks=1','--cpus-per-task=2','--gres=gpu:2',
        str(ROOT/'.runtime/venv/bin/python'),'-u',str(ROOT/'.runtime/scaling/washout0_restart_step.py'),str(B/'plan.json')]
    with (D/'server.log').open('w') as log:
        service=subprocess.Popen(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    for _ in range(180):
        if service.poll() is not None:raise RuntimeError('New GPU step exited before readiness')
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open('http://127.0.0.1:18049/v1/models',timeout=2) as response:
                payload=json.load(response)
            if payload.get('data'):break
        except Exception:time.sleep(2)
    else:raise RuntimeError('Server readiness timeout')
    assert hashlib.sha256((D/'hardware.json').read_bytes()).hexdigest()==plan['hardware_sha256']
    record('SAME_GPU_SERVER_READY')
    command(['scontrol','release',str(CLIENT)]);record('CLIENT_RELEASED')
    while running(CLIENT):
        if service.poll() is not None:raise RuntimeError('GPU step exited while continuation still active')
        time.sleep(30)
    done=json.loads((D/'COMPLETE.json').read_text())
    assert done['validated'] and done['seeds']==[2030,2032]
    command(['scancel',cancel_target(150049)])
    record('ALL_SEEDS_COMPLETE_ALLOCATION_RELEASED')
    (B/'COMPLETE.json').write_text(json.dumps(dict(validated=True,client=CLIENT,gpu_job=150049)))
except BaseException as error:
    (B/'ERROR.json').write_text(json.dumps(dict(error=repr(error),utc=datetime.datetime.now(datetime.timezone.utc).isoformat())))
    raise
