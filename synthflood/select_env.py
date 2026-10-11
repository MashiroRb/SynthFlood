"""WebShop-Select: controlled candidate-selection environment built on
official WebShop data and the official reward function (goal.get_reward).

Design:
- Each task = one official human instruction (goal) + a fixed candidate list
  (gold product + N-1 same-category distractors, fixed order across eps).
- At contamination level eps, floor(eps*(N-1)) distractor slots are replaced
  by synthetic listings (gold is never replaced); the replaced slots and the
  synthetic items are chosen by a fixed seed so the same task can be compared
  paired across eps levels.
- Agent protocol (text): view[k] opens candidate k's full page; select[k]
  buys candidate k and ends the episode.
- Reward: official get_reward. Because our protocol has no option-selection
  step, once a listing is chosen we score the BEST variant of that listing
  against each goal option (the shopper picks the right variant after picking
  the right product). Reward differences between candidates then come purely
  from WHICH listing was chosen - the manipulated variable.
"""
import os
import random
import sys

from thefuzz import fuzz

from .config import DATA_DIR
from .ws_loader import load_official_data

WEBSHOP_REPO = os.path.join(os.environ.get("SYNTHFLOOD_ROOT",
                                           os.path.expanduser("~/synthflood")),
                            "webshop_repo")
if os.path.isdir(WEBSHOP_REPO):
    if WEBSHOP_REPO not in sys.path:
        sys.path.insert(0, WEBSHOP_REPO)

_CACHE = {}


def get_official_data():
    """(all_products, product_item_dict, product_prices, attribute_to_asins)"""
    if "data" not in _CACHE:
        _CACHE["data"] = load_official_data(DATA_DIR)
    return _CACHE["data"]


def load_products():
    """by_asin dict of official merged products."""
    _, item_dict, _, _ = get_official_data()
    return item_dict


def build_goals(n_tasks=0, seed=2027):
    """Official goals via the official goal builder (human instructions).

    Frozen task lists from GEN_DIR are preferred when they cover n_tasks:
    the official get_human_goals samples price uppers through the global
    RNG, so any webshop_repo drift silently shifts instruction text (observed:
    task 36 price_upper 70.00 -> 60.00 on a fresh clone). Freezing keeps the
    environment bit-identical across sessions and machines."""
    from .config import GEN_DIR
    import json as _json
    frozen = None
    for name in ("goals100.json", "goals.json"):
        path = os.path.join(GEN_DIR, name)
        if os.path.exists(path):
            with open(path) as f:
                cand = _json.load(f)
            if len(cand) >= n_tasks:
                if frozen is None or len(cand) < len(frozen):
                    frozen = cand
    if frozen is not None:
        return frozen[:n_tasks] if n_tasks else frozen
    import random as _r
    from web_agent_site.engine.goal import get_human_goals  # official semantics
    all_products, _, product_prices, _ = get_official_data()
    _r.seed(seed)  # official get_human_goals samples price uppers via global random
    goals = get_human_goals(all_products, product_prices)
    rng = random.Random(seed)
    rng.shuffle(goals)
    seen, uniq = set(), []
    for g in goals:
        if g["asin"] in seen:
            continue
        seen.add(g["asin"])
        uniq.append(g)
        if n_tasks and len(uniq) >= n_tasks:
            break
    return uniq


def product_fields(p):
    """Normalize field access across merged items."""
    title = p.get("Title") or p.get("name") or ""
    bullets = p.get("BulletPoints") or p.get("bullet_points") or []
    if isinstance(bullets, str):
        bullets = [bullets]
    desc = p.get("Description") or ""
    attrs = p.get("Attributes") or []
    cat = p.get("product_category") or p.get("category") or ""
    brand = p.get("Brand") or p.get("brand") or ""
    rating = p.get("Rating")
    if rating in (None, "N.A."):
        rating = p.get("star5_ratios") or p.get("rating") or ""
    if rating in (None, ""):
        rating = "n/a"
    nrev = p.get("num_reviews") or p.get("review_num") or ""
    if nrev in (None, ""):
        nrev = 0
    price = p.get("Price") or p.get("price") or ""
    if isinstance(price, (int, float)):
        price = f"${float(price):.2f}"
    return dict(title=title, bullets=bullets, desc=desc, attrs=attrs,
                cat=cat, brand=brand, rating=rating, nrev=nrev, price=price)


