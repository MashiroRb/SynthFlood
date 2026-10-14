# M1 实验日志：内化 vs 情境性诱导

本日志同步于三处：lab 机 `~/synthflood_repo/m1/`、GitHub 仓库 `m1/`、本地项目。
每次追加后由 m1_finalize.sh 提交推送。

## 2026-10-14 — 环境重建（lab 机再次重置）

- 开工检查发现 lab 机被再次重置：家目录全空（vLLM、仓库、数据、PAT 全部丢失），
  GPU 硬件完好（nvidia-smi 正常，1 MiB 占用 = 无进程）。
- 执行 provision_m1.sh 全量重配：apt（python3.10-dev/build-essential）、
  pip（vllm==0.31.0、huggingface_hub<2.0、hf_transfer、spacy+en_core_web_sm、
  prettytable）、princeton-nlp/WebShop 克隆、官方数据三件套
  （items_shuffle.json 5.48GB / items_ins_v2.json 186MB / items_human_ins.json
  5.1MB，HF 镜像 YWZBrandon/webshop-data，Xet 高速通道秒级完成）、
  SynthFlood 仓库克隆（HEAD=15be3cf，与远程一致）、harness 软链布局
  （~/synthflood → ~/synthflood_repo/synthflood，数据符号链接就位）。
- 补丁：huggingface-cli 在 hub 2.x 下不存在 → 改用 snapshot_download 下载
  Qwen2.5-7B-Instruct；补装 thefuzz/rapidfuzz（select_env 依赖）。
- 本次实验代码（m1/）与 agent_react.py 的 sys_extra 兼容性补丁（默认参数，
  不影响既有调用）在上传后提交推送。

## 预注册

判定标准与全部设计细节见 PRE_REG_M1.md（跑数前写定，含 Holm 校正族、
半衰期定义、泄漏防护、种子表）。

## 实验执行

（待补：prep、smoke、full 的逐段记录）

## 结果与判定

（待补：m1_summary.json 摘录 + 对照第 7 节判定分支的结论，措辞遵循
【符合预期】【反转预期】【无显著差异】精确判定语）
