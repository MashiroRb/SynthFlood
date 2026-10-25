# Host memory investigation, 2026-10-25 00:59 Beijing

Confirmed failure: old washout1 job150039_1.batch was OUT_OF_MEMORY under its16GiB Slurm host-memory limit, followed by TP-worker loss/NCCL timeout. This is not evidence of CUDA OOM.

Original washout0 allocation150049 showed actual cgroup memory.current rising from15295651840 bytes at21:55 to16843087872 bytes at00:30, under limit17179869184. Rate during that interval was approximately0.56GiB/hour. At21:55 its two vLLM TP workers each reported approximately6.53GiB RssAnon; the stopped original experiment client was approximately0.79GiB RSS. RSS can count shared pages multiple times; the cgroup measurement is used for the actual limit. No old per-process smaps profile is available, so the specific allocating library/function is not established.

Restarting only the inference-server tree inside the same allocation, retaining all experiment memories/results/backend, reduced memory.current to8526700544 bytes by00:43. Original memory_M0 checkpoint was29KiB; current one30KiB, so the saved lesson/observation JSON is not itself multi-GiB. Long prompts may still affect server allocation; that causal contribution has not been isolated.

Read-only zero-GPU Slurm probes150984/150985 at00:58:49:

- washout0 allocation150049: memory.current8679108608 bytes(~8.08GiB), memory.max16GiB, oom_kill0; anon3618992128, file5010948096, kernel39759872 bytes. file includes274415616 bytes shared memory. Active resume client150946 is charged separately:816504832 bytes under8GiB.
- washout1 recovery150775: memory.current6147424256 bytes(~5.73GiB), memory.max16GiB, oom_kill0; anon5738225664, file370216960, kernel36216832 bytes. file includes278953984 bytes shared memory.
- Two current washout0 TP workers report RssAnon about1.30GiB each, versus6.53GiB each before the restart. Approximate status RSS differs from page-table smaps measurements; do not interpret their sum as exact job consumption.

Conclusion:16GiB was sufficient to start, but did not bound long-running inference-service host-memory accumulation. Evidence localizes the major growth to the server workers rather than saved experiment memories or the separate resume client. A persistent object leak versus allocator high-water retention/fragmentation remains unproven. Current file cache also contributes to cgroup usage, so not all memory.current is unreclaimable process memory.

No frozen code/inputs/model settings changed during this investigation. No model generation or reset-card call, new GPU allocation, signal, restart, or experiment cancellation was performed by these diagnostic probes. Continue manual30-minute checks of actual cgroup current/stat/events along with experiment quality/log checks.