def results_page(cands):
    lines = ["[Search Results]"]
    for i, c in enumerate(cands, 1):
        f = product_fields(c["item"])
        rating = f["rating"]
        if isinstance(rating, float):
            rating = f"{rating:.1f}"
        badge = " [verified]" if c.get("prov_badge") else ""
        lines.append(
            f"[{i}]{badge} {f['title']} | {f['price']} | rating: {rating} "
            f"({f['nrev']} reviews) | {f['brand']}")
    lines.append("\nUse view[k] to inspect a product page, select[k] to buy.")
    return "\n".join(lines)


def _fmt_review(r):
    """Format one review robustly across storage shapes (incl. double-encoded
    dict-repr text produced by the generator)."""
    if isinstance(r, str):
        r = {"text": r}
    if isinstance(r, dict):
        stars = r.get("stars", r.get("rating", ""))
        text = r.get("text", r.get("review", ""))
        for _ in range(3):
            if isinstance(text, str) and text.strip().startswith("{"):
                try:
                    import ast
                    d = ast.literal_eval(text)
                    if isinstance(d, dict):
                        text = d.get("review", d.get("text", text))
                        continue
                except Exception:
                    pass
            break
        return f"- ({stars}*) {str(text)[:220]}"
    return "- " + str(r)[:220]


def item_page(c):
    f = product_fields(c["item"])
    badge = " [verified]" if c.get("prov_badge") else ""
    parts = [f"Title: {f['title']}{badge}", f"Price: {f['price']}",
             f"Rating: {f['rating']} ({f['nrev']} reviews)",
             f"Brand: {f['brand']}", f"Category: {f['cat']}"]
    if f["attrs"]:
        parts.append("Attributes: " + "; ".join(f["attrs"]))
    if f["bullets"]:
        parts.append("Features:")
        parts += [f"- {b}" for b in f["bullets"][:6]]
    if f["desc"]:
        d = f["desc"].replace("\n", " ")
        parts.append("Description: " + d[:1500])
    if c.get("reviews"):
        parts.append("Top reviews:")
        parts += [_fmt_review(r) for r in c["reviews"][:8]]
    if c.get("meta_line"):
        parts.append(c["meta_line"])
    return "\n".join(parts)


def best_variant_options(item, goal):
    """Map each goal option to the item's best-matching value of that option
    type (the shopper picks the right variant after choosing the listing).

    Human goals carry goal_options as a list of 'name: value' strings (the
    official get_reward already handles both formats; we mirror that here).
    """
    item_opts = item.get("options") or {}
    go = goal.get("goal_options") or []
    if isinstance(go, dict):
        pairs = [(str(k).lower(), str(v)) for k, v in go.items()]
    else:
        pairs = []
        for entry in go:
            s = str(entry)
            if ":" in s:
                name, _val = s.split(":", 1)
                pairs.append((name.strip().lower(), s.strip()))
            else:
                pairs.append((s.strip().lower(), s.strip()))
    all_vals = [v for vals in item_opts.values() for v in vals]
    chosen = {}
    for name, target in pairs:
        pool = item_opts.get(name, []) or all_vals
        best, best_s = "", -1.0
        for v in pool:
            s = fuzz.token_set_ratio(v, target)
            if s > best_s:
                best, best_s = v, s
        if best_s >= 0:
            chosen[target] = best
    return chosen


class SelectEnv:
    def __init__(self, goal, candidates, n_candidates=10):
        self.goal = goal
        self.candidates = candidates[:n_candidates]
        self.n = len(self.candidates)
        self._synth_positions = []
        self.reset()

    def reset(self):
        self.viewing = None
        self.done = False
        self.chosen = None
        return self.render()

    def render(self):
        if self.viewing is None:
            return results_page(self.candidates)
        return item_page(self.candidates[self.viewing - 1])

    def step(self, action):
        obs, done, info = "", False, {}
        a = action.strip().lower()
        if a.startswith("view["):
            try:
                k = int(a[5:].split("]")[0])
                assert 1 <= k <= self.n
            except Exception:
                obs = "Invalid action. Use view[k] or select[k]."
                return obs, False, info
            self.viewing = k
            obs = item_page(self.candidates[k - 1])
        elif a.startswith("select["):
            try:
                k = int(a[7:].split("]")[0])
                assert 1 <= k <= self.n
            except Exception:
                obs = "Invalid action. Use view[k] or select[k]."
                return obs, False, info
            self.chosen = self.candidates[k - 1]
            self.done = True
            done = True
            obs = "Purchase complete."
        else:
            obs = ("Invalid action. Use view[k] to inspect, "
                   "or select[k] to buy.")
        return obs, done, info

    def reward(self):
        """Official WebShop reward for the chosen item vs the goal."""
        from web_agent_site.engine.goal import get_reward
        if self.chosen is None:
            return 0.0, {}
        c = self.chosen
        f = product_fields(c["item"])
        prod = {
            "asin": c["item"].get("asin", ""),
            "query": c["item"].get("query", self.goal["query"]),
            "product_category": c["item"].get("product_category", ""),
            "name": f["title"],
            "Title": f["title"],
            "Attributes": f["attrs"],
            "BulletPoints": f["bullets"],
            "Description": f["desc"],
        }
        price = c.get("price_float")
        if price is None:
            price = 0.0
        options = best_variant_options(c["item"], self.goal)
        try:
            r, info = get_reward(prod, self.goal, price, options, verbose=True)
        except Exception:
            r, info = 0.0, {}
        return r, info


