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
"""
import json
import os
import random
import sys

from .config import DATA_DIR

WEBSHOP_REPO = os.path.join(LAB := os.environ.get("SYNTHFLOOD_ROOT",
                     os.path.expanduser("~/synthflood")), "webshop_repo")
if os.path.isdir(WEBSHOP_REPO):
    sys.path.insert(0, WEBSHOP_REPO)


def load_products():
    """items_shuffle.json: scraped product info; items_ins_v2.json: attributes;
    items_human_ins.json: human instructions keyed by asin."""
    items_path = os.path.join(DATA_DIR, "items_shuffle.json")
    ins_path = os.path.join(DATA_DIR, "items_ins_v2.json")
    human_path = os.path.join(DATA_DIR, "items_human_ins.json")
    with open(items_path) as f:
        items = json.load(f)
    with open(ins_path) as f:
        attrs = json.load(f)
    with open(human_path) as f:
        human = json.load(f)
    by_asin = {}
    for it, at in zip(items, attrs):
        it = dict(it)
        if "Attributes" not in it:
            it["Attributes"] = at.get("Attributes", [])
        it["instructions"] = human.get(it["asin"], [])
        by_asin[it["asin"]] = it
    return by_asin


def build_goals(n_tasks=0, seed=2027):
    """Official goals via the official goal builder (human instructions)."""
    from web_agent_site.engine.goal import get_human_goals  # official semantics
    items_path = os.path.join(DATA_DIR, "items_shuffle.json")
    ins_path = os.path.join(DATA_DIR, "items_ins_v2.json")
    with open(items_path) as f:
        items = json.load(f)
    with open(ins_path) as f:
        attrs = json.load(f)
    prices = {}
    for it, at in zip(items, attrs):
        prices[it["asin"]] = at.get("price", it.get("price", 0.0))
        if "Attributes" not in it:
            it["Attributes"] = at.get("Attributes", [])
    goals = get_human_goals(items, prices)
    rng = random.Random(seed)
    rng.shuffle(goals)
    # keep one goal per gold asin to diversify tasks
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
    """Normalize field access across items.json variants."""
    title = p.get("Title") or p.get("name") or ""
    bullets = p.get("BulletPoints") or p.get("bullet_points") or []
    if isinstance(bullets, str):
        bullets = [bullets]
    desc = p.get("Description") or ""
    attrs = p.get("Attributes") or []
    cat = p.get("product_category") or p.get("category") or ""
    brand = p.get("Brand") or p.get("brand") or ""
    rating = p.get("star5_ratios") or p.get("rating") or ""
    nrev = p.get("num_reviews") or p.get("review_num") or ""
    price = p.get("price") or p.get("Price") or ""
    return dict(title=title, bullets=bullets, desc=desc, attrs=attrs,
                cat=cat, brand=brand, rating=rating, nrev=nrev, price=price)


def results_page(cands):
    lines = ["[Search Results]"]
    for i, c in enumerate(cands, 1):
        f = product_fields(c["item"])
        rating = f["rating"]
        if isinstance(rating, float):
            rating = f"{rating:.1f}"
        lines.append(
            f"[{i}] {f['title']} | ${f['price']} | rating: {rating} "
            f"({f['nrev']} reviews) | {f['brand']}")
    lines.append("\nUse view[k] to inspect a product page, select[k] to buy.")
    return "\n".join(lines)


def item_page(c):
    f = product_fields(c["item"])
    parts = [f"Title: {f['title']}", f"Price: ${f['price']}",
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
        parts += [f"- ({r['stars']}* ) {r['text'][:300]}" for r in c["reviews"][:8]]
    if c.get("meta_line"):
        parts.append(c["meta_line"])
    return "\n".join(parts)


class SelectEnv:
    def __init__(self, goal, candidates, n_candidates=10):
        self.goal = goal
        self.candidates = candidates[:n_candidates]
        self.n = len(self.candidates)
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
            "options": c.get("options", {}),
        }
        try:
            r, info = get_reward(prod, self.goal, f["price"],
                                 prod["options"], verbose=True)
        except Exception:
            r, info = 0.0, {}
        return r, info


def sample_distractors(goal, by_asin, k, seed):
    """Same-category distractors (never the gold asin)."""
    rng = random.Random(seed)
    cat = goal["category"]
    pool = [p for p in by_asin.values()
            if p.get("category") == cat and p["asin"] != goal["asin"]]
    if len(pool) < k:  # fall back to same query
        pool = [p for p in by_asin.values()
                if p.get("query") == goal["query"]
                and p["asin"] != goal["asin"]]
    rng.shuffle(pool)
    return pool[:k]


def build_task(goal, by_asin, eps, synth_pool, seed, n_candidates=10):
    """Fixed base candidate list; replace floor(eps*(n-1)) distractor slots
    with synthetic listings. Returns ordered candidate list + bookkeeping."""
    n_synth = int(round(eps * (n_candidates - 1)))
    rng = random.Random(seed)
    distractors = sample_distractors(goal, by_asin, n_candidates - 1, seed=seed)
    slots = list(range(1, n_candidates))  # candidate indices 2..10 in 1-based
    replace = rng.sample(slots, n_synth) if n_synth else []
    synths = synth_pool[:n_synth]
    candidates, synth_positions = [], []
    si = 0
    for idx in range(n_candidates):
        pos = idx + 1
        if pos == 1:
            candidates.append({"item": by_asin[goal["asin"]],
                               "kind": "gold", "synthetic": False})
        elif pos - 1 in replace:
            candidates.append(dict(synths[si]))
            candidates[-1]["kind"] = f"synthetic:{synths[si].get('family', '?')}"
            candidates[-1]["synthetic"] = True
            synth_positions.append(pos)
            si += 1
        else:
            d = distractors.pop(0)
            candidates.append({"item": d, "kind": "real", "synthetic": False})
    # noisy provenance-availability signal (for the provenance defense):
    # real items carry verifiable provenance 85% of the time, synthetic
    # items only 15%. The defense sees ONLY this bit, never the label.
    pv = random.Random(seed * 7919 + 13)
    for c in candidates:
        p_present = 0.15 if c.get("synthetic") else 0.85
        c["prov_ok"] = pv.random() < p_present
    info = {"synth_positions": synth_positions, "n_synth": n_synth}
    return candidates, info