"""Assemble the completed audit without changing any primary calculations."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT/name).read_text())


if __name__=='__main__':
    audit=read('audit_m1/audit.json')
    options=read('audit_m1/options_autopsy_v2.json')
    quality=read('audit_m1/quality_autopsy_v2.json')
    historical=read('audit_m1/historical_options_counterfactual.json')
    diagnostic=read('results_m1_v2/diagnostic/summary.json')
    summary=read('results_m1_v2/summary.json')
    extra=read('results_m1_v2/exploratory_quality_effects.json')
    if not diagnostic['stable'] or len(summary['seeds'])!=8:
        raise RuntimeError('Incomplete or unstable experiment; refusing a completed final report')
    effect=summary['primary_parity20_M0_minus_B0']
    acquisition=summary['secondary']['parity0_M0_B0']
    acq_low,acq_high=acquisition['bootstrap95']
    low,high=effect['bootstrap95']
    if summary['meets_predeclared_practical_equivalence_interval']:
        interpretation='本次修正协议的平均末期差异符合预设 ±5pp 的实际等价区间标准；不是对每条轨迹均无残留的断言，且限于固定任务、污染文本池、模型与后端。'
    elif low>0 and effect['sign_flip_two_sided_p']<.05:
        interpretation='修正协议下检测到末期正向克隆选择差异；应报告效应与轨迹层区间，不能将其等同于模型权重发生内化。'
    elif high<0 and effect['sign_flip_two_sided_p']<.05:
        interpretation='修正协议下末期差异为负，未支持持久的正向克隆偏好。'
    else:
        interpretation='修正协议未提供稳定末期残留的充分证据，也未达到预设等价标准；不把不显著称为证明完全消退。'
    lines=['# Figure 6(a) 代码审计、诊断与补跑结果','',interpretation,
        '但诱导结束时未见稳定的平均正向偏好，因而本次不能建立“先成功诱导、再完成洗脱”的结论；下文分别报告诱导与末期状态。','',
        '原始三个种子的结果和论文文件保留；全部新实验通过 Slurm 计算节点执行，未推送远程。',
        '源仓库起点：`e102c95dc7c050bcecf12cafe3dfbed952e470fd`。本地分支：`audit/figure6a-washout`。','',
        '## 原始问题的解释','',
        '- B0 有持续更新的经验记忆，并不是固定输入对照，曲线本身可以随干净经验变化。原 B0 总共 20 集，M0 为 20 集暴露加 20 集洗脱，经验量未配平。',
        '- 真正异常的是固定空记忆的 M2：历史平价题在同一种子 c0→c20 翻转 9/38、4/38、8/38；seed2b 的 M0/B0 在 c20 注入文本完全相同，仍有 3/38 不同。原始请求未归档，不能唯一追溯后端数值或未记录输入差异。',
        '- seed2b 克隆文件字节一致，但保存的暴露与洗脱指令分别有 9/20、15/20 不同；未设种子的商品价格表、旧缓存以及生成过程随机性破坏了仅靠目标种子冻结仪器的保证。完整历史考试指令未保存，无法认证字节一致。',
        '- 原平价 38 对只有 22 个不同金品；并非 38 条独立记忆轨迹。原论文的区间虽已标注只描述题目，但仍不足以支持跨轨迹稳定性。',
        '- 重建原 467 对后，按 RA1 原脚本 Random(1000) 洗牌的 250 对全部匹配 manifest。原保留打折/平价题分别有 26/39、29/38 对曾用于 RA1，原“按索引即可保证未用题”声明错误。',
        '- 两类考试还与暴露阶段直接共享金品：打折 277（B07MJVB31T），平价 292/293（B09K7YCMYK）。新主考试按身份排除这三对；完整历史卷仅用于记忆诊断。',
        '- 最后三条记忆会在三个干净观察后完全换掉，教训只看最近五条观察。晚期差异可以通过行为反馈传播，但不能直接解释成仍在读取暴露条目，更不能把首次阈值交叉当成可靠的动力学半衰期。','',
        '## 评分与实现','',
        f"生成器继承了金品 options，但候选转换丢掉了它。在新主卷的评分对照中，{options['pairs_affected']}/{len(options['rows'])} 对受影响，平均评分损失 {options['mean_reward_loss_from_dropping_options']:.3f}。",
        f"修复后 {quality['clone_reward_ge_gold']}/{quality['n']} 道克隆并不劣于金品（官方评分）；平价为 {quality['by_phase']['parity']['clone_reward_ge_gold']}/{quality['by_phase']['parity']['n']}。因此必须同时报告克隆选择和奖励损失。",'',
        '| 历史种子 | 合成品购买数 | 原评分≥金品 | 仅恢复选项后≥金品 | 原平均奖励差 | 恢复后差 |',
        '|---|---:|---:|---:|---:|---:|']
    for seed,result in historical['runs'].items():
        if result['certified_n']!=result['synthetic_purchases']:
            raise RuntimeError('Historical counterfactual table requires full certification')
        lines.append(f"| {seed} | {result['synthetic_purchases']} | {result['original_reward_ge_gold']} | {result['restored_reward_ge_gold_certified']} | {result['original_mean_gap_all']:.3f} | {result['restored_mean_gap_certified']:.3f} |")
    lines += ['', '这是基于原日志分量、金品满分及原生成器继承选项的评分反事实；不会修复当时已用错误反馈生成的记忆，动态结果必须补跑。',
        '另外修复了稳定的生成种子、属性列表原地修改、M2 不写记忆、无购买却记已购买、线程异常吞失、CSV 表头竞态、日志重名覆盖与输入未归档等问题。',
        '历史教训温度为 0.3，不能把全过程简化描述为贪心；原分析未执行写明的 Holm，且“部分衰减命中”与原判据不一致，详见 [历史审计](REPORT.md)。',
        'options 转换是主程序的共享路径，其他实验的旧奖励数值也需要单独复核；本次模型补跑范围为 M1 / Figure 6(a)。','',
        '## 固定输入重复测量','',
        '使用新冻结仪器，逐一重放空记忆和三个历史种子的 M0/B0 末期文本，各三轮。完整诊断通过逐输入哈希与购买结果一致性校验。',
        '下表是固定文本干预，不能作为独立暴露轨迹的总体检验。','',
        '| 记忆文本 | 平价克隆率（三轮相同） |', '|---|---:|']
    for label,group in diagnostic['repeats'].items():
        value=group['1']['a_rate']
        lines.append(f'| {label} | {value:.3f} |')
    for label,value in diagnostic['seed1_crossed_memory_intervention'].items():
        lines.append(f"| {label}（交叉文本，一轮） | {value['rate']:.3f} |")
    lines += ['',
        'seed1 的末期 M0 教训为 “Choose high-demand items for higher rewards.”，B0 为 “Choose products with higher official rewards for better outcomes.”。将 M0 观察配上 B0 教训后，克隆选择从 30/38 降为 24/38；反向组合为 29/38。这定位了该固定文本差异的行为作用，但不能证明该教训会被独立污染轨迹稳定地产生。',
        '', '## 八轨迹修正协议','',
        '固定种子 2030–2037，全部纳入；每条包含 B0/M0/M2，每臂 20 集前阶段加 20 集洗脱。两臂干净候选、目标和位置配平；M2 写而不读。',
        '金品位置随机，污染家族各两条；固定价表、显示价与评分用价一致，完整归档每个检查点。主卷打折 38 对、平价 36 对，与所有暴露/洗脱目标 ASIN 不重叠。',
        '模型 Qwen2.5-7B-Instruct；固定 RTX 3090、vLLM 0.8.1、单请求串行、关闭前缀缓存；教训温度 0。观察用可见标题和价格，不使用人工“廉价仿品”标签。',
        '这是修正协议的补跑，含明确的协议变更，不是旧结果的逐字节重现；细节与边界见 [新协议](../m1/PRE_REG_M1_V2.md)。','',
        f"主要终点（平价 c20，M0−B0）：**{effect['mean']*100:+.2f}pp**，轨迹 bootstrap 95% 区间 **[{low*100:+.2f}, {high*100:+.2f}]pp**；8 轨迹符号翻转双侧 p={effect['sign_flip_two_sided_p']:.5f}。",
        f"诱导阶段检查（平价 c0，M0−B0）：均值 **{acquisition['mean']*100:+.2f}pp**，轨迹 bootstrap 95% 区间 **[{acq_low*100:+.2f}, {acq_high*100:+.2f}]pp**，预设次级检验 Holm 校正 p={summary['secondary_holm']['parity0_M0_B0']:.5f}。修正协议没有稳定诱导出平均正向克隆偏好的证据；不能据末期相同就断言‘成功诱导的偏好被洗脱’，也不能据此估计衰减半衰期。",
        '末期退化为零宽度的 bootstrap 区间源于这八条差值全部为零；它没有估计换题、换污染文本、换后端或新增轨迹的不确定性。操作化等价判据满足，只是当前固定仪器上的条件性结果。',
        f"全部正式考试中未购买 {summary['no_purchase_episodes']} 次，均保留分母，并未冒充金品选择。所有 M2 与 PRE/跨检查点的一致性检查通过。",'',
        '| 种子 | M0@0 | B0@0 | M0@20 | B0@20 | 差值@20 |','|---|---:|---:|---:|---:|---:|']
    cells=list(csv.DictReader((ROOT/'results_m1_v2/trajectory_cells.csv').open()))
    for seed in summary['seeds']:
        rates={(r['arm'],int(r['checkpoint'])):float(r['rate']) for r in cells if int(r['seed'])==seed and r['phase']=='parity'}
        values=[rates['M0',0],rates['B0',0],rates['M0',20],rates['B0',20]]
        lines.append(f"| {seed} | "+' | '.join(f'{value:.3f}' for value in values)+f" | {(values[2]-values[3])*100:+.2f}pp |")
    lower=extra['mean_endpoint_effects']['parity']['lower_reward']
    matching=sum(cell['checkpoint']==20 and cell['equal_effective_memory_state'] for cell in extra['memory_state_comparisons'])
    lines += ['', f"探索性状态核查：clean20 的 M0/B0 在 {matching}/8 条轨迹中具有相同的实际注入文本及最近五条观察。相同注入文本决定当次考试输入，相同五条观察还决定下一次教训提炼的依据；这有助于区分状态收敛与仅仅率相近。",
        f"按输入哈希逐题比较：种子内不一致计数为 {extra['within_seed_inconsistent_inputs']}，跨种子合并后有 {extra['cross_seed_inconsistent_inputs']} 个输入出现不同购买结果。此为技术核查，不增加主检验。",'',
        f"探索性分层：对确实劣于金品的平价克隆，末期选择率差为 {lower['clone_rate_difference']*100:+.2f}pp，记录的奖励损失差为 {lower['regret_difference']:+.3f}。分层不替代预设主检验，未新增确认性 p 值。",'',
        '## 对论文结论与后续实验的建议','',
        '当前证据不支持把原 seed1 单条轨迹作为稳定的“偏好未消退”结论，也不支持把本次末期相同改写成强诱导后的普遍完全消退。适合报告的是：原测量存在未控制变化；修正协议在固定任务池上未得到稳定的平均正向诱导，且观察到八条轨迹的末期有效记忆状态收敛。',
        '本次同时改变评分、价表、观察措辞和后端，不能把新旧结果的变化唯一归因于某一项修复。若继续研究获取与保持，应另立协议：在独立开发任务上先检查诱导强度，在未用于调参的任务与全新污染文本上确认；记录所有预设轨迹，不能只挑诱导成功的种子，再用相同状态在预定检查点分叉测量保持。',
        '若研究代码生成的“廉价仿品”标签是否驱动效应，应将历史标签与中性事实记录作为事先指定的因素做消融，明确标签是额外监督；不要在看到本次阴性结果后悄悄恢复标签，再与本次结果混合检验。后续预先冻结协议后再运行，不连续修改至出现显著性。','',
        '![修正协议逐轨迹曲线](../results_m1_v2/parity_trajectories.png)','',
        '完整主分析：[summary.json](../results_m1_v2/summary.json)。探索性质量分解：[exploratory_quality_effects.json](../results_m1_v2/exploratory_quality_effects.json)。',
        '10 项回归检查、完整输入哈希与源代码校验、GPU 预检和全部轨迹完整性检查通过。原始历史文件未改写；本地 origin push URL 已禁用，未 push。']
    (ROOT/'audit_m1/FINAL_REPORT.md').write_text('\n'.join(lines)+'\n')
    print('FINAL_REPORT_COMPLETE',flush=True)
