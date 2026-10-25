import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
directory=root/'.runtime/scaling'
report=dict(reason='Use the exact array element when releasing completed legacy allocation; never its parent array',
    old_shard0_actual_job=150049,old_shard1_release_target='150039_1',
    sources_sha256={name:hashlib.sha256((directory/name).read_bytes()).hexdigest()
        for name in ('resume_washout.py','attach.sbatch','test_resume.py')},
    retained_prior_source_sha256=hashlib.sha256((directory/'resume_washout.before-specific-release.txt').read_bytes()).hexdigest(),
    frozen_protocol_sources_modified=False)
(directory/'release_routing_amendment.json').write_text(json.dumps(report,indent=2)+'\n')
print('EXACT_ARRAY_ELEMENT_RELEASE_GUARD_RECORDED')
