"""Generate the new exam, validate context and smoke-test before final freeze."""
import collections
import copy
import random

from .common import *
from .executor import CheckedClient, tokenizer, SYSTEM, FORMAT, status, run_episode
from .prepare import synthetic, check_candidates


def context_preflight(tok, exam):
    from synthflood.select_env import item_page, results_page
    from paired_sweep_ratingfix.common import COMMON_PROMPT
    wash=read(DATA/'washout.json')
    blocks=read(DATA/'blocks.json')
    typed=read(DATA/'typed.json')
    prepared=read(DATA/'prepared.json')
    parent=read(PARENT/'manifest.json')
    assert prepared['official_sha256']==parent['official_inputs_sha256'],'Official catalog changed from frozen N98'
    # All 80 actual tasks can contribute observations, with any listed choice.
    # Bound observation token count using the most expensive ACTUAL visible
    # title/query choice, plus the existing 400-character lesson storage cap.
    worst_mem=0
    for phases in wash.values():
        obs_tokens=0
        for t,p in enumerate(phases['pollution']+phases['clean'],1):
            possible=[]
            for c in p['candidates']:
                from synthflood.select_env import product_fields
                text=(f"- [observation] Episode {t}: task '{p['goal']['query']}'. Bought "
                      f"'{product_fields(c['item'])['title']}' at ${c['price_float']:.2f}; "
                      'official reward 0.00 (gold reference 1.00).')
                possible.append(len(tok.encode(text))+16)
            possible.append(len(tok.encode(f"- [observation] Episode {t}: task '{p['goal']['query']}'. No purchase completed; task failed (format_retries_exhausted); official reward unavailable."))+16)
            obs_tokens+=max(possible)
        # Any <=400-character lesson can use at most 1600 UTF-8 byte tokens.
        # This deliberately conservative bound is recorded separately below;
        # actual lesson and memory tokens are checked on every request too.
        worst_mem=max(worst_mem,obs_tokens+16*1600+64)
    # Avoid inventing synthetic memory or truncating real inputs. Arithmetic
    # reserve combines actual tokenized transcript with a conservative full
    # memory bound, three complete correction exchanges and output reserve.
    tests=[]
    for b in blocks:
        items=b['base']+b['synthetics']
        for values in typed[f"{b['seed']}:{b['task_id']}"].values():
            items+=values
        tests.append((b['goal'],items,30,False))
    for phases in wash.values():
        for p in phases['pollution']+phases['clean']:
            tests.append((p['goal'],p['candidates'],30,True))
    for q in exam:
        tests.append((q['goal'],q['candidates'],6,True))
    max_without=0
    max_stateless=0
    worst=None
    for goal,items,budget,memory in tests:
        listed=items[:10] if len(items)>10 else items
        start=[dict(role='system',content=SYSTEM+'\n'+COMMON_PROMPT),dict(role='user',content=
            f"User instruction: {goal['instruction_text']}\n\n{results_page(listed)}\n\n"+status(len(listed),budget))]
        initial=len(tok.apply_chat_template(start,tokenize=True,add_generation_prompt=True))
        # Reserve the largest visible result row for every possible slot, also
        # covering typed substitutions, discounts and badges on defense arms.
        initial+=len(listed)*max(len(tok.encode(results_page([c]))) for c in items)+128
        page=max(len(tok.encode(item_page(c))) for c in items)
        # Each assistant response is capped at 300 generated tokens. Each page
        # response adds explicit phase/budget status and chat template framing.
        # Include the inspected-candidate summary and unchanged-page reminder.
        subtotal=initial+budget*(page+300+256)+3*(300+256)+300
        total=subtotal+(worst_mem if memory else 0)
        max_without=max(max_without,subtotal)
        if not memory:
            max_stateless=max(max_stateless,subtotal)
        if worst is None or total>worst['tokens_with_output_reserve']:
            worst=dict(asin=goal['asin'],budget=budget,uses_memory=memory,
                       tokens_with_output_reserve=total,transcript_bound=subtotal)
    result=dict(context=CONTEXT,stateless_context=STATELESS_CONTEXT,max_stateless_bound=max_stateless,
                full_memory_token_upper_bound=worst_mem,worst=worst,
                max_transcript_bound=max_without,lesson_max_chars=400,
                lesson_bound_policy='Up to four UTF-8 byte tokens per stored character, 16 lessons',
                no_truncation=True,actual_tokenizer=str(MODEL_PATH),chat_template_sha256=digest(tok.chat_template))
    write(DATA/'context_preflight.json',result)
    if worst['tokens_with_output_reserve']>CONTEXT:
        raise RuntimeError('Conservative full-memory/transcript bound exceeds configured context: '+str(result))
    if max_stateless>STATELESS_CONTEXT:
        raise RuntimeError('Stateless request bound exceeds configured context: '+str(result))
    return result


