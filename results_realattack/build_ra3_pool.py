"""Build RA3 pool: REAL same-category listings + programmatic inflation
signals (rating 4.6-4.9, 400-3000 reviews, price=f*gold set at runtime)
+ REAL YelpZip filtered (fake) review texts. All text is real; only the
inflation signals are assigned programmatically, exactly as in the
synthetic reviews-family protocol."""
import json, random, collections

items = json.load(open("/tmp/work/prj_01M4HVRPHEDVD2DBGC9EN30RKN/realdata/ws_items_struct.json"))
goals = json.load(open("/tmp/work/prj_01M4HVRPHEDVD2DBGC9EN30RKN/repo_clone/data/contamination/goals100.json"))
fake_texts = open("/tmp/work/prj_01M4HVRPHEDVD2DBGC9EN30RKN/realattack/yelpzip/fake_reviews_pos.txt").read().split("\n===\n")
fake_texts = [t.strip().replace("\n", " ")[:300] for t in fake_texts if len(t.strip()) > 120]
rng = random.Random(77)

# index real items by top query tokens
def toks(s):
    import re
    return [t for t in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if len(t) > 2]
by_q = collections.defaultdict(list)
for it in items:
    if it["Title"] and it["price"]:
        for t in toks(it["query"])[:2]:
            by_q[t].append(it)

pool = {}
used = set()
for gi, goal in enumerate(goals):
    q = goal.get("query", "")
    qt = toks(q)
    cands = []
    for t in qt:
        cands.extend(by_q.get(t, []))
    # fallback: same category
    if len(cands) < 20:
        cands = [it for it in items if it["cat"] == goal.get("category")]
    entries = []
    seen = set()
    for it in cands:
        a = it["asin"]
        if a in seen or a in used or not it["Title"] or not it["price"]:
            continue
        seen.add(a)
        revs = [{"stars": 5, "text": fake_texts[rng.randrange(len(fake_texts))]}
                for _ in range(6)]
        entries.append({"asin": a, "family": "reviews_real",
                        "product_category": goal.get("product_category", ""),
                        "query": q, "Brand": it["Brand"],
                        "Title": it["Title"], "BulletPoints": it["BulletPoints"],
                        "Description": it["Description"],
                        "Attributes": [], "price": None, "rating": None,
                        "num_reviews": None, "reviews": revs,
                        "judge_score": 5})
        if len(entries) >= 12:
            break
    used |= seen
    pool[gi] = entries
    if len(entries) < 12:
        print(f"task {gi}: only {len(entries)} entries")
json.dump(pool, open("/tmp/work/prj_01M4HVRPHEDVD2DBGC9EN30RKN/realattack/ra3_pool.json", "w"))
print("tasks:", len(pool), "median per task:", sorted(len(v) for v in pool.values())[50])
