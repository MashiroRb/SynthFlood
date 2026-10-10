"""JSONL run logger: full trajectory per run, plus a compact summary line."""
import json
import os
import time


class RunLogger:
    def __init__(self, path: str, meta: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.meta = meta
        self.steps = []
        self.t0 = time.time()

    def step(self, kind: str, payload: dict):
        self.steps.append({
            "t": round(time.time() - self.t0, 2),
            "kind": kind,
            **payload,
        })

    def finish(self, summary: dict):
        rec = {
            "meta": self.meta,
            "steps": self.steps,
            "summary": summary,
            "wall_sec": round(time.time() - self.t0, 2),
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return summary


def append_summary(csv_path: str, row: dict, fields: list):
    """Append one CSV line (header created on first write)."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    header_needed = not os.path.exists(csv_path)
    with open(csv_path, "a") as f:
        if header_needed:
            f.write(",".join(fields) + "\n")
        f.write(",".join(str(row.get(k, "")) for k in fields) + "\n")