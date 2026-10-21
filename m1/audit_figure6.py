"""Dependency-free, read-only audit of released M1 data (no model calls)."""
import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = {"seed1": ("results_m1", "contamination"),
        "seed2": ("results_m1_s2", "contamination_s2"),
        "seed2b": ("results_m1_s2b", "contamination_s2b")}


def exact_p(down, up):
    n = down + up
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(down, up) + 1)) / 2**n)


def index(rows, arm, phase, checkpoint):
    selected = [r for r in rows if r["arm"] == arm and r["phase"] == phase
                and int(r["checkpoint"]) == checkpoint]
    out = {int(r["pair_idx"]): int(r["chose_clone"]) for r in selected}
    if len(out) != len(selected):
        raise ValueError(f"duplicate rows: {arm}/{phase}/{checkpoint}")
    return out


def paired(a, b):
    common = sorted(a.keys() & b.keys())
    if a.keys() != b.keys():
        raise ValueError("unmatched pair identities")
    if not common:
        raise ValueError("empty comparison")
    down = sum(a[k] == 1 and b[k] == 0 for k in common)
    up = sum(a[k] == 0 and b[k] == 1 for k in common)
    return {"n": len(common), "a_rate": sum(a.values()) / len(a),
            "b_rate": sum(b.values()) / len(b), "a1_b0": down,
            "a0_b1": up, "flips": down + up, "p_exact": exact_p(down, up)}


def context(path):
    entries = json.loads(path.read_text())["entries"][-3:]
    return ("Your experience notes from earlier shopping sessions:\n" +
            "\n".join(f"- [{e['type']}] {e['text']}" for e in entries)) if entries else ""


def holm(values):
    result, running = {}, 0.0
    for rank, (name, p) in enumerate(sorted(values.items(), key=lambda kv: kv[1])):
        running = max(running, (len(values) - rank) * p)
        result[name] = min(1.0, running)
    return result


