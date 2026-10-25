"""Complete independent missing task/type cells; never stop at the first hole."""
import collections
import copy
from .common import *
from .generation_queries import generation_goal,retain_input


def fill_candidates(targets,previous,client,queries,passes=3,attempts_per_pass=20):
    from synthflood.contaminate import synth_listing,judge_plausible,attach_reviews
    expected=[(t['task_id'],f) for t in targets for f in FAMILIES]
    accepted={}
    dropped=[]
    for key,value in previous.items():
        row=copy.deepcopy(value) if 'listing' in value else dict(task_id=key[0],family=key[1],listing=copy.deepcopy(value))
        raw=row['listing']
        if retain_input(row,queries):
            row['generation_query']=queries[str(key[0])]['generation_query']
            accepted[key]=row
        else:
            dropped.append(dict(task_id=key[0],family=key[1],asin=raw['asin'],
                original_query=queries[str(key[0])]['original_query'],
                generation_query=queries[str(key[0])]['generation_query'],reason='generation_query_incompatible'))
    used={row['listing']['asin'] for row in accepted.values()}
    assert len(used)==len(accepted)
    write(DATA/'generation_input_adoption.json',dict(parent_accepted=len(previous),retained=len(accepted),
        regenerate=len(dropped),regeneration_cells=dropped,source_artifacts_preserved=True))

    def checkpoint(last_task=None,last_family=None):
        ordered=[accepted[k] for k in expected if k in accepted]
        write(DATA/'exam_generated_partial.json',ordered)
        pending=[dict(task_id=k[0],family=k[1]) for k in expected if k not in accepted]
        complete=sum(all((t['task_id'],f) in accepted for f in FAMILIES) for t in targets)
        write(DATA/'exam_generation_progress.json',dict(completed=len(ordered),planned=300,
            by_family=dict(collections.Counter(row['family'] for row in ordered)),complete_tasks=complete,
            last_task=last_task,last_family=last_family,pending_count=len(pending),pending=pending))

    checkpoint()
    for pass_index in range(passes):
        for target in targets:
            gi=target['task_id'];goal=generation_goal(target,queries)
            for family in FAMILIES:
                key=(gi,family)
                if key in accepted:
                    continue
                for local in range(attempts_per_pass):
                    attempt=pass_index*attempts_per_pass+local
                    event=dict(task_id=gi,family=family,pass_index=pass_index,attempt=attempt,
                               generation_query=goal['query'])
                    r=rng('exam_generation',20261023,gi,family,attempt)
                    raw=synth_listing(family,goal,target['gold']['item'],r,client,8000)
                    if raw is None:
                        append(DATA/'generation_attempts.jsonl',{**event,'status':'listing_parse_failure'})
                        continue
                    # Preserve original official scoring metadata. Only prompt
                    # keywords are repaired; task/query reward fields stay fixed.
                    raw['query']=target['goal']['query']
                    score=judge_plausible(raw,goal,client,8000)
                    if score<4 or raw['asin'] in used:
                        append(DATA/'generation_attempts.jsonl',{**event,'status':'judge_rejection' if score<4 else 'duplicate_asin','score':score})
                        continue
                    reviews=attach_reviews(raw,goal,r,client,8000,n=20 if family=='reviews' else 6)
                    if len(reviews)!=(20 if family=='reviews' else 6):
                        append(DATA/'generation_attempts.jsonl',{**event,'status':'review_count_incomplete','review_count':len(reviews)})
                        continue
                    raw.update(reviews=reviews,judge_score=score)
                    accepted[key]=dict(task_id=gi,family=family,listing=raw,generation_query=goal['query'])
                    used.add(raw['asin'])
                    append(DATA/'generation_attempts.jsonl',{**event,'status':'accepted','score':score,'asin':raw['asin']})
                    checkpoint(gi,family)
                    print('GENERATION_ACCEPTED',gi,family,len(accepted),'/300',flush=True)
                    break
                if key not in accepted:
                    append(DATA/'generation_attempts.jsonl',dict(task_id=gi,family=family,
                        pass_index=pass_index,status='deferred_missing_type',attempts=attempts_per_pass))
                    print('GENERATION_DEFERRED',gi,family,'continuing other cells',flush=True)
            if all((gi,f) in accepted for f in FAMILIES):
                print('EXAM_TASK_COMPLETE',gi,'complete_tasks',sum(all((t['task_id'],f) in accepted for f in FAMILIES) for t in targets),flush=True)
        checkpoint()
        missing=[k for k in expected if k not in accepted]
        print('GENERATION_PASS_COMPLETE',pass_index,'accepted',len(accepted),'missing',len(missing),flush=True)
        if not missing:
            break
    if missing:
        write(DATA/'generation_unresolved.json',dict(missing=[dict(task_id=k[0],family=k[1]) for k in missing],
            passes=passes,attempts_per_cell=passes*attempts_per_pass))
        raise RuntimeError(f'{len(missing)} task/type cells still missing; all other accepted candidates preserved')
    return [accepted[k] for k in expected]
