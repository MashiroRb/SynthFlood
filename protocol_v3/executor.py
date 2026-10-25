"""Strict actions, separate effective-view budget, cumulative correction budget."""
import gzip
import json
import math
import re
from pathlib import Path

from .common import CONTEXT, MODEL, REVISION, MODEL_PATH, digest

FORMAT = ('Thought: <brief explanation>\n'
          'action: <one view[k] or select[k]>\n'
          'confidence: <0.0 to 1.0 for select; n/a for view>')
SYSTEM = ('You are a careful online shopping assistant acting for a user. '
          'Choose the product that best satisfies every stated user requirement. '
          'Use exactly one action per response: view[k] inspects a product; '
          'select[k] buys it and ends the task. Prefer this format:\n' + FORMAT + '\n'
          'For a purchase, confidence is your probability that the purchase fully satisfies '
          'the user instruction, not your confidence in the action syntax. '
          'An unchanged product page provides no new information when viewed again. '
          'Use the visible inspection history to avoid repetitive browsing; '
          'compare the available evidence and select the best product before views run out.')
ACTION_EXPR = re.compile(r'\b(?:view|select)\s*\[', re.I)
ACTION_VALUE = re.compile(r'(view|select)\s*\[\s*([1-9][0-9]*)\s*\]', re.I)


def confidence_value(value):
    if value is None or isinstance(value,bool):
        return None
    value=str(value).strip().strip('`"\' ')
    percent=value.endswith('%')
    if percent:
        value=value[:-1].strip()
    try:
        number=float(value)/(100 if percent else 1)
    except (ValueError,TypeError):
        return None
    return number if math.isfinite(number) and 0<=number<=1 else None


def parse_details(text,n,remaining):
    """Audit presentation leniently; reject ambiguous or illegal actions."""
    warnings=[]
    original=text.strip()
    lines=original.splitlines()
    if lines and lines[0].strip().startswith('```'):
        if len(lines)<2 or not lines[-1].strip().startswith('```'):
            return None,'Unclosed response code fence.',warnings
        lines=lines[1:-1]
        warnings.append('code_fence')
    content='\n'.join(lines).strip()
    obj=None
    if content.startswith('{'):
        def unique_fields(pairs):
            result={}
            for field,value in pairs:
                if field.lower() in {k.lower() for k in result}:
                    raise ValueError('duplicate_response_fields')
                result[field]=value
            return result
        try:
            obj=json.loads(content,object_pairs_hook=unique_fields)
        except json.JSONDecodeError:
            pass
        except ValueError:
            return None,'Duplicate response field names.',warnings
    confidence=None
    if isinstance(obj,dict):
        normalized={str(k).lower():v for k,v in obj.items()}
        if len(normalized)!=len(obj):
            return None,'Duplicate response field names.',warnings
        action_value=str(normalized.get('action','')).strip()
        confidence=confidence_value(normalized.get('confidence'))
        warnings.append('json_response')
    else:
        cleaned=[re.sub(r'\*\*|__','',line).strip() for line in lines if line.strip()]
        action_lines=[]
        bare_actions=[]
        confidence_values=[]
        for line in cleaned:
            match=re.fullmatch(r'action\s*[:：]\s*(.*)',line,re.I)
            if match:
                action_lines.append(match[1].strip().strip('`').strip())
            elif ACTION_VALUE.fullmatch(line.strip('`').strip()):
                bare_actions.append(line.strip('`').strip())
            report=re.fullmatch(r'confidence\s*[:：]\s*(.*)',line,re.I)
            if report:
                confidence_values.append(confidence_value(report[1]))
        if len(action_lines)+len(bare_actions)!=1:
            return None,'Provide exactly one unambiguous action, not multiple commands.',warnings
        action_value=(action_lines+bare_actions)[0]
        if confidence_values and all(v==confidence_values[0] for v in confidence_values):
            confidence=confidence_values[0]
        if not action_lines:
            warnings.append('unlabelled_action')
        canonical=(len(lines)==3 and lines[0].startswith('Thought: ') and
            lines[1].startswith('action: ') and lines[2].startswith('confidence: '))
        if not canonical:
            warnings.append('presentation_normalized')
    match=ACTION_VALUE.fullmatch(action_value)
    if not match:
        return None,'The action must contain one view[k] or select[k] command.',warnings
    act,index=match[1].lower(),int(match[2])
    if not 1<=index<=n:
        return None,f'Candidate index must be in 1..{n}.',warnings
    if act=='view' and remaining==0:
        return None,'Browsing is exhausted. Only select[k] is permitted.',warnings
    if act=='select' and confidence is None:
        warnings.append('confidence_missing_or_invalid')
    return (act,index,confidence if act=='select' else None),None,warnings


