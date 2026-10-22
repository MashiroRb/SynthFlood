"""CPU barrier: validate all main results before any defense purchase."""
import subprocess
import time
import traceback

from .common import ROOT, DATA, OUT, LANES, read, write, file_sha, validate_sources
from .analyze import summarize


def check_jobs():
    path=ROOT/'.runtime/paired_n98_jobs.json'
    if not path.exists():
        return
    jobs=read(path)['worker_jobs']
    result=subprocess.run(['sacct','--allocations','-n','-P','-j',','.join(map(str,jobs)),
        '--format=JobIDRaw,State'],capture_output=True,text=True,timeout=30)
    if result.returncode:
        print('ACCOUNTING_RETRY',result.returncode,flush=True);return
    for line in result.stdout.splitlines():
        if '|' not in line:continue
        job,state,*_=line.split('|')
        if state.startswith(('FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED')):
            raise RuntimeError(f'Worker Slurm failure {job}: {state}')


def wait_for(marker):
    last=time.monotonic()
    while True:
        if (OUT/'FAILED.json').exists():
            raise RuntimeError('Worker failure: '+str(read(OUT/'FAILED.json')))
        ready=sum((OUT/f'worker{i}'/marker).exists() for i in range(LANES))
        if ready==LANES:return
        if time.monotonic()-last>=60:
            check_jobs();print('BARRIER_PROGRESS',marker,ready,'/',LANES,flush=True);last=time.monotonic()
        time.sleep(15)


def run():
    validate_sources();OUT.mkdir(parents=True,exist_ok=True)
    wait_for('MAIN_COMPLETE.json')
    summarize('main')
    write(OUT/'DEFENSE_READY.json',{'validated':True,'manifest_sha256':file_sha(DATA/'manifest.json'),
        'main_summary_sha256':file_sha(OUT/'main_summary.json')})
    print('DEFENSE_BARRIER_RELEASED',flush=True)
    wait_for('COMPLETE.json')
    summarize('defense')
    write(OUT/'COMPLETE.json',{'validated':True,'workers':LANES,
        'manifest_sha256':file_sha(DATA/'manifest.json')})
    print('PAIRED_N98_ALL_COMPLETE',flush=True)


if __name__=='__main__':
    try:
        run()
    except Exception as error:
        OUT.mkdir(parents=True,exist_ok=True)
        write(OUT/'FAILED.json',{'stage':'coordinator','error':repr(error),'traceback':traceback.format_exc()})
        raise
