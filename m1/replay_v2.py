"""Repeat identical frozen exam inputs and historical endpoint memories."""
import csv
import json
import os
from pathlib import Path

from m1_run import OUT, PARITY_IDX, init_ctx, run_exams
from audit_figure6 import REPO, RUNS, context, index, paired


def run():
    target = Path(OUT)
    target.mkdir(parents=True, exist_ok=True)
    if (target / "m1_exams.csv").exists():
        raise RuntimeError("Diagnostic results already exist; preserve them.")
    ctx = init_ctx()
    # Historical-memory diagnosis retains the full reconstructed 38-pair
    # instrument. Main trajectories use the separate ASIN-disjoint subset.
    ctx['parity_clones']=ctx['diagnostic_parity_clones']
    memories = {"EMPTY": ""}
    for seed, (folder, _) in RUNS.items():
        for arm in ("M0", "B0"):
            memories[f"{seed}_{arm}"] = context(REPO / folder / f"snapshot_{arm}_wash_end.json")
    for label, memory in memories.items():
        for repeat in range(3):
            run_exams(ctx, label, "parity", repeat, PARITY_IDX, ctx["parity_clones"], memory)
    # A crossed intervention on seed1's final notes and final lesson, without
    # modifying the released snapshots or generating any new memory text.
    seed1={arm:json.loads((REPO/'results_m1'/f'snapshot_{arm}_wash_end.json').read_text())['entries'][-3:]
           for arm in ('M0','B0')}
    hybrids={}
    for observations,lesson in [('M0','B0'),('B0','M0')]:
        entries=[entry for entry in seed1[observations] if entry['type']!='lesson']
        entries += [entry for entry in seed1[lesson] if entry['type']=='lesson']
        memory='Your experience notes from earlier shopping sessions:\n'+'\n'.join(f"- [{entry['type']}] {entry['text']}" for entry in entries)
        label=f'seed1_notes{observations}_lesson{lesson}'
        hybrids[label]=memory
        run_exams(ctx,label,'parity',0,PARITY_IDX,ctx['parity_clones'],memory)
    rows = list(csv.DictReader((target / "m1_exams.csv").open()))
    summary = {"protocol": "v2 instrument, historical memories; not historical input reproduction",
               "repeats": {}, "same_text_s2b": memories["seed2b_M0"] == memories["seed2b_B0"]}
    summary['seed1_crossed_memory_intervention']={label:{'rate':sum(index(rows,label,'parity',0).values())/len(ctx['parity_clones']),
        'injected_context':memory,'measurement_repeats':1} for label,memory in hybrids.items()}
    for label in memories:
        summary["repeats"][label] = {str(i): paired(index(rows,label,"parity",0),index(rows,label,"parity",i)) for i in (1,2)}
    summary["s2b_identical_text_comparison"] = paired(index(rows,"seed2b_M0","parity",0), index(rows,"seed2b_B0","parity",0))
    unstable = any(result["flips"] for group in summary["repeats"].values() for result in group.values())
    unstable |= bool(summary["s2b_identical_text_comparison"]["flips"])
    groups={}
    for row in rows:
        outcome=(row['chosen_kind'],row['chose_clone'],row['reward'],row['purchased'])
        groups.setdefault(row['input_sha256'],set()).add(outcome)
    summary['distinct_actual_inputs']=len(groups)
    summary['unstable_input_hashes']=[key for key,outcomes in groups.items() if len(outcomes)>1]
    unstable |= bool(summary['unstable_input_hashes'])
    summary["stable"] = not unstable
    (target / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if unstable:
        raise RuntimeError("Identical model inputs are not stable: main experiment blocked; inspect archived requests.")
    print("DIAGNOSTIC_STABLE", flush=True)


if __name__ == "__main__":
    run()
