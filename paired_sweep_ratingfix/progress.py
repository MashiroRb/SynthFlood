"""Small read-only status utility; no model or catalog loading."""
import collections
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/paired_n98_ratingfix_v2'
OUT=ROOT/'results_paired_n98_ratingfix_v2'
result={'prepared':(DATA/'manifest.json').exists(),'main_summary':(OUT/'main_summary.json').exists(),
    'defense_released':(OUT/'DEFENSE_READY.json').exists(),'complete':(OUT/'COMPLETE.json').exists(),
    'failed':json.loads((OUT/'FAILED.json').read_text()) if (OUT/'FAILED.json').exists() else None,'workers':{}}
for lane in range(8):
    directory=OUT/f'worker{lane}'
    counts={}
    for phase in ('main','defense'):
        path=directory/f'{phase}.jsonl'
        counts[phase]=sum(1 for _ in path.open()) if path.exists() else 0
    hardware=directory/'hardware.json'
    counts.update(gpu=json.loads(hardware.read_text())['name'] if hardware.exists() else None,
        main_complete=(directory/'MAIN_COMPLETE.json').exists(),complete=(directory/'COMPLETE.json').exists())
    result['workers'][str(lane)]=counts
print(json.dumps(result,ensure_ascii=False))
