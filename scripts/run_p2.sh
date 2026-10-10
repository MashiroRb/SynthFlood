#!/bin/bash
# P2 dose-response signal: 50 tasks x eps {0,.25,.75}, main backbone.
set -e
cd ~/synthflood/code
python3 -m synthflood.run_sweep --stage P2 --n-tasks 50 \
  --eps 0,0.25,0.75 --family mix --seed 1 --port 8000 --workers 32
