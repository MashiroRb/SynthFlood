"""Replay actual candidate assembly with labelled stand-ins, without inference.

The extracted build_task body is executed unchanged. Only catalog loading and
distractor sampling are replaced by fixed fixtures, isolating the slot logic.
"""
import ast
import copy
import csv
import hashlib
import itertools
import json
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit_dose_positions'
DOSES = (0, .1, .25, .5, .75)


def node(source, name):
    return next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)


def identity(candidate):
    return candidate['item']['asin']


def run():
    source = (ROOT / 'synthflood/select_env.py').read_text()
    old = subprocess.check_output(['git', 'show', 'e102c95:synthflood/select_env.py'], cwd=ROOT, text=True)
    same_body = ast.dump(node(source, 'build_task')) == ast.dump(node(old, 'build_task'))
    assert same_body, 'Historical and current assembler differ; audit versions separately'
    base_items = [{'asin': f'D{i}', 'Title': f'real{i}'} for i in range(1, 20)]
    namespace = {'random': random,
        'get_official_data': lambda: (None, None, {'G': 1, **{p['asin']: 1 for p in base_items}}, None),
        'sample_distractors': lambda goal, by_asin, k, seed: copy.deepcopy(base_items[:k])}
    exec(compile(ast.Module(body=[node(source, 'build_task')], type_ignores=[]), 'actual_build_task', 'exec'), namespace)
    build = namespace['build_task']
    synthetics = [{'asin': f'S{i}', 'family': 'clone', 'synthetic': True,
        'kind': 'synthetic:clone', 'price_float': 1, 'item': {'asin': f'S{i}'}} for i in range(1, 10)]
    cases = []
    tests = []
    for seed in (1, 2):
        layouts = {}
        for eps in DOSES:
            candidates, info = build({'asin': 'G'}, {'G': {'asin': 'G'}}, eps, synthetics, seed)
            ids = [identity(c) for c in candidates]
            layouts[eps] = ids
            k = int(eps * 9)
            expected_base = ['G'] + [f'D{i}' for i in range(1, 10)]
            moved = [{'id': item, 'from': expected_base.index(item) + 1, 'to': pos}
                for pos, item in enumerate(ids, 1) if item.startswith('D') and pos != expected_base.index(item) + 1]
            unexpected = [pos for pos, (a, b) in enumerate(zip(expected_base, ids), 1)
                if pos not in info['synth_positions'] and a != b]
            intended_retained = [expected_base[pos - 1] for pos in range(2, 11) if pos not in info['synth_positions']]
            actual_retained = [x for x in ids if x.startswith('D')]
            cases.append({'seed': seed, 'eps': eps, 'n_synth': k, 'layout': ids,
                'synthetic_positions': info['synth_positions'], 'moved_surviving_reals': moved,
                'unreplaced_slots_changed': unexpected, 'intended_retained': intended_retained,
                'actual_retained': actual_retained,
                'retained_identity_set_matches_in_place_replacement': set(intended_retained) == set(actual_retained)})
            assert ids[0] == 'G' and len(ids) == 10
        for low, high in zip((.25, .5), (.5, .75)):
            a, b = layouts[low], layouts[high]
            common = [x for x in a if x.startswith('S') and x in b]
            tests.append({'seed': seed, 'low': low, 'high': high,
                'synthetic_slots_nested': {i for i, x in enumerate(a) if x.startswith('S')} <= {i for i, x in enumerate(b) if x.startswith('S')},
                'common_synthetics_moved': [{'id': x, 'from': a.index(x) + 1, 'to': b.index(x) + 1} for x in common if a.index(x) != b.index(x)]})
    # Reference design invariants; this is NOT a patch to the live assembler.
    reference_checks = 0
    for seed in range(100):
        clean = ['G'] + [f'D{i}' for i in range(1, 10)]
        slot_order = random.Random(seed).sample(list(range(1, 10)), 9)
        previous = None
        for k in range(10):
            fixed = list(clean)
            for j, slot in enumerate(slot_order[:k]):
                fixed[slot] = f'S{j + 1}'
            assert sum(a != b for a, b in zip(clean, fixed)) == k
            assert all(fixed[i] == clean[i] for i in range(10) if i not in slot_order[:k])
            if previous:
                assert all(fixed[i] == x for i, x in enumerate(previous) if x.startswith('S'))
            previous = fixed
            reference_checks += 1
    inventories = []
    for name in ('p4a_sweep.csv', 'p2_sweep.csv', 'p4e_sweep.csv', 'p4g_sham_sweep.csv'):
        with (ROOT / 'results_csv' / name).open() as stream:
            rows = list(csv.DictReader(stream))
        inventories.append({'file': name, 'rows': len(rows), 'seeds': sorted({r['cseed'] for r in rows}),
            'doses': sorted({float(r['eps']) for r in rows}), 'tasks': len({r['task_id'] for r in rows})})
    logs = []
    for stage in ('P4A', 'P2', 'P4E'):
        path = ROOT / f'logs/{stage}/{stage}__0__e0.00__mix__none.jsonl'
        if path.exists():
            record = json.loads(path.read_text())
            logs.append({'stage': stage, 'sample_log': str(path.relative_to(ROOT)),
                'step_kinds': sorted({s['kind'] for s in record['steps']}),
                'has_recorded_input_steps': any(s['kind'] == 'input' for s in record['steps'])})
    result = {'scope': 'Exact assembly-body reproduction with fixed labelled stand-ins; not model reruns or recovered historical full prompts',
        'historical_commit': 'e102c95dc7c050bcecf12cafe3dfbed952e470fd',
        'current_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'historical_current_build_task_AST_identical': same_body,
        'assembler_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'cases': cases, 'cross_dose_synthetic_mapping': tests, 'reference_invariant_checks': reference_checks,
        'recorded_result_inventory': inventories, 'historical_log_samples': logs,
        'new_model_calls': 0, 'production_source_modified': False}
    OUT.mkdir(exist_ok=True)
    (OUT / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 剂量实验候选位置审计', '',
        '确认存在位置配对错误。历史e102c95与当前d6f6336的build_task函数AST一致；本次没有修改生产代码，没有模型调用。',
        '下面直接执行原函数体，仅将数据加载和真实干扰抽样替换为固定标签G/D1…D9，提供可复核的最小反例，不冒充历史完整提示词重建。', '',
        '## seed1：实际布局', '', '|污染水平|合成数量|位置1至10|存活真实商品移动数|未替换槽位变化数|', '|---:|---:|---|---:|---:|']
    for case in cases:
        if case['seed'] == 1:
            lines.append(f"|{case['eps']}|{case['n_synth']}|{' / '.join(case['layout'])}|{len(case['moved_surviving_reals'])}|{len(case['unreplaced_slots_changed'])}|")
    lines += ['', '## 根因与附带问题', '',
        '- select_env.py:339–340抽样替换槽位；367–368在剩余位置依次pop(0)，没有读取原槽位对应的真实商品。真实商品总是留下D1…D(9−k)，不是删除被抽中槽位原有的商品。',
        '- select_env.py:343–366按位置升序消费合成列表。增量污染可能插在更前的槽位，使低剂量已有合成商品也换位置；即便替换槽位集合嵌套，商品到槽位映射仍不固定。',
        '- run_sweep.py:129–130传入同一个args.seed给每个任务，slot抽样不含task_id。因此同seed的位置变动模式跨任务重复，不会因增加任务数自动平均消除。',
        '- run_sweep.py:42–55没有针对none额外洗牌；defenses.py:92–93直接返回。因此问题在主剂量曲线里已经存在，不能归咎于防御重排。',
        '- provenance标记按位置流生成，真实商品移动后也可能拿到不同的标记。防御跨剂量解释同样需要重新检查。', '',
        '## 范围与解释', '',
        '确认的代码路径用于P2/P4A、第二种子P4E、单家族剂量及其他run_sweep实验；具体已存结果见audit.json的清单。',
        '固定剂量下不同防御故意重排，属于防御干预；不能把该设计与跨剂量本应保持的原始布局混为一谈。',
        '此问题不直接波及独立两候选probe_p1或最近40→40购物环境：后者先以eps0构建基表，再在副本指定槽位直接赋值；此前冻结结果不改写。',
        '旧数据仍记录复合干预下的行为差异，但不能单凭它将全部差异唯一归因于增加合成商品数量，或维持“除替换槽位外逐位置相同”的方法描述。影响方向和大小需要模型反事实补跑，当前未测量。',
        '抽查的旧日志仅含llm/conf步骤，未记录完整input，不能从这些日志逐字节恢复所有历史候选。结果CSV也没有完整候选清单。', '',
        '## 修复应满足的规则', '',
        '每个任务/seed先冻结10个商品基表、9槽位的替换优先序和合成商品序列；k个污染时只用S[j]替换priority[j]，其它原位置及商品对象不动。',
        f'本审计参考布局在100个seed×10个k共{reference_checks}个状态验证：只改变k个位置，未替换真实商品逐位置不变，已有合成商品随剂量递增保持原位。参考布局没有接入生产代码。',
        '正式修复需新版本、独立目录与来源manifest；当前select_env.py受既有实验源哈希冻结约束，不能直接覆盖后宣称旧结果来自新实现。',
        '建议先补同任务/文本/后端的固定位置剂量曲线，增加真实商品替换placebo；要估计位置影响，还需固定商品集合仅改变排列的对照。单纯比较新旧整条曲线会同时改变真实商品身份和位置，不能称纯位置效应。', '',
        '## 论文对应描述', '',
        'paper/sections/problem.tex:25–26与method.tex:40–41声称位置固定、仅替换槽位不同，与实现不符。当前不修改论文；应在修正设计并补跑后同步修订方法及相应结论。', '',
        '本次仅本地审计，不推送新增审计文件，不改写任何历史结果。']
    (OUT / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'identical_assembler': same_body, 'reference_checks': reference_checks,
        'seed1_layouts': [c for c in cases if c['seed'] == 1], 'synthetic_movement': tests}, ensure_ascii=False, indent=2))
    print('DOSE_POSITION_AUDIT_COMPLETE', flush=True)


if __name__ == '__main__':
    run()
