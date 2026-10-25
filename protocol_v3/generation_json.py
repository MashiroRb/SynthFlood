"""Escape unescaped internal string quotes, preserving generated text values."""
import json
import re

from synthflood.contaminate import _extract_json as original_extract
from .common import DATA, append, digest


def repaired_source(source):
    output=[]
    inside=False
    escaped=False
    changed=False
    for i,char in enumerate(source):
        if not inside:
            output.append(char)
            if char=='"':
                inside=True
            continue
        if escaped:
            output.append(char);escaped=False;continue
        if char=='\\':
            output.append(char);escaped=True;continue
        if char!='"':
            output.append(char);continue
        following=source[i+1:].lstrip()
        # A genuine JSON string terminator precedes a delimiter or EOF.
        # Other quotes (e.g. 8x10"), or plain "premium" text) are literal
        # content and require escaping. Existing escapes are never altered.
        if not following or following[0] in ':,]}':
            output.append(char);inside=False
        else:
            output.append('\\"');changed=True
    return ''.join(output) if changed else None


def extract_json(text, log=True):
    original=original_extract(text)
    if original is not None:
        return original
    match=re.search(r'\{.*\}',text or '',re.S)
    if not match:
        return None
    source=match[0]
    repaired=repaired_source(source)
    if repaired is None:
        return None
    try:
        result=json.loads(repaired)
    except (ValueError,TypeError):
        return None
    if not isinstance(result,dict):
        return None
    if log:
        append(DATA/'generation_json_repairs.jsonl',dict(policy='escape_internal_double_quotes_only',
            original_sha256=digest(source),repaired_sha256=digest(repaired),original=source,repaired=repaired))
    return result
