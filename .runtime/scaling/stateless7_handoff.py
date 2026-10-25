"""Isolate only the legacy waiting batch shell; leave worker1 and its server alone."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from protocol_v3.common import OUT,read,write,validate,digest,file_sha

OLD_JOB=150046
OLD_ELEMENT='150037_1'
CONTROL=ROOT/'.runtime/scaling/stateless7_control'


def inspect_process(pid):
    path=Path('/proc')/str(pid)
    try:
        if path.stat().st_uid!=os.getuid():return None
        fields=(path/'stat').read_text().rsplit(')',1)[1].split()
        argv=[p.decode(errors='replace') for p in (path/'cmdline').read_bytes().split(b'\0') if p]
        env=dict(p.split(b'=',1) for p in (path/'environ').read_bytes().split(b'\0') if b'=' in p)
        return dict(pid=pid,ppid=int(fields[1]),state=fields[0],start_ticks=fields[19],argv=argv,
                    job=env.get(b'SLURM_JOB_ID',b'').decode())
    except (FileNotFoundError,PermissionError,ProcessLookupError):return None


def same_process(saved):
    current=inspect_process(saved['pid'])
    return current if current and current['start_ticks']==saved['start_ticks'] and current['argv']==saved['argv'] else None


def identify_chain(processes):
    workers=[p for p in processes if p['argv'][-3:]==['-m','protocol_v3.worker','1']]
    if len(workers)!=1:raise RuntimeError('Expected exactly one running worker1')
    worker=workers[0]
    launch=next((p for p in processes if p['pid']==worker['ppid']),None)
    if launch is None or launch['argv']!=['bash','protocol_v3/slurm/launch.sh','worker','1']:
        raise RuntimeError('Unexpected worker1 launcher')
    batch=next((p for p in processes if p['pid']==launch['ppid']),None)
    if batch is None or batch['argv']!=['/bin/bash',f'/var/spool/slurm/job{OLD_JOB}/slurm_script']:
        raise RuntimeError('Unexpected outer batch shell')
    if any(p.get('job')!=str(OLD_JOB) for p in (worker,launch,batch)):
        raise RuntimeError('Refusing to touch processes from a different job')
    servers=[p for p in processes if 'vllm.entrypoints.openai.api_server' in p['argv']]
    if not servers or any(p['state'] in ('T','t','Z') for p in [worker,launch,*servers]):
        raise RuntimeError('Current inference processes must remain active')
    return dict(batch=batch,launch=launch,worker=worker,servers=servers)


def pause_single_waiting_parent(saved):
    current=same_process(saved)
    if current is None:raise RuntimeError('Outer process identity changed before handoff')
    os.kill(saved['pid'],signal.SIGSTOP)
    for _ in range(100):
        current=same_process(saved)
        if current and current['state'] in ('T','t'):return
        time.sleep(.01)
    raise RuntimeError('Outer batch shell did not stop')


def verify_children_active(chain):
    for child in [chain['worker'],chain['launch'],*chain['servers']]:
        current=same_process(child)
        if current is None or current['state'] in ('T','t','Z'):
            raise RuntimeError('Handoff unexpectedly affected current inference child')


def retire_stopped_parent(saved):
    current=same_process(saved)
    if current is None or current['state'] not in ('T','t'):
        raise RuntimeError('Only the isolated, retired batch parent may be terminated')
    # Never let allocation cleanup SIGCONT this shell into its obsolete worker7 branch.
    os.kill(saved['pid'],signal.SIGKILL)


def release_target(value):
    if value!=OLD_ELEMENT:raise RuntimeError('Only exact assigned array element may be released')
    return value


def completion_valid(value):
    return value.get('validated') is True and value.get('lane')==1 and value.get('nondefense_rows')==3410 and value.get('defense_rows')==7500


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def verify_manifest(value):
    if digest(validate())!=value['frozen_manifest_sha256']:
        raise RuntimeError('Frozen experiment manifest changed')
    for name,sha in value['source_sha256'].items():
        if file_sha(ROOT/name)!=sha:raise RuntimeError('Handoff source changed: '+name)


def verify_new():
    validate()
    manifest=read(CONTROL/'manifest.json')
    verify_manifest(manifest)
    if str(manifest['new_gpu_job'])!=os.environ['SLURM_JOB_ID']:
        raise RuntimeError('This job does not own worker7')
    state=read(CONTROL/'state.json')
    if state['phase'] not in ('PARENT_ISOLATED','CURRENT_WORKER_FINISHED','OLD_ALLOCATION_RELEASED'):
        raise RuntimeError('Legacy future-launch path has not been isolated')
    if state['phase']!='OLD_ALLOCATION_RELEASED':
        age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(state['updated_utc'])).total_seconds()
        if age>90:raise RuntimeError('Handoff controller heartbeat is stale')
    if (OUT/'worker7/LAUNCH.json').exists():raise RuntimeError('worker7 has already started')
    write(CONTROL/'new_owner_verified.json',dict(job=os.environ['SLURM_JOB_ID'],verified_utc=now(),old_element=OLD_ELEMENT))


def supervise():
    validate()
    manifest=read(CONTROL/'manifest.json')
    verify_manifest(manifest)
    if manifest['controller_job']!=int(os.environ['SLURM_JOB_ID']) or manifest['old_job']!=OLD_JOB or manifest['old_element']!=OLD_ELEMENT:
        raise RuntimeError('Handoff manifest does not authorize this job')
    if not manifest['analysis_dependency_updated']:
        raise RuntimeError('Final analysis must wait for independent worker7 and this controller')
    if (OUT/'worker7').exists():raise RuntimeError('worker7 must be completely unstarted before isolation')
    if (OUT/'worker1/COMPLETE.json').exists():raise RuntimeError('Current worker already finished; re-audit routing before handoff')
    with (CONTROL/'controller.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        processes=[p for path in Path('/proc').glob('[0-9]*') if (p:=inspect_process(int(path.name))) and p['job']==str(OLD_JOB)]
        chain=identify_chain(processes)
        write(CONTROL/'before.json',dict(chain=chain,verified_utc=now(),frozen_sources_unchanged=True))
        try:
            pause_single_waiting_parent(chain['batch'])
            verify_children_active(chain)
        except BaseException:
            # New GPU job is still held until the assistant sees isolation proof.
            if same_process(chain['batch']):os.kill(chain['batch']['pid'],signal.SIGCONT)
            raise
        write(CONTROL/'isolation_proof.json',dict(batch=inspect_process(chain['batch']['pid']),
            worker=inspect_process(chain['worker']['pid']),launch=inspect_process(chain['launch']['pid']),
            servers=[inspect_process(p['pid']) for p in chain['servers']],verified_utc=now()))
        state=dict(phase='PARENT_ISOLATED',old_job=OLD_JOB,old_element=OLD_ELEMENT,
            controller_job=int(os.environ['SLURM_JOB_ID']),new_gpu_job=manifest['new_gpu_job'],updated_utc=now())
        write(CONTROL/'state.json',state)
        print('OUTER_BATCH_ONLY_ISOLATED; WORKER1_AND_SERVER_CONTINUE',flush=True)
        deadline=time.monotonic()+3.5*3600
        while time.monotonic()<deadline:
            batch=same_process(chain['batch'])
            if batch is None or batch['state'] not in ('T','t'):
                raise RuntimeError('Legacy batch shell is no longer isolated')
            complete=OUT/'worker1/COMPLETE.json'
            worker=same_process(chain['worker'])
            launch=same_process(chain['launch'])
            if complete.exists():
                value=read(complete)
                if not completion_valid(value):raise RuntimeError('Refusing to release incomplete worker1')
                if worker is None and launch is None:
                    validate()
                    state.update(phase='CURRENT_WORKER_FINISHED',updated_utc=now(),completion=value)
                    write(CONTROL/'state.json',state)
                    print('WORKER1_COMPLETE_AND_LAUNCHER_EXITED; RELEASE_ASSIGNED_ELEMENT',flush=True)
                    retire_stopped_parent(chain['batch'])
                    time.sleep(.5)
                    queued=subprocess.run(['squeue','-h','-j',OLD_ELEMENT,'-o','%i'],text=True,capture_output=True)
                    if queued.stdout.strip():
                        result=subprocess.run(['scancel',release_target(manifest['old_element'])],text=True,capture_output=True)
                        if result.returncode:
                            remaining=subprocess.run(['squeue','-h','-j',OLD_ELEMENT,'-o','%i'],text=True,capture_output=True)
                            if remaining.stdout.strip():raise RuntimeError('Assigned allocation release failed: '+result.stderr)
                    for _ in range(30):
                        queued=subprocess.run(['squeue','-h','-j',OLD_ELEMENT,'-o','%i'],text=True,capture_output=True)
                        if not queued.stdout.strip():break
                        time.sleep(1)
                    else:raise RuntimeError('Released old allocation still appears in queue')
                    state.update(phase='OLD_ALLOCATION_RELEASED',updated_utc=now(),expected_slurm_state='CANCELLED_OR_FAILED_RETIRED_BATCH_AFTER_WORKER1_COMPLETE')
                    write(CONTROL/'state.json',state)
                    write(CONTROL/'COMPLETE.json',dict(validated=True,worker1_complete=True,new_owner=manifest['new_gpu_job'],
                        old_element=OLD_ELEMENT,old_batch_did_not_launch_worker7=True,finished_utc=now()))
                    print('CONTROL_COMPLETE; ORIGINAL_WORKER1_RESULTS_PRESERVED',flush=True)
                    return
            elif worker is None:
                raise RuntimeError('worker1 exited without a validated COMPLETE; preserve results for investigation')
            state['updated_utc']=now();write(CONTROL/'state.json',state)
            time.sleep(10)
        raise RuntimeError('Controller time limit reached; keep legacy parent isolated and preserve work')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['supervise','verify-new'])
    args=parser.parse_args()
    if args.mode=='verify-new':verify_new()
    else:
        try:supervise()
        except BaseException as error:
            CONTROL.mkdir(exist_ok=True)
            write(CONTROL/'ERROR.json',dict(error=repr(error),utc=now(),preserve_current_children_and_results=True))
            raise
