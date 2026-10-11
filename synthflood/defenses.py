"""Defenses compared in P5.

- none        : no preprocessing
- prompt      : agent system prompt gains skepticism instructions (in agent_react)
- detector_text    : perplexity-style statistical detector, drop flagged items
- detector_struct  : structural (SlopShape-inspired) features, drop flagged items
- random      : drop a uniformly random subset of the same expected size
- provenance  : rerank by a noisy provenance-availability signal (models the
                real-world incompleteness of C2PA/Content-Signal style signals)
- oracle      : perfect provenance (synthetics sink to bottom); upper bound

Detector defenses only see page TEXT; provenance only sees the noisy
availability bit; only oracle sees ground truth. Thresholds are calibrated to
a fixed false-positive rate on real items.
"""
import hashlib
import math
import re

SUPERLATIVES = re.compile(
    r"\b(best|perfect|premium|ultimate|top[- ]rated|world[- ]class|"
    r"unbeatable|revolutionary|game[- ]changing)\b", re.IGNORECASE)
MARKETING = re.compile(
    r"\b(elevate|experience|craftsmanship|curated|seamless|effortless|"
    r"elevate your|designed for you)\b", re.IGNORECASE)


def structural_score(item, reviews):
    """Higher = more machine-optimized-looking. Lightweight SlopShape-style
    features computable from text alone."""
    f = item
    text = " ".join([str(f.get("Title", "")),
                     " ".join(f.get("BulletPoints") or []),
                     str(f.get("Description", ""))])
    words = max(1, len(text.split()))
    sup = len(SUPERLATIVES.findall(text)) / words * 100
    mkt = len(MARKETING.findall(text)) / words * 100
    bullets = f.get("BulletPoints") or []
    lens = [len(str(b).split()) for b in bullets]
    uni = 0.0
    if len(lens) >= 3:
        mu = sum(lens) / len(lens)
        var = sum((x - mu) ** 2 for x in lens) / len(lens)
        uni = math.exp(-var / max(1.0, mu))
    specs = f.get("Attributes") or []
    spec_complete = min(1.0, len([s for s in specs if ":" in str(s)]) / 5.0)
    revs = reviews or []
    div = 0.0
    if revs:
        toks = set(" ".join(r["text"] for r in revs).lower().split())
        div = len(toks) / max(1, sum(len(r["text"].split()) for r in revs))
    em = text.count("—") / words * 100
    score = (0.35 * sup + 0.20 * mkt + 0.25 * uni + 0.20 * spec_complete
             - 1.5 * div + 0.05 * em)
    return score


def perplexity(page_text, client):
    """Mean per-token logprob under the scoring model via vLLM completions
    with echo + logprobs. Returns (perplexity, mean_logprob)."""
    import json
    import urllib.request
    url = client.url.rsplit("/chat/completions", 1)[0] + "/completions"
    payload = {"model": client.model, "prompt": page_text[:6000],
               "max_tokens": 1, "echo": True, "logprobs": 0,
               "temperature": 0}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read().decode())
    lp = out["choices"][0]["logprobs"]["token_logprobs"]
    lp = [x for x in lp if x is not None][1:]
    if not lp:
        return float("inf"), 0.0
    mean_lp = sum(lp) / len(lp)
    return math.exp(-mean_lp), mean_lp


def provenance_ok(item_key, synthetic, seed=0):
    """Noisy provenance-availability bit. Deterministic per item.
    Real items carry verifiable provenance 85% of the time; synthetic items
    only 15% (models real-world incompleteness in both directions)."""
    h = hashlib.sha1(f"{seed}:{item_key}".encode()).hexdigest()
    u = int(h[:8], 16) / 0xFFFFFFFF
    return u < (0.15 if synthetic else 0.85)


def apply_defense(defense, candidates, goal, drop_rate=0.3,
                  struct_thresh=0.55, perplexity_fn=None, ppl_thresh=15.0,
                  ppr_lambda=1.0):
    if defense in ("none", "prompt"):
        return candidates
    if defense == "oracle":
        reals = [c for c in candidates if not c.get("synthetic")]
        synths = [c for c in candidates if c.get("synthetic")]
        for c in reals:
            c["prov_badge"] = True
        return reals + synths
    if defense == "provenance":
        reals = [c for c in candidates if c.get("prov_ok", True)]
        rest = [c for c in candidates if not c.get("prov_ok", True)]
        for c in reals:
            c["prov_badge"] = True
        return reals + rest
    if defense == "ppr":
        # Provenance-Prior Re-ranking (soft version of `provenance`):
        # sort candidates by perceived utility u = rating + lambda*1[prov_ok],
        # stable within equal utility (original order kept as tie-break).
        # Verified items also get the badge, so the ONLY difference vs the
        # `provenance` arm is soft re-ranking instead of a hard partition;
        # lambda -> large approaches the provenance behaviour.
        def _util(c):
            it = c.get("item") or {}
            try:
                r = float(it.get("rating") or 0.0)
            except (TypeError, ValueError):
                r = 0.0
            return r + ppr_lambda * (1.0 if c.get("prov_ok", True) else 0.0)
        ranked = sorted(enumerate(candidates),
                        key=lambda t: (-_util(t[1]), t[0]))
        ranked = [c for _, c in ranked]
        for c in ranked:
            if c.get("prov_ok", True):
                c["prov_badge"] = True
        return ranked
    if defense == "reviewtrust":
        # Naive social-proof baseline: re-rank by rating * log(num_reviews+1).
        # No provenance information is used; this is the policy a platform
        # would adopt if it trusted popularity signals blindly. Expected to
        # AMPLIFY the reviews-family attack (synthetic review volume).
        import math as _m
        def _rt(c):
            it = c.get("item") or {}
            try:
                r = float(it.get("rating") or 0.0)
            except (TypeError, ValueError):
                r = 0.0
            try:
                n = float(it.get("num_reviews") or 0.0)
            except (TypeError, ValueError):
                n = 0.0
            return r * _m.log1p(max(n, 0.0))
        ranked = sorted(enumerate(candidates), key=lambda t: (-_rt(t[1]), t[0]))
        return [c for _, c in ranked]
    if defense == "random":
        import random as _r
        rng = _r.Random(goal.get("asin", 0))
        idx = list(range(1, len(candidates)))  # never drop the top slot? no:
        keep = [c for i, c in enumerate(candidates)
                if i == 0 or rng.random() > drop_rate]
        if len(keep) < 2:
            keep = candidates[:2]
        return keep
    if defense == "detector_struct":
        scored = [(c, structural_score(c["item"], c.get("reviews")))
                  for c in candidates]
        keep = [c for c, s in scored if s < struct_thresh]
        if len(keep) < 2:
            keep = [c for c, _ in sorted(scored, key=lambda x: x[1])[:2]]
        return keep
    if defense == "detector_text":
        assert perplexity_fn is not None
        keep = []
        for c in candidates:
            text = _page_text(c)
            ppl, _ = perplexity_fn(text)
            if ppl < ppl_thresh:
                keep.append(c)
        if len(keep) < 2:
            keep = candidates[:2]
        return keep
    raise ValueError(defense)


def _page_text(c):
    """Text seen by the perplexity detector. MUST match the calibration
    field set (title + bullets + attributes); including long free-text
    descriptions inflates real-product perplexity and inverts the filter."""
    f = c["item"]
    return " ".join([str(f.get("Title", "")),
                     " ".join(f.get("BulletPoints") or []),
                     " ".join(str(a) for a in (f.get("Attributes") or []))])