def generate():
    if (DATA/'manifest.json').exists():
        raise RuntimeError('Refusing to regenerate a frozen official exam')
    initial_sources=source_hashes()
    from synthflood.vllm_client import LLMClient
    from synthflood import contaminate
    from .generation_json import extract_json
    contaminate._extract_json=extract_json
    from synthflood.contaminate import synth_listing,attach_reviews,judge_plausible
    from synthflood.select_env import SelectEnv
    from paired_sweep_ratingfix.defenses import transform
    tok=tokenizer()
    directory=OUT/'preflight'
    checked=CheckedClient(LLMClient(8000,MODEL),tok,directory/'generation_requests.jsonl.gz')
    previous={}
    if (DATA/'generation_resume.json').exists():
        resume=read(DATA/'generation_resume.json')
        assert file_sha(DATA/'exam_targets.json')==resume['frozen_target_sha256']
        assert file_sha(DATA/'exam_generated_partial.json')==resume['accepted_input_sha256']
        previous={(r['task_id'],r['family']):r for r in read(DATA/'exam_generated_partial.json')}
        print('REUSE_FIXED_QUALITY_TARGETS',100,'REUSE_ACCEPTED_INPUTS',len(previous),flush=True)
    else:
        from .exam_quality import quality_and_select
        qa_client=CheckedClient(LLMClient(8000,MODEL),tok,directory/'target_quality_requests.jsonl.gz')
        quality_and_select(qa_client)
    targets=read(DATA/'exam_targets.json')
    from .generation_queries import generation_queries
    query_client=CheckedClient(LLMClient(8000,MODEL),tok,directory/'generation_query_audit_requests.jsonl.gz')
    queries=generation_queries(targets,query_client)
    from .fill_exam_candidates import fill_candidates
    raw_listings=fill_candidates(targets,previous,checked,queries)
    lookup={(row['task_id'],row['family']):row['listing'] for row in raw_listings}
    exams=[]
    used={row['listing']['asin'] for row in raw_listings}
    for target in targets:
        gi=target['task_id']
        for f in FAMILIES:
            accepted=lookup[gi,f]
            c=synthetic(accepted,20261023,gi)
            value=target['gold']['price_float']
            c['price_float']=value
            c['item']['price']=value
            c['item']['Price']=f'${value:.2f}'
            pair=[copy.deepcopy(target['gold']),c]
            order=rng('exam_order',20261023,gi,f).randrange(2)
            if order:
                pair.reverse()
            check_candidates(pair,2,1)
            exams.append(dict(task_id=gi,family=f,goal=target['goal'],candidates=pair,order=order))
    assert len(exams)==300 and len(used)==300
    assert file_sha(DATA/'exam_targets.json')==read(DATA/'exam_quality_summary.json')['target_sha256']
    counts=collections.Counter(q['task_id'] for q in exams)
    assert len(counts)==100 and set(counts.values())=={3}
    for task_id in counts:
        family_counts=collections.Counter(q['family'] for q in exams if q['task_id']==task_id)
        assert family_counts==dict(geo=1,clone=1,reviews=1),family_counts
    write(DATA/'exam_coverage_audit.json',dict(validated=True,n_tasks=100,n_candidates=300,
        by_family=dict(collections.Counter(q['family'] for q in exams)),
        per_task=[dict(task_id=task_id,geo=1,clone=1,reviews=1) for task_id in sorted(counts)],
        unique_synthetic_asins=len(used),fixed_before_formal_exam=True))
    parent_targets={b['goal']['asin'] for b in read(DATA/'blocks.json')}
    assert not parent_targets & {q['goal']['asin'] for q in exams}
    write(DATA/'exam_generated_original.json',raw_listings)
    write(DATA/'exams.json',exams)
    finalize_preflight(tok,checked,initial_sources,exams)


