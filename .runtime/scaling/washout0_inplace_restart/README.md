# washout0 original-allocation server restart

At2026-10-25 00:30 Beijing, actual cgroup memory reached16843087872/17179869184 bytes, leaving about321MiB. OOM count remained0. To prevent the same host-OOM/NCCL failure seen in washout1, only this server was restarted within its original GPU allocation150049 (exact array element150039_0), preserving both physical3090 GPUs, their order and the exact hardware/backend file.

Tests150929 passed4 protections: exact cancellation target, GPU identity/order, completed byte-prefix preservation and server-tree isolation. Zero-compute Slurm step150931 proved existing-allocation srun works with job150049 and CUDA_VISIBLE_DEVICES0,1. No additional GPU allocation was requested; global count remains9, A8002.

Control150933 retired CPU client150294, acquired the released RESUME.lock, copied17837 completed rows and all old seed memories/lessons/checkpoints to this directory, and retired only the old vLLM server process tree. Original batch/launch shell and its stale stopped client274350 remain to retain the allocation. Do not resume that stale client.

The new GPU service runs as Slurm step150049.1, hosted by srun inside zero-GPU job150933. GPU step code verified original physical GPU UUIDs/order before starting the exact original model-server argv/environment. Frozen experiment code and inputs are unchanged.

Initial control readiness polling omitted proxy bypass. Direct check150941 proved the new service healthy. CPU job150947 paused only the readiness Python PID293954 (start63182446), leaving srun and the GPU step running. TAKEOVER.json records this. The paused controller must NOT be resumed or cancelled while inference is ongoing: its job retains the srun process. Current disk controller code includes the proxy correction for future use; the running paused process uses the earlier code.

Unused held client150932 was cancelled before any output. Sole current writer is zero-GPU client150946 using the unchanged resume_washout.py, seeds2030/2032, original endpoint18049 and exact original backend. It skips completed cases, restores successful request prefixes, reconstructs old observations/lessons and proceeds from the frontier. Once COMPLETE validates both assigned seeds, its batch footer releases exact150039_0 and then150933, and writes this directory's COMPLETE.json. Thus control150933 may eventually be CANCELLED as expected cleanup; final analysis must NOT depend on its success.

Final analysis150299 was held during transition, then dependency150294 replaced by150946. Current dependency afterok150037_0,150038,150292,150478,150775,150946. It has been released back to ordinary dependency waiting.

Verification150956 confirmed exact historical JSONL prefixes, all old memory/lesson/checkpoint contents, unchanged hardware/backend bytes and no duplicate cases. At its early snapshot the client was still skipping old rows; use the subsequent full audit and new appended rows to establish resumed inference. Actual allocation memory had dropped to8526700544 bytes (~7.9GiB), OOM count0. User informed of both recovery and readiness-helper omission.

Full post-restart audit150961 at16:46:51Z confirmed17847 washout0 rows, hence10 genuinely new rows above17837, unchanged frozen inputs, valid confidence/raw requests/full memory and no duplicate cases. All29 current logs were clean. Seed inventory16:46:57Z showed no newly complete unreported seeds. Final analysis has returned to dependency waiting.

No experimental price revision was applied. Proposed75–95% exam-price experiment remains evaluation-only, explicitly not authorized for implementation. No model/reset-card calls were used for monitoring; health checks only accessed local model metadata.
