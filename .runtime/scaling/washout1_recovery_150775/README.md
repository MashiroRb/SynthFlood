# washout1 recovery, 2026-10-24

Manual audit150766 found a NCCL collective timeout at21:44:59 Beijing. Same-node CPU probe150774 confirmed both TP workers were zombies even though /health returned200. Retiring the broken allocation exposed a cgroup OOM event:150039_1.batch OUT_OF_MEMORY,16G request, MaxRSS18854420K. Its old paused client1578603 must never be resumed.

Only client150298 and exact GPU array element150039_1 were cancelled. washout0/150039_0 and every other experiment continued. Final analysis150299 was held first, its dependency150298 replaced by150775, then released after recovery started. Current dependency: afterok150037_0,150038,150292,150294,150478,150775.

CPU job150776 preserved server logs, hardware, launch/handoff records, all18166 completed rows and all seed memories/checkpoints here before restarting. Seed2031 is complete; seed2033 had40 pollution and34 clean shops and5372 exams, ending exam:M0:cp34:clone:90:2033:1. The final five archived requests all belonged to completed cases; no successful response from the interrupted next question needed cross-backend replay.

Recovery150775 runs the unchanged existing recover_gpu.sbatch and launch_extra.sh on2x4090,4CPU16G, and the original seeds2031/2033. All18166 completed cases were verified and skipped, not rerun. CPU verification150786 confirmed exact historical byte prefixes, unchanged old observations/lessons/checkpoints, identical model/precision/context/TP/sampling settings, no duplicate cases, and32 fresh rows reaching cp36.

One physical GPU was replaced by Slurm; old backend d32fbce82e6d810e69658ff32917afdae6722080d5563aea8c3d12188c0c2e72, new f2a286ce1a2ee033684aedaa874ea1f95e11ee2d5b9f8386899f2a9ebdfbca6a. Old rows retain old provenance. Strict frozen pairing includes backend_sha256, so seed2033 checkpoints whose M0 and B0 hardware differ have reduced/zero matching pairs. Do not rewrite backend hashes or silently broaden pairing. Report this limitation in final analysis; pooled descriptive cells retain every valid row. User has been informed.

No frozen source, input, price, budget or memory protocol changed. Proposed75–95% exam-price revision is explicitly NOT authorized and has not been applied. Old full snapshots and current results remain available. Monitoring log coverage now includes v3-recover-150775.log.

Only CPU verification job150779 was cancelled to remove an inefficient repeated index construction; replacement150786 passed. This had no effect on experiments.

Read-only150778 measured washout0 cgroup current15295651840 bytes (~14.2GiB) against16GiB request; paused original client RSS826816KiB. Two A800 jobs MaxRSS about8GB. No signal or configuration change was made to those jobs. Continue manual half-hour checks including memory pressure.