def audit(repo):
    output = {"source_commit": "e102c95dc7c050bcecf12cafe3dfbed952e470fd",
              "inference_limit": "Pair-level tests are conditional diagnostics, not inference over independent memory trajectories.",
              "runs": {}, "instrument": {}}
    for name, (folder, gen) in RUNS.items():
        path = repo / folder
        rows = list(csv.DictReader((path / "m1_exams.csv").open()))
        keys = [(r['arm'], r['phase'], r['checkpoint'], r['pair_idx']) for r in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"duplicate cells in {name}")
        data = {"rows": len(rows), "parity": {}, "m2_repeatability": {}, "tests": {}}
        for arm in ("B0", "M0", "M2"):
            data["parity"][arm] = {}
            for checkpoint in (0, 10, 20):
                cell = index(rows, arm, "parity", checkpoint)
                data["parity"][arm][checkpoint] = ({"n": len(cell), "clones": sum(cell.values()),
                    "rate": sum(cell.values()) / len(cell)} if cell else None)
        for phase in ("exam", "parity"):
            base = index(rows, "M2", phase, 0)
            for checkpoint in (10, 20):
                data["m2_repeatability"][f"{phase}:0-{checkpoint}"] = paired(base, index(rows, "M2", phase, checkpoint))
        for checkpoint in (10, 20):
            data["tests"][f"parity_M0_B0@{checkpoint}"] = paired(index(rows, "M0", "parity", checkpoint), index(rows, "B0", "parity", checkpoint))
        data["tests"]["parity_M0:0-20"] = paired(index(rows, "M0", "parity", 0), index(rows, "M0", "parity", 20))
        data["tests"]["parity_M0_M2@0"] = paired(index(rows, "M0", "parity", 0), index(rows, "M2", "parity", 0))
        a = context(path / "snapshot_M0_wash_end.json")
        b = context(path / "snapshot_B0_wash_end.json")
        data["endpoint_injected_memory"] = {"identical": a == b, "M0": a, "B0": b}
        data["memory_exposure_entry_counts_at_end"] = {}
        for arm in ("M0", "B0"):
            entries = json.loads((path / f"snapshot_{arm}_wash_end.json").read_text())["entries"][-3:]
            data["memory_exposure_entry_counts_at_end"][arm] = sum(e["t"] < 1000 for e in entries)
        # Distribution across all 11 no-memory measurements, not just endpoints.
        checkpoints = sorted({int(r["checkpoint"]) for r in rows if r["arm"] == "M2" and r["phase"] == "exam"})
        cells = [index(rows, "M2", "exam", c) for c in checkpoints]
        data["m2_exam_unstable_pairs"] = sum(len({c[k] for c in cells}) > 1 for k in cells[0])
        output["runs"][name] = data
    family = {name: x["tests"]["parity_M0_B0@20"]["p_exact"] for name, x in output["runs"].items()}
    output["endpoint_pair_tests_holm_across_3_runs"] = holm(family)
    s1 = repo / "data/contamination"
    for name, (_, gen) in RUNS.items():
        root = repo / "data" / gen
        data = {"clone_files": {}, "task_instruction_changes_vs_seed1": {}}
        for filename in ("m1_exam_clones.json", "m1_parity_clones.json"):
            raw = (root / filename).read_bytes()
            data["clone_files"][filename] = {"sha256": hashlib.sha256(raw).hexdigest(),
                "byte_identical_to_seed1": raw == (s1 / filename).read_bytes()}
        reference = json.loads((s1 / "goals_m1.json").read_text())
        goals = json.loads((root / "goals_m1.json").read_text())
        for phase, original in reference.items():
            current = goals[phase]
            data["task_instruction_changes_vs_seed1"][phase] = {
                "n": len(original), "asin_changes": sum(a["asin"] != b["asin"] for a, b in zip(original, current)),
                "instruction_changes": sum(a["instruction"] != b["instruction"] for a, b in zip(original, current))}
        data["unverifiable"] = ["Full historical exam instructions and gold listing/price tables were not released.",
            "realattack_pairs.json was not released; original pair ordering cannot be certified.",
            "Actual request payloads, checkpoint 10 memory and backend versions were not released."]
        output["instrument"][name] = data
    pair_path=repo/'data/official/realattack_pairs.json'
    if pair_path.exists():
        pairs=json.loads(pair_path.read_text())
        manifest=json.loads((repo/'results_realattack/ra1_task_manifest.json').read_text())
        order=list(pairs);random.Random(1000).shuffle(order)
        matches=sum((order[r['task_id']]['gold_asin'],order[r['task_id']]['clone_asin'])==(r['gold'],r['clone']) for r in manifest)
        if matches!=len(manifest):
            raise ValueError('Reconstructed RA1 shuffled ordering does not match the released manifest')
        used={(r['gold'],r['clone']) for r in manifest}
        proof={'pool_pairs':len(pairs),'RA1_manifest_matches':matches,'RA1_shuffle_seed':1000,'runs':{}}
        for name,(folder,gen) in RUNS.items():
            rows=list(csv.DictReader((repo/folder/'m1_exams.csv').open()))
            phases={}
            goals=json.loads((repo/'data'/gen/'goals_m1.json').read_text())
            for phase in ('exam','parity'):
                indices=set(index(rows,'M0',phase,0))
                golds={pairs[i]['gold_asin'] for i in indices}
                phases[phase]={'n':len(indices),'unique_gold_asins':len(golds),
                    'reused_RA1_pairs':sum((pairs[i]['gold_asin'],pairs[i]['clone_asin']) in used for i in indices),
                    'exposure_gold_overlap':sorted(golds & {g['asin'] for g in goals['exposure']}),
                    'washout_gold_overlap':sorted(golds & {g['asin'] for g in goals['washout']})}
            proof['runs'][name]=phases
        output['reconstructed_pair_validation']=proof
    return output


