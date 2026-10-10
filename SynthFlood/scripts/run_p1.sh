#!/bin/bash
# P1 forced-choice susceptibility probe (300 pairs).
set -e
cd ~/synthflood/code
python3 -m synthflood.probe_p1 --n-tasks 30 --pairs 10 --port 8000
