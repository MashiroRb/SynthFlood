"""Recovery adapters around the unchanged, frozen experiment implementation."""
import copy
import gzip
import json
import os
from pathlib import Path
import shutil
import time

from protocol_v3.common import ROOT,digest,append
from protocol_v3.executor import CheckedClient
from protocol_v3.plans import key,request_definition
from protocol_v3 import worker


def preserve(path):
    target=path.with_name(path.name+f'.before-repair-{time.time_ns()}')
    shutil.copyfile(path,target)
    return target


def read_rows(path,repair=False):
    path=Path(path)
    if not path.exists():return []
    data=path.read_bytes();lines=data.splitlines(keepends=True);out=[];kept=[]
    for i,line in enumerate(lines):
        try:row=json.loads(line)
        except json.JSONDecodeError:
            if i!=len(lines)-1:raise
            break
        out.append(row);kept.append(line if line.endswith(b'\n') else line+b'\n')
    corrected=b''.join(kept)
    if repair and corrected!=data:
        preserve(path)
        temporary=path.with_suffix(path.suffix+'.repair');temporary.write_bytes(corrected);os.replace(temporary,path)
    return out


def read_request_prefix(path,repair=True):
    path=Path(path)
    if not path.exists():return []
    rows=[];damaged=False
    try:
        with gzip.open(path,'rt') as stream:
            for line in stream:
                row=json.loads(line)
                if 'response_text' not in row or 'response' not in row:
                    damaged=True;break
                rows.append(row)
    except (EOFError,OSError,json.JSONDecodeError):damaged=True
    if repair and damaged:
        preserve(path)
        temporary=path.with_suffix(path.suffix+'.repair')
        with gzip.open(temporary,'wt') as stream:
            for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        os.replace(temporary,path)
    return rows


class ReplayCheckedClient(CheckedClient):
    counts={}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.prefix=read_request_prefix(self.log_path)
        self.replayed=0;self.fresh=0

    def chat(self,messages,temperature=0,max_tokens=300,seed=0,**kwargs):
        if self.replayed<len(self.prefix):
            from protocol_v3.common import MODEL,REVISION
            row=self.prefix[self.replayed]
            payload=dict(model=MODEL,revision=REVISION,messages=messages,temperature=temperature,
                max_tokens=max_tokens,seed=seed,**kwargs)
            if digest(payload)!=row['request_sha256']:
                raise RuntimeError('Refusing replay with a changed request: '+str(self.log_path))
            tokens=len(self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True))
            assert tokens==row['prompt_tokens'] and tokens+max_tokens<=self.context
            self.hashes.append(row['request_sha256']);self.replayed+=1
            # This counter describes all real successful calls belonging to
            # this case, including its already archived prefix before restart.
            self.client.calls+=1
            usage=row['response'].get('usage',{})
            for field,name in [('tokens_in','prompt_tokens'),('tokens_out','completion_tokens')]:
                if hasattr(self.client,field):setattr(self.client,field,getattr(self.client,field)+usage.get(name,0))
            self.counts[str(self.log_path)]=(self.replayed,self.fresh)
            return row['response_text'],row['response']
        result=super().chat(messages,temperature=temperature,max_tokens=max_tokens,seed=seed,**kwargs)
        self.fresh+=1;self.counts[str(self.log_path)]=(self.replayed,self.fresh)
        return result


class Frontier(Exception):pass


class ResumeEvaluator(worker.Evaluator):
    def __init__(self,directory,tok,backend,dry_run=False):
        super().__init__(directory,tok,backend)
        self.completed={};self.dry_run=dry_run;self.skipped=0;self.added=0
        for phase in ('shopping','exam'):
            for row in read_rows(directory/(phase+'.jsonl'),repair=not dry_run):
                if row['case_key'] in self.completed:raise RuntimeError('Duplicate saved case')
                self.completed[row['case_key']]=row

    def switch_seed(self,seed):
        self.cache.clear()
        for row in self.completed.values():
            if row['seed']==seed and row['backend_sha256']==self.backend and row['origin']=='new':
                self.cache.setdefault(row['input_sha256'],row)

    def evaluate(self,case,final,extra,memory='',force=False):
        identity=key(case)
        if identity in self.completed:
            row=self.completed[identity]
            if digest(request_definition(case,final,extra,memory))!=row['input_sha256']:
                raise RuntimeError('Saved-result input/memory mismatch: '+identity)
            self.skipped+=1
            return row
        if self.dry_run:raise Frontier(identity)
        result=super().evaluate(case,final,extra,memory,force)
        self.completed[identity]=result;self.added+=1
        log=result.get('request_log')
        prefix,fresh=ReplayCheckedClient.counts.get(str(ROOT/log) if log else '',(0,0))
        append(self.directory/'resume_events.jsonl',dict(case_key=identity,
            historical_request_prefix=prefix,fresh_successful_calls=fresh,
            backend_sha256=result['backend_sha256'],job_id=os.environ.get('SLURM_JOB_ID')))
        return result


def install_replay_client():
    # This mutation affects this auxiliary Python process only.
    worker.CheckedClient=ReplayCheckedClient