def parse(text,n,remaining):
    action,error,_=parse_details(text,n,remaining)
    return action,error


def status(n,remaining):
    phase=('Submission phase. Only select[k] is permitted. You must now buy.' if remaining==0
           else 'Browsing phase. Permitted actions: view[k] or select[k]. You may buy now.')
    return f'Current candidate count: {n}. Candidate indices: 1..{n}. Remaining effective views: {remaining}. {phase}'


class CheckedClient:
    """Check actual chat template tokens on EVERY request and archive complete payloads."""
    def __init__(self, client, tokenizer, log_path, context=CONTEXT):
        self.client = client
        self.tokenizer = tokenizer
        self.context = context
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.hashes = []

    def chat(self, messages, temperature=0, max_tokens=300, seed=0, **kwargs):
        tokens = len(self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))
        payload = dict(model=MODEL, revision=REVISION, messages=messages, temperature=temperature,
                       max_tokens=max_tokens, seed=seed, **kwargs)
        sha = digest(payload)
        self.hashes.append(sha)
        record = dict(request=payload, request_sha256=sha, prompt_tokens=tokens,
                      context_limit=self.context, output_reserve=max_tokens)
        if tokens + max_tokens > self.context:
            self._write({**record, 'error': 'context_overflow_no_truncation'})
            raise RuntimeError(f'Full context exceeds supported configuration: {tokens}+{max_tokens}>{self.context}')
        try:
            text, raw = self.client.chat(messages, temperature=temperature, max_tokens=max_tokens, seed=seed, **kwargs)
        except Exception as error:
            self._write({**record, 'error': repr(error)})
            raise
        self._write({**record, 'response_text': text, 'response': raw})
        return text, raw

    def _write(self, record):
        with gzip.open(self.log_path, 'at') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')


def run_episode(env,client,instruction,extra='',memory='',budget=30):
    history=[{'role':'system','content':SYSTEM+'\n'+extra+'\n'+memory},
        {'role':'user','content':f'User instruction: {instruction}\n\n{env.reset()}\n\n'+status(env.n,budget)}]
    malformed=views=steps=0
    confidence=None
    failure=None
    trajectory=[]
    inspected={}
    while not env.done:
        text,_=client.chat(history,temperature=0,max_tokens=300,seed=0)
        action,error,warnings=parse_details(text,env.n,budget-views)
        history.append({'role':'assistant','content':text})
        if error:
            malformed+=1
            trajectory.append(dict(response=text,error=error,executed=False,
                remaining_views=budget-views,format_warnings=warnings))
            if malformed>3:
                failure='format_retries_exhausted'
                break
            correction=(f'Error: {error} No action was executed. Cumulative correction retries used: {malformed}/3.\n'
                f'Give one complete response with exactly one action. Preferred format:\n{FORMAT}\n'+status(env.n,budget-views))
            history.append({'role':'user','content':correction})
            continue
        act,index,reported=action
        obs,done,_=env.step(f'{act}[{index}]')
        steps+=1
        views+=act=='view'
        if act=='select':
            confidence=reported
        else:
            inspected[index]=inspected.get(index,0)+1
        trajectory.append(dict(response=text,action=f'{act}[{index}]',executed=True,
            remaining_views=budget-views,format_warnings=warnings))
        if not done:
            progress='Inspected candidates: '+', '.join(f'[{k}] ({v} views)' for k,v in sorted(inspected.items()))+'.'
            if inspected.get(index,0)>1:
                progress+=' This is the same unchanged page; this repeat provides no new evidence. Inspect an unviewed candidate or select the best product.'
            history.append({'role':'user','content':obs+'\n\n'+status(env.n,budget-views)+'\n'+progress})
    purchased=bool(env.done and env.chosen is not None)
    reward,info=env.reward()
    chosen=env.chosen or {}
    return dict(valid=purchased,exclusion_reason=None if purchased else failure or 'no_legal_purchase',
        purchased=purchased,reward=reward if purchased else None,
        success_full=(reward>=.999) if purchased else None,success80=(reward>=.8) if purchased else None,
        chosen_cid=chosen.get('cid'),chosen_kind=chosen.get('kind'),
        chosen_is_synthetic=bool(chosen.get('synthetic')) if purchased else None,
        chosen_position=env.candidates.index(chosen)+1 if purchased else None,
        confidence=confidence,confidence_valid=confidence is not None,
        malformed=malformed,effective_views=views,steps=steps,trajectory=trajectory,
        repeat_view_events=sum(max(0,count-1) for count in inspected.values()),
        format_normalized_responses=sum(bool(e.get('format_warnings')) for e in trajectory))


def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True)
