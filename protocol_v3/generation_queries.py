"""Freeze generation-only keyword repairs without changing official task metadata."""
import copy
import json

from .common import *
from .generation_json import extract_json

PROMPT='''Check whether an original search-query phrase is compatible with the actual product type.
Broad but relevant queries are acceptable. Reject a clearly different product type, for example
"skin care sets & kits" for hair clippers, or "elbow pads" for swimsuits.
Judge product TYPE only, not size/color, wording quality, price, or shopping success.
Reply ONLY JSON: {{"compatible": true or false, "reason": "at most20 words"}}.
Original query: {query}
Actual product title: {title}
Verified product category: {category}
Actual attributes: {attributes}
'''


def fallback_query(target):
    parts=[part.strip() for part in str(target['goal'].get('product_category') or '').split('›') if part.strip()]
    if parts:
        return parts[-1]
    title=str(target['gold']['item'].get('Title') or '').strip()
    if not title:
        raise ValueError(f"Target {target['task_id']} has neither category nor product title")
    return title


def generation_queries(targets,client):
    mapping={}
    for target in targets:
        goal=target['goal'];gi=target['task_id']
        prompt=PROMPT.format(query=goal['query'],title=target['gold']['item']['Title'],
            category=goal['product_category'],attributes=target['gold']['item'].get('Attributes'))
        answer=None
        for attempt in range(3):
            text,_=client.chat([dict(role='user',content=prompt)],temperature=0,max_tokens=120,seed=20261023)
            answer=extract_json(text)
            if isinstance(answer,dict) and type(answer.get('compatible')) is bool:
                break
        compatible=isinstance(answer,dict) and answer.get('compatible') is True
        leaf=fallback_query(target)
        mapping[str(gi)]=dict(task_id=gi,asin=goal['asin'],original_query=goal['query'],
            compatible=compatible,generation_query=goal['query'] if compatible else leaf,
            reason=answer.get('reason','unparseable_compatibility') if isinstance(answer,dict) else 'unparseable_compatibility',
            rule='keep compatible original query; otherwise use last nonempty verified category component, or real title if category is empty',
            official_goal_changed=False)
        print('GENERATION_QUERY_QA',gi+1,'/100','compatible',compatible,flush=True)
    write(DATA/'generation_queries.json',mapping)
    write(DATA/'generation_queries_frozen.json',dict(target_sha256=file_sha(DATA/'exam_targets.json'),
        mapping_sha256=file_sha(DATA/'generation_queries.json'),n_tasks=100,
        repaired_count=sum(not x['compatible'] for x in mapping.values()),
        original_scoring_metadata_preserved=True,frozen_before_new_generation=True))
    return mapping


def generation_goal(target,mapping):
    value=copy.deepcopy(target['goal'])
    value['query']=mapping[str(target['task_id'])]['generation_query']
    return value


def retain_input(row,mapping):
    info=mapping[str(row['task_id'])]
    actual=row.get('generation_query',info['original_query'])
    return actual==info['generation_query']
