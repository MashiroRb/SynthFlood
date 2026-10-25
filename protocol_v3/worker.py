import argparse
import copy
import math
import time
import gzip
import json
import urllib.request

from .common import *
from .executor import CheckedClient, run_episode, tokenizer
from .plans import cases, key, request_definition
from paired_sweep_ratingfix.defenses import transform, _page_text


class Evaluator:
    def __init__(self, directory, tok, backend):
        self.directory = directory
        self.tok = tok
        self.backend = backend
        self.cache = {}

    def evaluate(self, case, final, extra, memory='', force=False):
        from synthflood.select_env import SelectEnv
        from synthflood.vllm_client import LLMClient
        case_key = key(case)
        definition = request_definition(case, final, extra, memory)
        sha = digest(definition)
        info = {k: v for k,v in case.items() if k not in ('block','candidates')}
        result = dict(**info, case_key=case_key, input_sha256=sha, backend_sha256=self.backend,
                      candidate_ids=[c['cid'] for c in final], pre_sha256=digest(case['candidates']),
                      final_sha256=digest(final), candidate_count=len(final))
        cached = self.cache.get(sha) if not force else None
        if cached:
            result.update({k:v for k,v in cached.items() if k not in info and k not in result})
            result.update(origin='reused_new_protocol', source_case_key=cached['case_key'],
                          source_result_sha256=digest(cached), new_model_calls=0)
        else:
            request_log = self.directory / 'requests' / (case_key.replace(':','_') + ('_sentinel' if force else '') + '.jsonl.gz')
            base = LLMClient(8000, MODEL)
            checked = CheckedClient(base, self.tok, request_log,context=definition['context'])
            env = SelectEnv(case['block']['goal'], copy.deepcopy(final), n_candidates=len(final))
            summary = run_episode(env, checked, case['block']['goal']['instruction_text'], extra=extra,
                                  memory=memory, budget=definition['effective_view_budget'])
            if summary['valid'] and case['phase'] in ('main','defense'):
                assert abs(summary['reward']-case['block']['reward_by_cid'][summary['chosen_cid']])<1e-9
            gold = next((c for c in case['candidates'] if c['kind']=='gold'), None)
            if 'gold_reward' in case['block']:
                gold_reward = case['block']['gold_reward']
            else:
                goldenv = SelectEnv(case['block']['goal'], [copy.deepcopy(gold)], n_candidates=1)
                goldenv.step('select[1]')
                gold_reward = goldenv.reward()[0]
            result.update(summary, origin='new', source_case_key=None,
                request_log=str(request_log.relative_to(ROOT)), request_sha256=checked.hashes,
                request_sequence_sha256=digest(checked.hashes), new_model_calls=base.calls,
                gold_reward=gold_reward,
                regret=gold_reward-summary['reward'] if summary['valid'] else None)
            if not force:
                self.cache[sha] = result
        if force:
            reference = self.cache[sha]
            fields = ('chosen_cid','reward','confidence','valid','request_sequence_sha256')
            assert all(result[k] == reference[k] for k in fields), 'Same-service repeatability sentinel failed'
            result['source_case_key'] = reference['case_key']
            append(self.directory/'sentinels.jsonl', result)
        else:
            append(self.directory/(case['phase']+'.jsonl'), result)
        return result


def run(lane):
    validate()
    directory = OUT/f'worker{lane}'
    if (directory/'STARTED.json').exists():
        raise RuntimeError('Refusing uncontrolled worker resume')
    write(directory/'STARTED.json', {'lane':lane})
    backend = digest(read(directory/'hardware.json'))
    ev = Evaluator(directory, tokenizer(), backend)
    blocks = read(DATA/'blocks.json')
    typed = read(DATA/'typed.json')
    probes = read(DATA/'probes.json')
    eligibility = read(DATA/'eligibility_audit.json')
    local = [b for b in blocks if b['lane']==lane]
    sentinel = None
    count = 0
    for case in cases(blocks, typed, probes, eligibility, lane):
        final, extra, _ = transform(case['block'], case['candidates'], case['k'], case['rotation'], 'none', {})
        ev.evaluate(case, final, extra)
        if sentinel is None:
            sentinel = (case, final, extra)
            ev.evaluate(*sentinel, force=True)
        count += 1
        if count % 100 == 0:
            print('STATELESS_PROGRESS', lane, count, flush=True)
    ev.evaluate(*sentinel, force=True)
    # Freeze detector scores and every defense plan before any defense purchase.
    from synthflood.vllm_client import LLMClient
    score_cache = {}
    plans = []
    for b in local:
        ppl = {}
        for c in b['base']+b['synthetics']:
            text = _page_text(c)[:3000]
            h = digest(text)
            if h not in score_cache:
                # Same current detector calculation, including its one echoed
                # completion token; archive the actual full request/response.
                payload=dict(model=MODEL,prompt=text,max_tokens=1,temperature=0.,echo=True,logprobs=0,seed=0)
                tokens=len(ev.tok.encode(text))
                assert tokens+1<=STATELESS_CONTEXT
                from synthflood.config import vllm_url
                req=urllib.request.Request(vllm_url(8000).rstrip('/')+'/completions',
                    data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=600) as response:
                    response=json.loads(response.read().decode())
                lps=response['choices'][0]['logprobs']['token_logprobs']
                vals=[v for v in lps[1:] if v is not None]
                n=len(vals)
                value=math.exp(-sum(vals)/max(1,n))
                assert math.isfinite(value) and n>0
                score_cache[h] = dict(ppl=value, n_logprobs=n)
                with gzip.open(directory/'detector_requests.jsonl.gz','at') as stream:
                    stream.write(json.dumps(dict(request=payload,request_sha256=digest(payload),response=response,
                        prompt_tokens=tokens,text_sha256=h,**score_cache[h]),ensure_ascii=False)+'\n')
            ppl[c['cid']] = score_cache[h]
        for k in (0,6):
            for r in range(10):
                raw = replace(b,b['synthetics'][:k],r)
                for arm in ARMS:
                    final,extra,metadata = transform(b,raw,k,r,arm,ppl)
                    case=dict(phase='defense',condition=f'{arm}:k{k}',task_id=b['task_id'],seed=b['seed'],
                        rotation=r,k=k,family='mix',block=b,candidates=raw,arm=arm)
                    plans.append(dict(case=case,final=final,extra=extra,metadata=metadata))
    # A compact manifest of every fully transformed plan, before purchases.
    write(directory/'DEFENSE_PLAN_FROZEN.json',dict(plans=[dict(case_key=key(p['case']),
          definition_sha256=digest(request_definition(p['case'],p['final'],p['extra'])),metadata=p['metadata']) for p in plans],
          detector_log_sha256=file_sha(directory/'detector_requests.jsonl.gz')))
    rng('v3_defense_order',lane,20261023).shuffle(plans)
    for i,p in enumerate(plans):
        ev.evaluate(p['case'],p['final'],p['extra'])
        if i%100==0:
            print('DEFENSE_PROGRESS',lane,i+1,'/',len(plans),flush=True)
    ev.evaluate(*sentinel, force=True)
    validate()
    write(directory/'COMPLETE.json',dict(validated=True,lane=lane,nondefense_rows=count,defense_rows=len(plans)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('lane',type=int)
    run(p.parse_args().lane)
