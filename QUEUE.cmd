#!/bin/bash
# rerun struct-stealth arm with correct defense name (detector-struct)
cd /root/synthflood/code
mv -f /root/synthflood/results/p4m_struct_st_sweep.csv /root/synthflood/archive/ 2>/dev/null
python3 -m synthflood.run_sweep --stage P4M_STRUCT_ST --n-tasks 40 --eps 0.75 \
  --family mix --seed 1 --defense detector-struct \
  --pool /root/synthflood/data/contamination/pool_stealth.json --workers 32
sed -i 's/for ARM in P4M_NONE_ST:none P4M_STRUCT_ST:struct P4M_PROV_ST:provenance/for ARM in P4M_NONE_ST:none P4M_STRUCT_ST:detector-struct P4M_PROV_ST:provenance/' scripts/run_fix5.sh