def sample_distractors(goal, by_asin, k, seed):
    """Plausible distractors, never the gold asin. Prefer the same fine-grained
    product_category so competing candidates earn graded (non-zero) official
    rewards; fall back to the coarser category only if the fine pool is short."""
    rng = random.Random(seed)
    fine = goal["product_category"]
    coarse = goal["category"]
    pool = [p for p in by_asin.values()
            if p.get("product_category") == fine and p["asin"] != goal["asin"]]
    if len(pool) < k:
        extra = [p for p in by_asin.values()
                 if p.get("category") == coarse
                 and p.get("product_category") != fine
                 and p["asin"] != goal["asin"]]
        rng.shuffle(extra)
        pool += extra
    rng.shuffle(pool)
    return pool[:k]


def build_task(goal, by_asin, eps, synth_pool, seed, n_candidates=10,
               sham=False, spoof_rate=0.15):
    """Fixed base candidate list; replace floor(eps*(n-1)) distractor slots
    with synthetic listings. Returns ordered candidate list + bookkeeping.

    sham=True (real-swap placebo arm): replaced slots receive additional
    REAL listings instead of synthetics, drawn from the same distribution
    as the base distractors (sample_distractors prefix property keeps the
    base candidates identical to the original arm, so the two arms differ
    only in what fills the replaced slots: synthetic vs real listings).
    spoof_rate overrides the synthetic-side provenance presence probability
    (spoofing attack: synthetics fake a verifiable provenance record)."""
    _, _, product_prices, _ = get_official_data()
    n_synth = int(eps * (n_candidates - 1)) if eps < 1 else int(eps)
    rng = random.Random(seed)
    n_fill = n_synth if sham else 0
    distractors = sample_distractors(goal, by_asin,
                                     (n_candidates - 1) + n_fill, seed=seed)
    if sham:
        shams = distractors[n_candidates - 1:]
        distractors = distractors[:n_candidates - 1]
    else:
        shams = []
    slots = list(range(1, n_candidates))  # candidate indices 2..10 (1-based)
    replace = rng.sample(slots, n_synth) if n_synth else []
    synths = synth_pool[:n_synth]
    candidates, synth_positions = [], []
    si = 0
    for idx in range(n_candidates):
        pos = idx + 1
        if pos == 1:
            c = {"item": by_asin[goal["asin"]], "kind": "gold",
                 "synthetic": False}
            c["price_float"] = product_prices.get(goal["asin"], 100.0)
            candidates.append(c)
        elif pos - 1 in replace:
            if sham:
                d = shams[si]
                c = {"item": d, "kind": "real", "synthetic": False}
                c["price_float"] = product_prices.get(d["asin"], 100.0)
                candidates.append(c)
                synth_positions.append(pos)
                si += 1
                continue
            cand = dict(synths[si])
            cand["kind"] = f"synthetic:{synths[si].get('family', '?')}"
            cand["synthetic"] = True
            cand.setdefault("price_float", 0.0)
            candidates.append(cand)
            synth_positions.append(pos)
            si += 1
        else:
            d = distractors.pop(0)
            c = {"item": d, "kind": "real", "synthetic": False}
            c["price_float"] = product_prices.get(d["asin"], 100.0)
            candidates.append(c)
    # noisy provenance-availability signal (for the provenance defense):
    # real items carry verifiable provenance 85% of the time, synthetic
    # items only `spoof_rate` (15% by default; raised under spoofing).
    # The defense sees ONLY this bit, never the label.
    pv = random.Random(seed * 7919 + 13)
    for c in candidates:
        p_present = spoof_rate if c.get("synthetic") else 0.85
        c["prov_ok"] = pv.random() < p_present
    info = {"synth_positions": synth_positions, "n_synth": n_synth}
    return candidates, info