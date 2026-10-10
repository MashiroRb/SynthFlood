#!/bin/bash
# P0 pipeline sanity: clean slice, 20 tasks, repeated twice for determinism.
set -e
cd ~/synthflood/code
python3 -m synthflood.p0_sanity --n-tasks 20 --port 8000 --repeat 2 --workers 16
