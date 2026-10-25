"""Pre-generation QA of real targets; no synthetic purchase outcome is consulted."""
import collections
import copy
import json

from .common import *

QA_PROMPT = """Audit the consistency of an ORIGINAL shopping benchmark task and its REAL target product.
This is a data-quality check before generating any synthetic candidates.
Compare the shopping instruction, the declared fine product category, and the actual product title/specifications.
Reject clear product-type mismatches (for example an instruction/category for elbow pads paired with an actual swimsuit).
Accept ordinary paraphrases and specific category names that are compatible with the product.
Variant options may satisfy a requested color/size even if the current title names another variant.
Do not reject only because a product has an unknown rating/review count.
Do not invent missing evidence. Mark uncertain cases false.
Return ONLY a JSON object with boolean fields instruction_matches_product and category_matches_product,
and a short reason of at most30 words.

Task and real target:
{record}
"""


def quality_and_select(client):
    from synthflood.contaminate import _extract_json
    from synthflood.select_env import product_fields
    reservoir=read(DATA/'exam_reservoir.json')
    sampling=read(DATA/'exam_reservoir_sampling.json')
    reports=[];passed=[]
    for i,t in enumerate(reservoir):
        f=product_fields(t['gold']['item'])
        evidence=dict(asin=t['goal']['asin'],instruction=t['goal']['instruction_text'],
            declared_category=t['goal']['product_category'],query=t['goal']['query'],
            title=f['title'],attributes=f['attrs'],bullets=f['bullets'][:6],description=f['desc'][:1500],
            options=t['gold']['item'].get('options'),price=t['gold']['price_float'],
            instruction_attributes=t['goal']['attributes'],goal_options=t['goal']['goal_options'])
        report=dict(reservoir_index=i,asin=t['goal']['asin'],gold_reward=t['gold_reward'])
        if t['gold_reward']<.999:
            report.update(eligible=False,reason='official_gold_reward_below_0.999',judgments=[])
        else:
            judgments=[]
            for attempt in range(3):
                text,_=client.chat([dict(role='user',content=QA_PROMPT.format(record=json.dumps(evidence,ensure_ascii=False)))],
                    temperature=0,max_tokens=180,seed=20261023)
                answer=_extract_json(text)
                judgments.append(dict(text=text,parsed=answer))
                if isinstance(answer,dict) and type(answer.get('instruction_matches_product')) is bool and type(answer.get('category_matches_product')) is bool:
                    break
            eligible=bool(isinstance(answer,dict) and answer.get('instruction_matches_product') is True and answer.get('category_matches_product') is True)
            report.update(eligible=eligible,reason=answer.get('reason','unparseable_qa') if isinstance(answer,dict) else 'unparseable_qa',judgments=judgments)
        reports.append(report)
        append(DATA/'exam_quality_audit.jsonl',report)
        if report['eligible']:
            passed.append(t)
        if (i+1)%25==0:
            print('EXAM_TARGET_QA',i+1,'/',len(reservoir),'eligible',len(passed),flush=True)
    if len(passed)<100:
        raise RuntimeError(f'Only {len(passed)} consistent official exam targets; no generation will start')
    available=list(passed)
    selected=[];matches=[]
    for slot,(fine,coarse) in enumerate(zip(sampling['category_slots'],sampling['coarse_slots'])):
        exact=[t for t in available if t['goal']['product_category']==fine]
        same=[t for t in available if t['goal']['category']==coarse]
        candidate=(exact or same or available)[0]
        available.remove(candidate)
        new=copy.deepcopy(candidate)
        new['task_id']=slot
        selected.append(new)
        matches.append(dict(task_id=slot,asin=new['goal']['asin'],desired_category=fine,
            actual_category=new['goal']['product_category'],match='fine' if exact else 'coarse' if same else 'global',
            reservoir_index=new['reservoir_index']))
    asins={t['goal']['asin'] for t in selected}
    assert len(asins)==100 and not asins & set(sampling['forbidden_targets'])
    assert all(t['gold_reward']>=.999 for t in selected)
    write(DATA/'exam_targets.json',selected)
    write(DATA/'exam_quality_summary.json',dict(reservoir_size=len(reservoir),eligible_count=len(passed),selected_count=100,
        rejected_count=len(reports)-len(passed),selected_asins=sorted(asins),category_matching=matches,
        audit_sha256=file_sha(DATA/'exam_quality_audit.jsonl'),target_sha256=file_sha(DATA/'exam_targets.json'),
        selection='First eligible matching fixed category slots in the pre-frozen reservoir order; no synthetic generation or purchase outcomes',
        explicit_user_authorization='2026-10-23: consistency audit then re-freeze100 official tasks'))
    print('EXAM_TARGETS_QUALITY_FROZEN',100,flush=True)
