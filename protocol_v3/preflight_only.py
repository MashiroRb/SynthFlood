"""Retry only the execution gate; retain all 100 targets and 300 accepted inputs."""
import collections

from .common import *
from .executor import CheckedClient,tokenizer
from .generate import finalize_preflight
from .prepare import check_candidates


def validate_complete_exam():
    targets=read(DATA/'exam_targets.json')
    expected={t['task_id']:t for t in targets}
    assert len(expected)==100
    assert file_sha(DATA/'exam_targets.json')==read(DATA/'exam_quality_summary.json')['target_sha256']
    query_freeze=read(DATA/'generation_queries_frozen.json')
    assert file_sha(DATA/'generation_queries.json')==query_freeze['mapping_sha256']
    assert file_sha(DATA/'exam_targets.json')==query_freeze['target_sha256']
    exams=read(DATA/'exams.json')
    raw=read(DATA/'exam_generated_original.json')
    lookup={(r['task_id'],r['family']):r for r in raw}
    assert len(exams)==len(raw)==len(lookup)==300
    wanted={(gi,f) for gi in expected for f in FAMILIES}
    assert set(lookup)==wanted
    assert {(q['task_id'],q['family']) for q in exams}==wanted
    synthetic_ids=[]
    for q in exams:
        target=expected[q['task_id']]
        assert q['goal']==target['goal']
        check_candidates(q['candidates'],2,1)
        gold=next(c for c in q['candidates'] if not c['synthetic'])
        generated=next(c for c in q['candidates'] if c['synthetic'])
        assert gold==target['gold']
        assert generated['family']==q['family']
        assert generated['price_float']==gold['price_float']
        listing=lookup[q['task_id'],q['family']]['listing']
        assert generated['item']['asin']==listing['asin']
        assert listing['judge_score']>=4
        assert len(listing['reviews'])==(20 if q['family']=='reviews' else 6)
        synthetic_ids.append(listing['asin'])
    assert len(set(synthetic_ids))==300
    audit=read(DATA/'exam_coverage_audit.json')
    assert audit['validated'] and audit['n_tasks']==100 and audit['n_candidates']==300
    assert audit['by_family']==dict(geo=100,clone=100,reviews=100)
    assert collections.Counter(q['task_id'] for q in exams)=={gi:3 for gi in expected}
    print('REUSE_COMPLETE_EXAM',100,300,'NO_REGENERATION',flush=True)
    return exams


def run():
    if (DATA/'manifest.json').exists():
        raise RuntimeError('Refusing to overwrite formal input freeze')
    initial_sources=source_hashes()
    exams=validate_complete_exam()
    parent=ROOT/'results_protocol_v3_20261023_examfix_v3_r2'/'preflight'
    artifacts={str(p.relative_to(ROOT)):file_sha(p) for p in (
        DATA/'exam_targets.json',DATA/'exam_generated_original.json',DATA/'exams.json',
        DATA/'generation_queries.json',parent/'generation_requests.jsonl.gz',
        parent/'generation_query_audit_requests.jsonl.gz',parent/'smoke.jsonl',
        ROOT/'.runtime/protocol-v3-examfix-v3-r2-source.tar.gz')}
    write(DATA/'preflight_resume.json',dict(parent_output=str(parent.relative_to(ROOT)),
        artifacts_sha256=artifacts,retained_targets=100,retained_synthetic_inputs=300,
        generated_new_inputs=0,formal_result_reuse=False,
        reason='Action-line trailing horizontal whitespace normalization; rerun execution preflight only'))
    tok=tokenizer()
    from synthflood.vllm_client import LLMClient
    checked=CheckedClient(LLMClient(8000,MODEL),tok,OUT/'preflight'/'context_probe_requests.jsonl.gz')
    finalize_preflight(tok,checked,initial_sources,exams)


if __name__=='__main__':
    run()
