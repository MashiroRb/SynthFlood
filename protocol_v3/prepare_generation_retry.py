"""Controlled input-generation resume; keep the100 audited targets unchanged."""
import shutil
from .common import *


def prepare():
    parent=ROOT/'data/protocol_v3_20261023_examfix_v2'
    previous=ROOT/'results_protocol_v3_20261023_examfix_v2/preflight'
    if DATA.exists() or OUT.exists():
        raise RuntimeError('Refusing overwrite of generation-retry version')
    DATA.mkdir(parents=True)
    for path in parent.iterdir():
        if path.suffix in ('.json','.jsonl'):
            shutil.copyfile(path,DATA/path.name)
            assert file_sha(path)==file_sha(DATA/path.name)
    targets=read(DATA/'exam_targets.json')
    quality=read(DATA/'exam_quality_summary.json')
    assert file_sha(DATA/'exam_targets.json')==quality['target_sha256']
    partial=read(DATA/'exam_generated_partial.json')
    shutil.copyfile(DATA/'exam_generated_partial.json',DATA/'generation_parent_accepted.json')
    expected=[(t['task_id'],f) for t in targets for f in FAMILIES]
    actual=[(x['task_id'],x['family']) for x in partial]
    assert len(actual)==len(set(actual)) and set(actual)<=set(expected)
    assert len({x['listing']['asin'] for x in partial})==len(partial)
    assert all(x['listing']['judge_score']>=4 for x in partial)
    assert all(len(x['listing']['reviews'])==(20 if x['family']=='reviews' else 6) for x in partial)
    provenance=OUT/'input_provenance'
    provenance.mkdir(parents=True)
    for name in ('generation_requests.jsonl.gz','target_quality_requests.jsonl.gz','hardware.json','FAILED.json'):
        if (previous/name).exists():
            shutil.copyfile(previous/name,provenance/name)
    ancestors=previous.parent/'input_provenance'
    if ancestors.exists():
        shutil.copytree(ancestors,provenance/'ancestors')
    archive=ROOT/'.runtime/protocol-v3-examfix-v2-source.tar.gz'
    shutil.copyfile(archive,provenance/'parent-code-snapshot.tar.gz')
    write(DATA/'generation_resume.json',dict(parent_directory=str(parent.relative_to(ROOT)),
        parent_output=str(previous.relative_to(ROOT)),accepted_count=len(partial),
        accepted_input_sha256=file_sha(DATA/'exam_generated_partial.json'),
        frozen_target_sha256=quality['target_sha256'],
        parent_request_log_sha256=file_sha(provenance/'generation_requests.jsonl.gz'),
        parent_qa_log_sha256=file_sha(provenance/'ancestors/target_quality_requests.jsonl.gz'),
        parent_code_sha256=file_sha(provenance/'parent-code-snapshot.tar.gz'),
        reason='Audit generation-only query compatibility for all100 fixed tasks; retain original scoring metadata and all accepted source artifacts',
        target_changes=0,purchase_result_reuse=False))
    print('CONTROLLED_GENERATION_RESUME_PREPARED',len(partial),'accepted;100 targets unchanged',flush=True)


if __name__=='__main__':
    prepare()
