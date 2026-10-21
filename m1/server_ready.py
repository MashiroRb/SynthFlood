"""Portable local model readiness probe; avoid curl/git dependencies on GPU nodes."""
import json
import sys
import urllib.request
from pathlib import Path

try:
    with urllib.request.urlopen(sys.argv[1],timeout=2) as response:
        payload=response.read()
    data=json.loads(payload)
    if not any(model.get('id')=='Qwen/Qwen2.5-7B-Instruct' for model in data.get('data',[])):
        raise ValueError('wrong served model')
    Path(sys.argv[2]).write_bytes(payload)
except Exception:
    sys.exit(1)
