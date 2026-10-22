"""Read-only inventory of recorded experiments linked to PDF figures."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
groups = {
    'Fig3c_Fig4_Table1': ['p4a_sweep.csv', 'p4e_sweep.csv'],
    'Fig8_Table3': [f'p4b_{f}_sweep.csv' for f in ('geo', 'clone', 'reviews')],
    'Fig3d_Fig7_Table2': ['p2_sweep.csv', 'p4a_sweep.csv'] + [f'p4c_{f}_sweep.csv' for f in ('prompt','detector_text','detector_struct','provenance','oracle','random')],
    'Fig5a': [f'p4h_ppr_l{v}_sweep.csv' for v in ('0.5','1.0','2.0','4.0','6.0','8.0')],
    'Fig5b': [f'p4i_spoof{v}_sweep.csv' for v in (25,35,50,65)] + ['p4c_provenance_sweep.csv'],
    'Fig5c': [f'p4m_{v}_st_sweep.csv' for v in ('none','struct','prov')],
    'Fig6b': ['p4a_sweep.csv','p4j_prov_s2_n100_sweep.csv','p4j_struct_s2_n100_sweep.csv']
        + [f'p4h_ppr_l{v}_n100_sweep.csv' for v in ('0.5','1.0','2.0')]
        + [f'p4i_spoof{v}_n100_sweep.csv' for v in (25,50)]
        + ['p4k_revtrust_n100_sweep.csv'] + [f'p4c_{v}_n100_sweep.csv' for v in ('oracle','text','random')],
    'Text_Backbone': ['p4d_llama_sweep.csv','p4f_3b_sweep.csv','p4f_1b5_sweep.csv'],
}
records = {}
for name in sorted({name for names in groups.values() for name in names}):
    path = ROOT / 'results_csv' / name
    if not path.exists():
        raise ValueError(f'Missing paper result: {name}')
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    cells = collections.Counter((r['eps'],r['cseed'],r['defense']) for r in rows)
    records[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': len(rows),
        'cells': [{'eps': e,'seed': s,'defense': d,'rows': n} for (e,s,d),n in sorted(cells.items())]}
pdf = ROOT.parent / 'sigconf.pdf'
result = {'pdf': str(pdf), 'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
    'figure_groups': groups, 'result_files': records, 'new_model_calls': 0,
    'scope': 'PDF captions and source path inventory; not certification of identical historical model inputs'}
out = ROOT / 'audit_dose_positions/paper_inventory.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print('PAPER_INVENTORY_COMPLETE',len(records),'result files')
