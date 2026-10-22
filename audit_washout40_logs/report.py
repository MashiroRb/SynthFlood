"""Render the small audit outputs; no experiment data is modified."""
import csv
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
d=json.loads((HERE/'audit.json').read_text())
s=json.loads((HERE/'server_audit.json').read_text())
rows=list(csv.DictReader((HERE/'checkpoints.csv').open()))
text=['# 污染40轮→干净40轮：M0/B0日志审计', '',
'本审计只读取历史数据；未重跑模型、修改历史结果或中断 N98 评分修复实验。大规模读取在 Slurm CPU 节点完成。', '',
'## 原始记录核验', '',
f"- 主考试 CSV 共 {d['expected_main_rows']:,} 条；匹配原始独立轨迹 {d['matched_raw_traces']:,} 条、独立 inode {d['unique_trace_inodes']:,} 个。",
f"- 按实验时间范围及 (arm, checkpoint, pair, input_sha256) 核对记录重数：缺少 {d['missing_traces']}，多出 {d['excess_traces']}。",
f"- 第14–40轮共 {d['cp14_through40_pairs']:,} 对题目；实际首次模型输入一致 {d['identical_actual_first_inputs']:,} 对；完整输入和原始输出轨迹一致 {d['identical_full_input_output_trajectories']:,} 对（忽略时间、延迟及累计usage计数）。",
f"- 主考试轨迹内记录 {d['actual_action_model_calls']:,} 次行动生成调用。",
f"- 异常计数：`{json.dumps(d['errors'],ensure_ascii=False)}`。",
f"- 8个服务日志共 {sum(x['received_requests'] for x in s):,} 次请求；HTTP非200共 {sum(x['http_non200'] for x in s)}，ERROR/Traceback行共 {sum(len(x['error_lines']) for x in s)}。这些请求还包含购物、哨兵、置信度和lesson调用。",
f"- lesson调用 {d['lesson_calls']} 次，独立API响应ID {d['unique_lesson_request_ids']} 个。", '',
'溯源限制：旧轨迹meta没有seed或独立experiment_id。这里以实验时间范围和上述键的重数核对覆盖，不能把共享相同键的每个UUID唯一归属于某个seed。后续应在轨迹记录seed、experiment_id及API请求ID。', '',
'## 为什么第14轮以后完全相同', '',
'`m1/m1_memory.py:70`只将最近3条记忆的类型和文字注入新对话；完整历史及arm标签不进入提示词。`m1/m1_memory.py:123`每次lesson只总结最近5条observation，不递归读旧lesson。', '',
'第12轮的读取窗口是 lesson1009 + observation1010 + observation1011。第14轮变为 observation1011、1012、1013。较早的差异退出读取窗口；之后各seed内部两组的干净经历与可见记忆保持一致。第14轮完整历史仍为M0=64、B0=16条；第40轮仍为96对48条。污染历史保存在磁盘，但未进入这些考试的输入。', '',
'各seed从以下节点开始，在全部后续已测节点中注入文本持续相同：', '',
'| seed | 干净购物轮数 |','|---|---:|']
text += [f'| {seed} | {cp} |' for seed,cp in d['permanent_context_equality'].items()]
text += ['', '第4轮暂时同输入后，第6轮可以再次不同：lesson读取最近5条观察，而考试只读取最后3条记录。此后早期差异退出这两个窗口，才持续一致。因此14不是硬编码的归零节点。', '',
'每题重建对话，temperature=0、请求seed=0；两臂有效输入相同时，本批日志中的输出也一致。源码分别建立两个MemoryStore，分别购物、考试，并生成独立UUID轨迹；未发现跨臂结果缓存或复制分支。汇总按(arm, checkpoint, pair_idx)分别取值。历史代码归档与manifest对照检查，环境渲染以归档版本为准，未混入当前评分修复版本。', '',
'## 重新计算的结果', '',
'| 干净轮数 | M0克隆率 | B0克隆率 | 逐题克隆选择不一致数/3616 |','|---|---:|---:|---:|']
for cp in range(0,41,2):
    r=[x for x in rows if int(x['checkpoint'])==cp]
    text.append(f"| {cp} | {sum(int(x['M0_clone']) for x in r)/3616:.2%} | {sum(int(x['B0_clone']) for x in r)/3616:.2%} | {sum(int(x['choice_differences']) for x in r)} |")
text += ['', '## 结论的边界', '',
'这组数据支持“当前短窗口外部记忆策略下，两组可见状态在干净经历中收敛”。它本身不能证明模型参数中的偏好被学到或洗掉，也不能把停止读取污染历史等同于在持续读取污染记忆的条件下主动纠正偏好。当前架构并未更新模型权重。', '',
'此外，这批历史日志仍含真实商品rating:n/a而克隆有评分的旧元数据缺陷。因此克隆率及早期差异应视为旧输入条件下的结果；当前评分修复不会追溯更改这些记录。这个问题可能影响选择与收敛时点，但不是相同有效输入产生相同输出的解释替代。', '',
'建议论文明确报告last-3读取和last-5总结规则；若研究目标是更持久的记忆效应，应预先设计记忆保留/检索对照，并先修复评分输入，再检验效果。此次审计不擅自改变实验。', '',
'## 轨迹样例（checkpoint14，pair0）', '']
for e in d['evidence'][:6]:
    text.append(f"- {e['arm']}: `{e['path']}`；input={e['input_hash']}；wall_sec={e['wall_sec']}；audit_input={e['audit_input_hash']}。")
(HERE/'REPORT.md').write_text('\n'.join(text)+'\n')
print(HERE/'REPORT.md')
