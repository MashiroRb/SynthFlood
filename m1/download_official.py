"""Download the released WebShop inputs on a Slurm CPU node, with resume."""
import argparse
import json
import os
import urllib.request
import fcntl
from pathlib import Path

FILES = ("items_shuffle.json", "items_ins_v2.json", "items_human_ins.json")
BASE = os.environ.get("WEBSHOP_DOWNLOAD_BASE", "https://hf-mirror.com/datasets/YWZBrandon/webshop-data/resolve/main/")


def download(name, output):
    final = output / name
    if final.exists():
        print("exists", name, final.stat().st_size, flush=True)
        return
    part = output / (name + ".partial")
    offset = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(BASE + name, headers={"Range": f"bytes={offset}-"} if offset else {})
    with urllib.request.urlopen(req, timeout=30) as response:
        resume = offset and response.status == 206
        with part.open("ab" if resume else "wb") as target:
            total = offset if resume else 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
                total += len(chunk)
                if total % (256 * 1024 * 1024) < 1024 * 1024:
                    print(name, total, "bytes", flush=True)
        if total == 0:
            raise RuntimeError(f"empty download: {name}")
    os.replace(part, final)
    print("downloaded", name, total, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".download.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for name in FILES:
            download(name, args.output)
        (args.output / "sources.json").write_text(json.dumps({name: BASE + name for name in FILES}, indent=2))
