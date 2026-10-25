# Completed protocol v3 archive (2026-10-25)

The authoritative run is `data/protocol_v3_20261024_relaxed_v1` and
`results_protocol_v3_20261024_relaxed_v1`. Earlier examfix/preflight directories
are historical evidence and must not be pooled with the completed run.

The run contains **189,480 unique formal records**: main 7,840, probe 980,
single-type 9,600, clone 10,500, defense 58,800, shopping 960 and exam 100,800.
There are 188,681 valid formal records and 799 excluded records. Logical reuse
is explicit: 161,373 evaluations are new, with 592 final failures to purchase
(0.3669%). Missing confidence remains missing; its rate among valid new
purchases is 1.1991%. All eight washout seeds (2030–2037) completed.

## Results to read first

- [All condition summaries](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/all_condition_summary.csv)
- [Paired effects and uncertainty](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/paired_comparisons.csv)
- [Every formal record](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/all_formal_records.csv)
- [Washout seed/group summaries](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/washout_seed_group_summary.csv)
- [All washout checkpoints](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/washout_all_checkpoints.csv)
- [Strict backend pairing coverage](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/exports/washout_pair_coverage.csv)
- [Frozen statistical output](../results_protocol_v3_20261024_relaxed_v1/analysis_scaled/summary.json)
- [Completion and final audit evidence](../.runtime/v3_manual_checks/MONITORING_COMPLETE.json)

CSV exports reproduce the frozen analysis; no estimator, price, confidence or
purchase outcome was changed for publication. The original Markdown report is
retained verbatim; its unescaped `|` condition names affect table rendering, so
use the CSVs when reading cells. Repeated seeds, rotations, exam families and
checkpoints stay within the task cluster. They are not independent samples.

## Archive layout and restoration

Original formal JSONLs, hardware/backend provenance, checkpoints, complete
observation/lesson memories, frozen inputs, plots and CSVs are retained.
Files exceeding GitHub's 100 MiB limit (the two merged exam JSONLs) are supplied
as additional gzip archives; the originals on the cluster were not edited.
Absolute analysis-worker symlinks are omitted from Git and recreated as
portable relative links. They refer to the original worker records, without
duplicating those records.

The user explicitly authorized uploading the **complete original request logs**
to this same GitHub repository, including prompts, product pages and model
interaction text. They are supplied as 83 lossless bundles under
`results_protocol_v3_20261024_relaxed_v1/request_archives/*.tar.zst`, containing
161,581 original files. This includes preflight and recovery evidence; it is
not an additional count of independent evaluations or formal records.

The bundles retain every original gzip file byte-for-byte, without
decompression/recompression. `members.jsonl` records original paths, byte sizes
and SHA256; `COMPLETE.json` lists bundle hashes and the member-manifest hash.
`VERIFIED.json` records the completed archive/restoration checks. Original
request files on the cluster remain unchanged. Credentials, model weights and
virtual environments are excluded.

From the repository root, restore the merged analysis files and relative links:

```sh
sbatch --partition=cpu,rtx,a800,pro6000 publication_v3/restore.sbatch
```

To also restore and verify all archived original request logs:

```sh
sbatch --partition=cpu,rtx,a800,pro6000 publication_v3/restore.sbatch --requests
```

Restoring the published analysis needs Python 3; optional request-bundle
restoration also needs the `zstd` executable. Restoration verifies SHA256 and
refuses to replace a different existing file. No model or API is invoked.
`publication_v3/files.jsonl` records the SHA256 and size of archived ordinary
files, excluding this manifest itself and the request bundles' own manifests.
The Slurm scripts use one CPU and 8 GiB. On a non-cluster machine the equivalent
command is `python3 publication_v3/restore.py [--requests]`.

## Source and continuation provenance

`protocol_v3/` is the unchanged frozen experiment implementation. Its manifest
digest is `71f201084a8a9b5091ed4eaae5dd1db168e754ab0d5f26cf70c2e1e2c1609800`.
The exact source snapshot, continuation scripts and final audit/export helpers
are selectively archived under `.runtime/` at their original relative paths;
virtual environments, model weights, full official catalog caches and
credentials are excluded. `.runtime/scaling/` records exclusive seed ownership,
request-prefix replay and preservation checks. These are historical execution
records, not instructions to resubmit completed inference jobs.

The two affected RTX services completed after user-authorized 24 GiB host-RAM
continuations, without rerunning completed cases. The 24 GiB migrations retained
the immediately preceding GPU identities/backend and all saved memories.
An **earlier** recovery changed one physical 4090 for seed 2033: its early
M0/B0 strict same-backend pairing is absent/reduced. This limitation remains in
the coverage CSV and original backend hashes; it was not repaired by relabeling.

Current exam synthetic prices equal the gold price. The proposed 75–95% discount
revision was **not implemented**. B0 starts without pre-exposure shopping, so
M0/B0 contrasts alone cannot isolate pollution from general prior experience.
The final audit found no unresolved log/design errors, and all experiment
allocations were released. Full historical execution notes remain in
`V3_RUN_STATUS_2026-10-23.md` and `.runtime/v3_manual_checks/DECISIONS.md`.