def write_report(data, target):
    lines = ["# Figure 6(a) 本地审计", "", "这是历史数据复算，不是新的模型实验。原始 CSV/快照保持原样。", "",
             "| 种子 | M0 平价 0→10→20 | B0 平价 10→20 | M2 平价 0→20 翻转 | M0/B0@20 配对精确 p |", "|---|---|---|---|---|"]
    for name, run in data["runs"].items():
        p = run["parity"]
        rates = lambda arm, cs: " → ".join(f"{p[arm][c]['clones']}/{p[arm][c]['n']}" for c in cs)
        lines.append(f"| {name} | {rates('M0', (0,10,20))} | {rates('B0',(10,20))} | {run['m2_repeatability']['parity:0-20']['flips']}/38 | {run['tests']['parity_M0_B0@20']['p_exact']:.5f} |")
    lines += ["", "证据与解释：", "",
        "- M2 无注入、固定题目与顺序仍发生翻转。温度 0 不等于服务端数值计算完全可重复；未保存原始请求，无法把历史变化唯一归因到某种后端原因。",
        "- seed2b 的两份克隆缓存字节一致，但暴露指令 9/20、洗脱指令 15/20 不同。完整考试指令未归档，因此不能证实考试指令字节一致。",
        "- seed2b 的 M0 与 B0 在 clean20 实际注入的文本完全相同，38 题仍有 3 题选择不同。该差异不可能由注入记忆文本差异解释。",
        "- B0 只有洗脱阶段的 20 集；M0 是 20 集暴露加 20 集洗脱，经验量与历史没有配平。",
        "- 三个种子 clean20 的最后三条注入记忆均无暴露阶段条目。新教训只看最近五条观察，不递归读取旧教训；晚期差异只能经由行为反馈传播或重复测量波动保留。",
        "- 每个种子每个臂只有一条记忆轨迹。38 道题不能代替 38 次独立暴露实验；题目层配对检验和 Wilson 区间均不估计轨迹间不确定性。",
        "- 原分析 McNemar 未按 phase 过滤，作为通用函数可能混入别的考试；现有 PRE 比较的交集仍是打折题，未发现该处已导致数值错误。原分析主要使用独立比例检验，未实现约定的 Holm 校正；此处按 phase 与 pair 显式配对，重复行和不匹配题集直接报错。",
        "- 显著性缺失不能证明恢复或等价。补跑应报告效应及轨迹层区间；预设等价界限后才可讨论“消退到可忽略”。", "",
        "预注册与报告还有三处需要修正：", "",
        "- 原主检验的“部分衰减”分支要求 clean20 仍显著高于 B0；seed1 clean20 为 0.667 对 0.718，明显不满足。实验日志却改用 c0 carryover 与首个阈值交叉点称该分支命中，属于判据偏离。",
        "- 原预注册写明主检验四项做 Holm，但输出分析没有实现。carryover 的原始 p=0.021 以及载体 p=0.025 不能直接当作通过预设校正的结果。这里给出的平价配对 p 也只是条件诊断，不能替代轨迹层检验。",
        "- “半衰期 4 集”实际是相对 B0@20 的首次阈值交叉，不是单调衰减或指数拟合；其后还会回升，且三条近因记忆在第三个干净观察后便已全部换掉，不能把 4 集视为独立验证的长期动力学参数。", "",
        "实现根因（代码级确认）：", "",
        "1. 商品区间价格用未设种子的全局 RNG 抽样；目标 seed 在商品加载之后才设置。旧缓存还会固定某次未知随机价格。",
        "2. generate_pool 使用 Python 随进程变化的 hash(fam)，且没有接收 M1_SEED_BASE。所谓整体平移并未控制池生成。",
        "3. synth_listing 直接打乱 goal['attributes']；浅拷贝没有隔离可变列表，多线程可互相影响。",
        "4. 毫秒命名的日志使用覆盖写，多线程下有日志丢失风险；初始提示、实际输入和中间记忆未保存。",
        "5. M2 的 notes=False 实际不写记忆，与“写但不读”的设计不符。没有买到商品也曾写成已购买常规商品。",
        "6. 线程内部异常不会传回 full()，脚本可能在部分失败时仍打印完成。CSV 首次写入的表头检查位于锁外。",
        "7. 生成器虽然继承金品 options，转换为环境候选时却丢弃 options；这会破坏宣称已控制的官方奖励选项项，需要重新做奖励验尸。",
        "8. 真实商品显示 Price/区间，但奖励使用另外抽样的 price_float；平价克隆因此不保证与金品显示价格一致。v2 统一显示价与评分用价。",
        "9. agent 使用温度 0，但历史教训提炼使用 0.3（默认 seed=0），与全程贪心的简化描述不符。",
        "10. 原 B0/M0 长任务的金品始终在第一个位置；v2 在两臂使用同一个随机排列，避免位置成为稳定提示。", "",
        "修复与新的实验协议见 [PRE_REG_M1_V2.md](../m1/PRE_REG_M1_V2.md)。详情、原始计数、哈希与条件配对检验见 audit.json。"]
    proof=data.get('reconstructed_pair_validation')
    if proof:
        lines += ['', '配对池恢复后的新增核查：', '',
            f"原算法重建 {proof['pool_pairs']} 对；按 Random(1000) 洗牌后，RA1 manifest 的 {proof['RA1_manifest_matches']} 对全部匹配。RA1 实际先洗牌取题，原文用索引段保证未使用的论证错误。"]
        for phase in ('exam','parity'):
            cell=proof['runs']['seed1'][phase]
            lines.append(f"- seed1 {phase} 保留的 {cell['n']} 对中，{cell['reused_RA1_pairs']} 对曾用于 RA1；仅含 {cell['unique_gold_asins']} 个不同金品 ASIN。暴露/洗脱 ASIN 重叠分别为 {len(cell['exposure_gold_overlap'])}/{len(cell['washout_gold_overlap'])}。")
        lines += ['','题目重用本身不等于训练或外部记忆泄漏（各实验未传递权重或记忆），但必须撤回“从未使用”与“仅靠索引即可防泄漏”的说法；多对同金品也削弱题目独立性的假设。']
    target.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--output", type=Path, default=REPO / "audit_m1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = audit(args.repo)
    (args.output / "audit.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    write_report(data, args.output / "REPORT.md")
    print(args.output / "REPORT.md")
