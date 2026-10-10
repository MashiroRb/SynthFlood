#!/bin/bash
# Generate the synthetic contamination pool (runs on GPU1 model).
set -e
cd ~/synthflood/code
python3 -m synthflood.generate_driver --n-tasks 40 --per-task 4 --port 8001
