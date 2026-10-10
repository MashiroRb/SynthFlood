# SynthFlood

Measuring how ambient synthetic (AI-generated) content floods degrade agentic
decision-making on the Web, and whether provenance-weighted retrieval mitigates it.

Submission target: The ACM Web Conference 2027 (WWW '27), Brave New Ideas track.

## Layout

- `synthflood/` core library (env adapters, agent loop, contamination, probes, metrics)
- `scripts/` experiment drivers (P0 pipeline check, P1 forced-choice probe, P2/P4 dose-response, P5 defenses)
- `results/` aggregated CSVs and figures
- `logs/` experiment logs (also mirrored here from the compute node)

## Gated validation protocol

Each stage verifies one assumption and gates the next (go/no-go criteria in
`docs/gates.md`):

1. **P0** pipeline sanity (clean accuracy in published range, reproducible)
2. **P1** forced-choice susceptibility probe (do agents prefer GEO-styled synthetic listings?)
3. **P2** dose-response signal (epsilon in {0, .25, .75})
4. **P3** power analysis -> final matrix
5. **P4** compressed main sweep
6. **P5** defense mini-trial (detectors vs provenance weighting vs oracle)

## Compute

All experiments run locally: 2x RTX 4090 (24 GB), vLLM OpenAI-compatible servers,
open-weight models only (Qwen2.5-7B-Instruct, Meta-Llama-3.1-8B-Instruct), zero API cost.
