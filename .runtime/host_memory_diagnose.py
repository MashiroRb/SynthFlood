import datetime,json,os,socket,sys
from pathlib import Path

targets=set(x for x in sys.argv[1:] if not x.startswith('--'))
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node':socket.gethostname(),'targets':sorted(targets),'processes':[],'cgroups':{}}
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit(): continue
    try:
        if proc.stat().st_uid!=os.getuid(): continue
        env=dict(x.split(b'=',1) for x in (proc/'environ').read_bytes().split(b'\0') if b'=' in x)
        job=env.get(b'SLURM_JOB_ID',b'').decode()
        if job not in targets: continue
        status=dict(x.split(':',1) for x in (proc/'status').read_text().splitlines() if ':' in x)
        row={'pid':int(proc.name),'job':job,'cmd':(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')[:500]}
        row['status']={k:status.get(k,'').strip() for k in ['State','PPid','VmRSS','RssAnon','RssFile','RssShmem','VmSwap','Threads']}
        try: row['smaps_rollup']=(proc/'smaps_rollup').read_text()
        except OSError as e: row['smaps_error']=str(e)
        cg=(proc/'cgroup').read_text().strip().split('::')[-1]
        row['cgroup']=cg
        out['processes'].append(row)
        for parent in [Path(cg),*Path(cg).parents]:
            if parent.name.startswith('job_'):
                cgroot=Path('/sys/fs/cgroup')/str(parent).lstrip('/')
                out['cgroups'][str(parent)]={k:(cgroot/k).read_text() for k in ['memory.current','memory.max','memory.events','memory.stat','memory.peak'] if (cgroot/k).exists()}
                break
    except (OSError,ValueError,ProcessLookupError): continue
if '--brief' in sys.argv:
    dest=Path('.runtime/v3_manual_checks')/('host_memory_'+os.environ['SLURM_JOB_ID']+'.json')
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2))
    brief={'utc':out['utc'],'node':out['node'],'cgroups':{}}
    for name,vals in out['cgroups'].items():
        stats=dict(line.split() for line in vals['memory.stat'].splitlines())
        brief['cgroups'][name]={'current_GiB':round(int(vals['memory.current'])/1024**3,3),'limit_GiB':round(int(vals['memory.max'])/1024**3,3),
            'anon_GiB':round(int(stats['anon'])/1024**3,3),'file_GiB':round(int(stats['file'])/1024**3,3),'events':vals['memory.events'].splitlines()}
    print(json.dumps(brief,ensure_ascii=False,indent=2),flush=True)
else:print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