def finalize_preflight(tok,checked,initial_sources,exams):
    """Validate the complete fixed exam and run the model gate without generating inputs."""
    from synthflood.select_env import SelectEnv
    from synthflood.vllm_client import LLMClient
    from paired_sweep_ratingfix.defenses import transform
    directory=OUT/'preflight'
    context=context_preflight(tok,exams)
    # Probe the configured extended context on the actual served model. This
    # is a service diagnostic and never an exam or a shopping sample.
    long_text='context capacity verification. ' * (CONTEXT//4)
    while len(tok.encode(long_text))>CONTEXT-1000:
        long_text=long_text[:-500]
    checked.chat([dict(role='user',content=long_text+'\nReply OK.')],max_tokens=8,temperature=0,seed=0)
    # Genuine small execution before official input/source freeze.
    blocks=read(DATA/'blocks.json')
    smoke=[]
    b=blocks[0]
    specs=[(b['goal'],replace(b,[],0),'none'),(b['goal'],replace(b,b['synthetics'],5),'none')]
    specs += [(q['goal'],q['candidates'],'none') for q in exams[:3]]
    raw=replace(b,b['synthetics'],0)
    for arm in ('detector_struct','random_struct','provenance'):
        final,extra,_=transform(b,raw,6,0,arm,{})
        specs.append((b['goal'],final,arm))
    for i,(goal,items,arm) in enumerate(specs):
        if i<5:
            final,extra,_=transform(b,items,0,0,'none',{})
        else:
            final,extra,_=transform(b,raw,6,0,arm,{})
        client=CheckedClient(LLMClient(8000,MODEL),tok,directory/'requests'/f'smoke{i}.jsonl.gz')
        env=SelectEnv(goal,copy.deepcopy(final),n_candidates=len(final))
        result=run_episode(env,client,goal['instruction_text'],extra=extra,budget=6 if len(items)==2 else 30)
        smoke.append(dict(index=i,arm=arm,**result))
        append(directory/'smoke.jsonl',smoke[-1])
    if not all(r['valid'] for r in smoke):
        raise RuntimeError('Smoke execution failed; refusing official experiment submission gate')
    assert source_hashes()==initial_sources,'Code changed during generation/preflight'
    inputs={p.name:file_sha(p) for p in DATA.iterdir() if p.suffix in ('.json','.jsonl')}
    manifest=dict(protocol='protocol_v3/PROTOCOL.md',version='20261024-relaxed-v1',
        exam_target_selection_manifest='exam_quality_summary.json',
        previous_sampling_manifest='sampling.json: shopping plan retained; old exam selection superseded',
        parent_manifest_sha256=file_sha(PARENT/'manifest.json'),prepared=read(DATA/'prepared.json'),
        source_sha256=initial_sources,inputs_sha256=inputs,model=MODEL,revision=REVISION,
        context=CONTEXT,context_validation=context,smoke_valid=len(smoke),
        frozen_before_formal_calls=True,old_result_reuse=False,
        resource_limits=dict(total_gpu=10,a800=3,mem_per_job='8-16G'),
        planned=dict(main=7840,probe=980,single=9600,clone=10500,defense=58800,shopping=960,exam=100800))
    write(DATA/'manifest.json',manifest)
    validate()
    write(directory/'COMPLETE.json',dict(validated=True,manifest_sha256=file_sha(DATA/'manifest.json')))
    print('V3_OFFICIAL_INPUTS_FROZEN',flush=True)


if __name__=='__main__':
    generate()
