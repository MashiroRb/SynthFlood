"""Continue saved trajectories or start only explicitly assigned unstarted seeds."""
import argparse
import copy
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
from protocol_v3.common import DATA,OUT,MODEL,digest,read,write,append,validate
from protocol_v3.executor import tokenizer,CheckedClient
from protocol_v3.washout import full_memory
from paired_sweep_ratingfix.common import COMMON_PROMPT
from m1.m1_memory import MemoryStore,LESSON_PROMPT,_extract_json
from synthflood.select_env import product_fields
from synthflood.vllm_client import LLMClient
from resume_core import ResumeEvaluator,ReplayCheckedClient,Frontier,read_rows,read_request_prefix,install_replay_client


def find_old_client(job,shard):
    found=[]
    for path in Path('/proc').glob('[0-9]*'):
        try:
            if path.stat().st_uid!=os.getuid():continue
            argv=(path/'cmdline').read_bytes().split(b'\0')
            if b'protocol_v3.washout' not in argv:continue
            if str(shard).encode() not in argv:continue
            environment=dict(part.split(b'=',1) for part in (path/'environ').read_bytes().split(b'\0') if b'=' in part)
            if environment.get(b'SLURM_JOB_ID')==str(job).encode():found.append(int(path.name))
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    if len(found)!=1:raise RuntimeError(f'Expected one original client for job {job}, found {found}')
    return found[0]


def validated_release_target(job,requested=None):
    target=requested or str(job)
    if job==150039 and target!='150039_1':
        raise RuntimeError('Refusing parent-array cancellation; require the assigned exact element')
    return target


def recover_lesson(directory,seed,group,t,saved):
    for entry in saved:
        if entry['type']=='lesson' and entry['t']==t:return copy.deepcopy(entry)
    paths=[directory/f'seed{seed}'/f'lesson_calls_{group}.jsonl']
    records=[r for path in paths for r in read_rows(path) if r['t']==t]
    responses=[r.get('response','') for r in records]
    responses += [r['response_text'] for r in read_request_prefix(directory/'requests'/f'lesson_{seed}_{group}_{t}.jsonl.gz',repair=False)]
    for text in responses:
        value=_extract_json(text)
        if value and value.get('lesson'):
            return dict(type='lesson',t=t,arm=group,text=str(value['lesson'])[:400],tags=value.get('tags') or [],data={})
    return None


