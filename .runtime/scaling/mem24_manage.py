import datetime,fcntl,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
from mem24_common import target,verify_prefix
from washout0_restart_common import proc

ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from protocol_v3.common import validate
action=sys.argv[1];shard=int(sys.argv[2]);cfg=target(shard)
D=ROOT/f'results_protocol_v3_20261024_relaxed_v1/washout{shard}'
B=ROOT/f'.runtime/scaling/mem24_washout{shard}';B.mkdir(exist_ok=True)
assert os.environ['SLURMD_NODENAME']==cfg['node']
def command(args):return subprocess.run(args,text=True,capture_output=True,check=True).stdout.strip()
def running(job):return bool(command(['squeue','-h','-j',str(job),'-o','%i']))
def record(phase,**kw):
    state=dict(phase=phase,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw)
    (B/'state.json').write_text(json.dumps(state,indent=2));print(json.dumps(state),flush=True)
def processes():
    rows=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if p.stat().st_uid==os.getuid():rows.append(proc(int(p.name)))
        except (OSError,ValueError):pass
    return rows
validate()
if action=='prepare':
    ps=processes()
    servers=[p for p in ps if p['env'].get('SLURM_JOB_ID')==str(cfg['old_job']) and 'vllm.entrypoints.openai.api_server' in p['argv']]
    ids={p['pid'] for p in servers};servers=[p for p in servers if p['ppid'] not in ids]
    assert len(servers)==1
    server=servers[0];assert str(cfg['port']) in server['argv']
    safe={'SYNTHFLOOD_ROOT','SYNTHFLOOD_DATA_DIR','SYNTHFLOOD_STRICT_REWARD','SYNTHFLOOD_API_BASE',
        'WEBSHOP_REPO','HF_HUB_OFFLINE','HF_HOME','HF_HUB_CACHE','TRANSFORMERS_OFFLINE','TRANSFORMERS_CACHE',
        'VLLM_CACHE_ROOT','TRITON_CACHE_DIR','TORCHINDUCTOR_CACHE_DIR','TORCHINDUCTOR_FX_GRAPH_CACHE',
        'TORCHINDUCTOR_FORCE_DISABLE_CACHES','OMP_NUM_THREADS','PATH','LD_LIBRARY_PATH','XDG_CACHE_HOME'}
    hw=(D/'hardware.json').read_bytes();hardware=json.loads(hw)
    assert hardware['context']==131072 and hardware['tensor_parallel_size']==2
    plan=dict(shard=shard,**cfg,server_argv=server['argv'],server_env={k:v for k,v in server['env'].items() if k in safe},
        gpu_uuids=[d['uuid'] for d in hardware['devices']],hardware_sha256=hashlib.sha256(hw).hexdigest())
    assert not (B/'plan.json').exists(),'Refuse to overwrite a prepared migration'
    (B/'plan.json').write_text(json.dumps(plan,indent=2));record('PREPARED_NO_RUNNING_TASK_CHANGED')
elif action=='cutover':
    new=int(sys.argv[3]);plan=json.loads((B/'plan.json').read_text())
    held=command(['scontrol','show','job',str(new),'-o'])
    assert 'JobState=PENDING' in held and 'JobHeldUser' in held
    assert 'MinMemoryNode=24G' in held and 'mem=24G' in held
    assert f"ReqNodeList={cfg['node']}" in held
    assert 'gres/gpu=2' in held
    assert 'JobHeldUser' in command(['scontrol','show','job','150299','-o'])
    assert running(cfg['old_job']) and running(cfg['client_job'])
    ps=processes();clients=[p for p in ps if p['env'].get('SLURM_JOB_ID')==str(cfg['client_job']) and '.runtime/scaling/resume_washout.py' in p['argv']]
    assert len(clients)==1 and clients[0]['state']!='T'
    client=clients[0];assert proc(client['pid'])['start']==client['start']
    retired=False;os.kill(client['pid'],signal.SIGSTOP)
    try:
        time.sleep(.3)
        assert proc(client['pid'])['state']=='T'
        assert hashlib.sha256((D/'hardware.json').read_bytes()).hexdigest()==plan['hardware_sha256']
        baseline={'new_job':new,'counts':{},'hashes':{},'old':cfg}
        for name in ('shopping.jsonl','exam.jsonl','resume_events.jsonl','server.log','hardware.json','LAUNCH.json','CLIENT_HANDOFF.json'):
            source=D/name
            if not source.exists():continue
            shutil.copy2(source,B/name)
            if name.endswith('.jsonl'):
                data=(B/name).read_bytes();rows=[json.loads(line) for line in data.splitlines()]
                baseline['counts'][name]=len(rows);baseline['hashes'][name]=hashlib.sha256(data).hexdigest()
        for sd in D.glob('seed*'):
            if sd.is_dir():shutil.copytree(sd,B/sd.name,dirs_exist_ok=True)
        (B/'baseline.json').write_text(json.dumps(baseline,indent=2));record('PAUSED_CLIENT_AND_SNAPSHOT_SAVED',new_job=new,counts=baseline['counts'])
        if cfg['client_job']!=cfg['old_job']:
            command(['scancel',str(cfg['client_job'])])
        command(['scancel',cfg['old_target']]);retired=True
        for _ in range(90):
            if not running(cfg['old_job']) and not running(cfg['client_job']):break
            time.sleep(1)
        assert not running(cfg['old_job']) and not running(cfg['client_job'])
        if cfg['host_job']:command(['scancel',str(cfg['host_job'])])
        with (D/'RESUME.lock').open('a') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for name in baseline['hashes']:verify_prefix((B/name).read_bytes(),(D/name).read_bytes())
        record('OLD_SERVICE_RETIRED_SNAPSHOT_VERIFIED',new_job=new)
        command(['scontrol','release',str(new)]);record('MEM24_JOB_RELEASED',new_job=new)
    except BaseException:
        if not retired:
            try:
                if proc(client['pid'])['start']==client['start']:os.kill(client['pid'],signal.SIGCONT)
            except OSError:pass
        raise
elif action=='verify':
    plan=json.loads((B/'plan.json').read_text());baseline=json.loads((B/'baseline.json').read_text())
    assert hashlib.sha256((D/'hardware.json').read_bytes()).hexdigest()==plan['hardware_sha256']
    counts={}
    for name in baseline['hashes']:
        verify_prefix((B/name).read_bytes(),(D/name).read_bytes());counts[name]=len((D/name).read_bytes().splitlines())
    for sd in B.glob('seed*'):
        for f in sd.glob('*.json'):
            old=json.loads(f.read_text());new=json.loads((D/sd.name/f.name).read_text())
            if f.name.startswith('memory_'):assert new['entries'][:len(old['entries'])]==old['entries']
            else:assert new==old
    ready=json.loads((B/'READY.json').read_text());assert ready['memory_limit']==24*1024**3
    record('MEM24_HISTORY_MEMORY_BACKEND_VERIFIED',new_job=ready['job'],baseline=baseline['counts'],current=counts)
else:raise ValueError(action)
