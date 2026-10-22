"""Stream historical vLLM request logs on a CPU allocation."""
import json
import re
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/'results_m1_washout40'
result=[]
for seed in range(2030,2038):
    ids=set();received=ok=bad=0;errors=[]
    for line in (BASE/f'seed{seed}/server.log').open():
        match=re.search(r'Received request (chatcmpl-[a-f0-9]+):',line)
        if match:
            ids.add(match[1]);received+=1
        if '"POST /v1/chat/completions HTTP/1.1"' in line:
            if ' 200 OK' in line: ok+=1
            else: bad+=1
        if line.startswith('ERROR') or 'Traceback (most recent call last)' in line:
            errors.append(line[:300].strip())
    row=dict(seed=seed,received_requests=received,unique_request_ids=len(ids),http_200=ok,http_non200=bad,error_lines=errors)
    result.append(row)
    print(json.dumps(row),flush=True)
Path(__file__).with_name('server_audit.json').write_text(json.dumps(result,indent=2)+'\n')