def execute(directory,seeds,tok,backend,dry_run=False):
    install_replay_client()
    ev=ResumeEvaluator(directory,tok,backend,dry_run=dry_run)
    shopping=read(DATA/'washout.json');exams=read(DATA/'exams.json')
    for seed in seeds:
        ev.switch_seed(seed)
        for group in ('M0','B0'):
            path=directory/f'seed{seed}'/f'memory_{group}.json'
            saved=read(path)['entries'] if path.exists() else []
            mem=MemoryStore(str(path),group);mem.entries=[]
            def verify_prefix():
                size=min(len(saved),len(mem.entries))
                if mem.entries[:size]!=saved[:size]:
                    raise RuntimeError(f'Saved-memory prefix mismatch: {seed}:{group}')
            def persist():
                verify_prefix()
                if not dry_run and len(mem.entries)>=len(saved):write(path,mem.export())
            def lesson(t):
                archived=recover_lesson(directory,seed,group,t,saved)
                if archived is not None:
                    mem.entries.append(archived);return
                if dry_run:raise Frontier(f'lesson:{seed}:{group}:{t}')
                checked=ReplayCheckedClient(LLMClient(8000,MODEL),tok,directory/'requests'/f'lesson_{seed}_{group}_{t}.jsonl.gz')
                recent=[e for e in mem.entries if e['type']=='observation'][-5:]
                notes='\n'.join(f"- {e['text']}" for e in recent)
                for attempt in range(3):
                    before=checked.replayed
                    messages=[dict(role='user',content=LESSON_PROMPT.format(notes=notes))]
                    text,raw=checked.chat(messages,temperature=0,max_tokens=160,seed=seed*10000+t)
                    if checked.replayed==before:
                        append(directory/f'seed{seed}'/f'lesson_calls_{group}.jsonl',dict(t=t,attempt=attempt,
                            messages=messages,temperature=0,seed=seed*10000+t,max_tokens=160,response=text,raw=raw))
                    value=_extract_json(text)
                    if value and value.get('lesson'):
                        mem.add_lesson(t,value['lesson'],value.get('tags'));return
                raise RuntimeError('Lesson generation exhausted original three attempts')
            def shop(plan,t,phase):
                case=dict(phase='shopping',condition=f'{group}:{phase}',task_id=plan['task_id'],seed=seed,
                    rotation=plan['rotation'],k=6 if phase=='pollution' else 0,family='mix',
                    block=dict(goal=plan['goal']),candidates=plan['candidates'],arm=group,episode=t)
                result=ev.evaluate(case,copy.deepcopy(plan['candidates']),COMMON_PROMPT,full_memory(mem))
                chosen=next((c for c in plan['candidates'] if c['cid']==result['chosen_cid']),None)
                description=None if chosen is None else f"'{product_fields(chosen['item'])['title']}' at ${chosen['price_float']:.2f}"
                if result['valid']:
                    mem.add_observation(t,plan['goal']['query'],result['chosen_kind'],result['reward'],
                        result['gold_reward'],choice_description=description)
                else:
                    mem.entries.append(dict(type='observation',t=t,arm=group,
                        text=f"Episode {t}: task '{plan['goal']['query']}'. No purchase completed; task failed ({result['exclusion_reason']}); official reward unavailable.",
                        data=dict(chosen_kind='none',reward=None,gold_reward=result['gold_reward'])))
                if t%5==0:lesson(t)
                persist()
            def exam(cp):
                verify_prefix();memory=full_memory(mem);before=digest(mem.entries)
                checkpoint=directory/f'seed{seed}'/f'checkpoint_{group}_{cp:02d}.json'
                snapshot=dict(entries=mem.entries,injected_context=memory,context_sha256=digest(memory))
                if checkpoint.exists():
                    if read(checkpoint)!=snapshot:raise RuntimeError(f'Checkpoint mismatch: {checkpoint}')
                elif not dry_run:write(checkpoint,snapshot)
                for i,q in enumerate(exams):
                    case=dict(phase='exam',condition=f'{group}:cp{cp}:{q["family"]}',task_id=q['task_id'],seed=seed,
                        rotation=q['order'],k=1,family=q['family'],block=dict(goal=q['goal']),
                        candidates=q['candidates'],arm=group,group=group,checkpoint=cp)
                    ev.evaluate(case,copy.deepcopy(q['candidates']),COMMON_PROMPT,memory)
                    if not dry_run and i%100==0:print('RESUME_EXAM_PROGRESS',directory.name,seed,group,cp,i,'skipped',ev.skipped,'added',ev.added,flush=True)
                assert digest(mem.entries)==before
            if group=='M0':
                for t,plan in enumerate(shopping[str(seed)]['pollution'],1):shop(plan,t,'pollution')
            exam(0)
            offset=40 if group=='M0' else 0
            for t,plan in enumerate(shopping[str(seed)]['clean'],1):
                shop(plan,offset+t,'clean')
                if t%2==0:exam(t)
            assert sum(e['type']=='observation' for e in mem.entries)==(80 if group=='M0' else 40)
            assert sum(e['type']=='lesson' for e in mem.entries)==(16 if group=='M0' else 8)
            persist()
        if not dry_run:write(directory/f'seed{seed}'/'COMPLETE_RESUMABLE.json',dict(validated=True,seed=seed))
    return ev


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--shard',type=int,required=True)
    parser.add_argument('--seeds',type=int,nargs='+',required=True);parser.add_argument('--attach-job',type=int)
    parser.add_argument('--release-target')
    args=parser.parse_args();validate()
    directory=OUT/f'washout{args.shard}';directory.mkdir(exist_ok=True)
    with (directory/'RESUME.lock').open('w') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        tok=tokenizer();backend=digest(read(directory/'hardware.json'))
        old_pid=None;attached=False
        if args.attach_job:
            prior_handoff=(directory/'CLIENT_HANDOFF.json').exists()
            old_pid=find_old_client(args.attach_job,args.shard)
            os.kill(old_pid,signal.SIGSTOP)
            # Only the old client is paused; its model server and Slurm job continue.
            time.sleep(.2)
            try:
                try:execute(directory,args.seeds,tok,backend,dry_run=True)
                except Frontier as frontier:print('RESUME_PREFIX_VERIFIED',str(frontier),flush=True)
            except BaseException:
                if not prior_handoff:os.kill(old_pid,signal.SIGCONT)
                raise
            write(directory/'CLIENT_HANDOFF.json',dict(old_job=args.attach_job,paused_client_pid=old_pid,
                continuation_job=os.environ['SLURM_JOB_ID'],assigned_seeds=args.seeds,
                server_preserved=True,completed_results_preserved=True))
            attached=True
        ev=execute(directory,args.seeds,tok,backend)
        validate()
        write(directory/'COMPLETE.json',dict(validated=True,seeds=args.seeds,skipped_completed=ev.skipped,
            added_this_attempt=ev.added,resumable=True))
        if attached:
            # This allocation has now completed every seed assigned to it.
            release_target=validated_release_target(args.attach_job,args.release_target)
            result=subprocess.run(['scancel',release_target],text=True,capture_output=True)
            write(directory/'ALLOCATION_FINISHED.json',dict(old_job=args.attach_job,returncode=result.returncode,
                completion='all assigned trajectories complete; GPU service released',stderr=result.stderr))
            for attempt in range(30):
                state=subprocess.run(['squeue','-h','-j',release_target,'-o','%i'],text=True,capture_output=True)
                if not state.stdout.strip():break
                time.sleep(1)
            failed=directory/'FAILED.json'
            if failed.exists():
                archive=directory/'attempts'/os.environ['SLURM_JOB_ID'];archive.mkdir(parents=True,exist_ok=True)
                failed.rename(archive/'completed-allocation-cleanup.json')
        print('RESUMABLE_WASHOUT_COMPLETE',args.shard,args.seeds,flush=True)

if __name__=='__main__':main()
