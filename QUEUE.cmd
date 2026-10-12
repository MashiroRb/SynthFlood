#!/bin/bash
cd /root/synthflood/code
mv -f /root/synthflood/results/p4m_struct_st_sweep.csv /root/synthflood/archive/p4m_struct_st_hyphen.csv 2>/dev/null
python3 -m synthflood.run_sweep --stage P4M_STRUCT_ST --n-tasks 40 --eps 0.75 \
  --family mix --seed 1 --defense detector_struct \
  --pool /root/synthflood/data/contamination/pool_stealth.json --workers 32
