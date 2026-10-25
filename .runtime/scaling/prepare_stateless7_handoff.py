"""Read-only freeze verification and routing metadata; run only as a CPU job."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from protocol_v3.common import OUT,validate,read,write,file_sha,digest
from stateless7_handoff import CONTROL,OLD_JOB,OLD_ELEMENT

parser=argparse.ArgumentParser()
parser.add_argument('--controller',type=int,required=True)
parser.add_argument('--new-gpu-job',type=int,required=True)
parser.add_argument('--tests',type=int,required=True)
args=parser.parse_args()
manifest=validate()
assert not (OUT/'worker7').exists()
assert not (OUT/'worker1/COMPLETE.json').exists()
tests=ROOT/f'.runtime/slurm/v3-lane7-tests-{args.tests}.log'
test_text=tests.read_text()
assert 'Ran 5 tests' in test_text and '\nOK\n' in test_text and 'FAILED' not in test_text
job=subprocess.run(['scontrol','show','job','150299','-o'],text=True,capture_output=True,check=True).stdout
dependency=re.search(r'\bDependency=(\S+)',job).group(1)
required=[str(args.controller),str(args.new_gpu_job),'150038','150292','150294','150298']
for identifier in required:
    assert re.search(r'[: ,]'+identifier+r'(?=[_(: ,]|$)',dependency),(identifier,dependency)
array0=subprocess.run(['scontrol','show','job','150037_0','-o'],text=True,capture_output=True,check=True).stdout
array0_actual=re.search(r'\bJobId=(\d+)',array0).group(1)
assert '150037_0' in dependency or re.search(r'[: ,]'+array0_actual+r'(?=[(: ,]|$)',dependency)
assert not re.search(r'[: ,]150037(?=[(: ,]|$)',dependency) and OLD_ELEMENT not in dependency
for identifier in (args.controller,args.new_gpu_job):
    state=subprocess.run(['scontrol','show','job',str(identifier),'-o'],text=True,capture_output=True,check=True).stdout
    assert 'JobState=PENDING' in state and 'Reason=JobHeldUser' in state,state
files=['stateless7_handoff.py','stateless7_control.sbatch','stateless7_new.sbatch','test_stateless7_handoff.py','prepare_stateless7_handoff.py']
sources={'.runtime/scaling/'+name:file_sha(ROOT/'.runtime/scaling'/name) for name in files}
record=dict(controller_job=args.controller,new_gpu_job=args.new_gpu_job,old_job=OLD_JOB,old_element=OLD_ELEMENT,
    new_lane=7,current_lane=1,analysis_job=150299,analysis_dependency=dependency,analysis_dependency_updated=True,
    frozen_manifest_sha256=digest(manifest),source_sha256=sources,tests_job=args.tests,tests_sha256=file_sha(tests),
    original_batch_sha256=file_sha(CONTROL/'original_batch.sbatch'),maximum_total_gpu=12,additional_gpu=1,
    unchanged_model_and_experiment_inputs=True,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
write(CONTROL/'manifest.json',record)
print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)
