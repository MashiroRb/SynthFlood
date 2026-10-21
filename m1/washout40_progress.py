"""Read only result CSVs; no catalog/model imports."""
import collections
import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = root / 'data/m1_washout40/manifest.json'
manifest = json.loads(data.read_text()) if data.exists() else {}
progress = {}
for seed in range(2030, 2038):
    directory = root / f'results_m1_washout40/seed{seed}'
    cells = collections.Counter()
    exams = directory / 'm1_exams.csv'
    if exams.exists():
        with exams.open() as stream:
            for row in csv.DictReader(stream):
                cells[f"{row['arm']}:{row['checkpoint']}"] += 1
    episodes = directory / 'm1_episodes.csv'
    n_episodes = max(0, sum(1 for _ in episodes.open()) - 1) if episodes.exists() else 0
    progress[str(seed)] = {'exam_rows': sum(cells.values()), 'clean_episodes': n_episodes,
        'cells': dict(cells), 'complete': (directory / 'COMPLETE.json').exists()}
print(json.dumps({'prepared': bool(manifest), 'checkpoints': manifest.get('checkpoints'),
    'expected_rows_per_seed': manifest.get('new_main_exams_per_seed', 0) + 32 if manifest else None,
    'summary_complete': (root / 'results_m1_washout40/summary.json').exists(), 'seeds': progress}, ensure_ascii=False))
