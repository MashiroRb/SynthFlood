# User-authorized24GiB washout continuation, 2026-10-25

User requested24G host RAM after explaining concern about repeated interruptions. Slurm rejected live MinMemoryNode24576 updates with 'Job is no longer pending execution'; no live memory limit was silently changed. Existing frozen sources and model/input/price settings were not edited.

Current jobs:

- washout0:151018,aias-compute-01,2original3090 UUIDs33900edc... and4511b3c3...,4CPU24GiB. Assigned2030(complete)/2032(incomplete).
- washout1:151012,aias-compute-2,2current4090 UUIDs395ab521... and91d87314...,4CPU24GiB. Assigned2031(complete)/2033(incomplete).
- Both run the exact previous server argv/environment and the unchanged resume_washout.py. Completed cases are validated and skipped; successful request prefixes and all observations/lessons/checkpoints are retained.
- analysis:151032,2CPU16G,post-switch verified and released to ordinary dependency waiting. Dependencies afterok150037_0,150292,150478,151018,151012; scontrol confirms only KillOInInvalidDependent=No, preserving recoverability if an upstream protection ever trips.

Safety tests151008 passed4 protections. Preparation151009/151010 captured server argv and safe execution environment, expected GPU UUIDs/order, hardware byte digest. Cutovers151013/151014 verified held24G replacements and held analysis, paused only the exact client, copied all result JSONLs and all seed memory/checkpoint/lesson JSONs, and verified preserved prefixes after old allocations retired.

Backups and exact byte baselines:

- .runtime/scaling/mem24_washout0:194shopping+17812exam=18006 completed rows. Old CPU150946,exactGPU150039_0(actual150049),and controller150933 retired. The old stopped original client was removed only with its retired GPU allocation.
- .runtime/scaling/mem24_washout1:214shopping+21206exam=21420 completed rows. Old150775 retired.
- Requests remain in their original output archives, used by unchanged prefix replay. No request reset or completed-case restart.

Initial replacement151011 was deliberately blocked by GPU identity validation BEFORE model loading or result writes: because worker5 had just completed, Slurm selected its newly free3090 as part of the replacement pair. This failed attempt is preserved in v3-washout24-151011.log. To recover the original two physical cards, temporary zero-inference placement151019 took only the nonexperiment UUID013d354f..., then151018 received the exact expected pair.151019 exits as soon as washout0 READY.json exists (maximum4minutes), releasing its extraGPU. GPU peak during placement was9, within user12/A8003 limits; steady8/A8002 after worker5 completed.

Held analysis150299 nevertheless had kill-on-invalid-dep=yes and Slurm auto-cancelled it on failed151011 dependency before it ever ran. Initial replacement151020 combined the old script's yes with CLI no, and scontrol showed both flags. Before any analysis ran, it was replaced by151032 using analyze_mem24.sbatch with no conflicting directive, the exact unchanged analyze_scaled.py invocation, and current dependencies. The controller confirms only No. No analysis outputs were lost or produced. This is scheduling cleanup, not a failed model experiment.

Neither24G migration changes hardware.json bytes or backend hash relative to the immediately prior service. The earlier21:55 washout1 migration DID replace a physical GPU, and its seed2033 pairing limitation must still be reported. Do not rewrite provenance or broaden frozen pairing keys.

Monitoring remains assistant-led every30minutes. The temporary placement helper only orchestrates allocation, not experiment-quality monitoring. No reset cards or external model calls were used. Both24G jobs free their model service and allocation after their assigned seeds validate COMPLETE.

Post-switch verification151021/151022 confirmed all old JSONL byte prefixes, all saved observation/lesson prefixes and exact checkpoints, and unchanged hardware bytes. Already4 and51 fresh exam rows respectively were appended at01:18. Actual cgroup limits were asserted inside both GPU allocations at25769803776 bytes. Read-only151027/151028 measured3.689/24GiB and3.943/24GiB at01:19:59, oom0. The full manual audit151023 completed successfully with159k+ unique formal rows,28current logs, no design issues/log errors/failures, no deferred checks, unchanged frozen hashes. New window final failures1/514, memory0/347; missing confidence9/513 overall, memory1/347. Seed inventory01:20:06 still only2030/2031/2034/2035 complete; all already reported, no newly complete full defense seed.

Remaining-time evidence01:20: washout0 seed2032 M0clean34,5228/6300exam,B0notstarted; recent M0~574/h and prior B0~892/h suggest9–11hours remaining(today10–12Beijing). washout1 seed2033 M0complete,B0clean14,2381/6300exam; recent B0~1161/h suggests4–5hours remaining(today05–06Beijing). These estimates include longer later-memory requests, and are not claims of exact finish times. A800150293/150292 at01:22 measured9.740/16GiB and9.889/16GiB,oom0; no changes to them. Next manual full check approximately01:50.
