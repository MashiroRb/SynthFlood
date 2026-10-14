"""Mine real lookalike pairs from the FULL WebShop catalog (1.18M items)
and intersect with human instructions to build real-clone probe tasks.
Output: realattack_pairs.json  (list of task specs)
"""
import json, re, itertools, collections, statistics

CATALOG = "/root/data/items_shuffle.json"
HUMAN_INS = "/root/data/items_human_ins.json"
OUT = "/root/realattack/realattack_pairs.json"

STOP = {"the","and","for","with","set","of","in","to","a","new","pack","size","pc","pcs"}
def toks(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return [t for t in s.split() if t and t not in STOP and len(t) > 1]

def price_of(rec):
    m = re.search(r"[\d,]+\.?\d*", str(rec.get("pricing") or ""))
    if not m: return None
    try: return float(m.group().replace(",", ""))
    except ValueError: return None

print("loading human instructions...", flush=True)
human = json.load(open(HUMAN_INS))
ins_asins = set(human.keys())
print("asins with human instructions:", len(ins_asins), flush=True)

print("loading catalog...", flush=True)
items = json.load(open(CATALOG))
print("items:", len(items), flush=True)

# index by (brand_token, first_noun, category)
blocks = collections.defaultdict(list)
for i, rec in enumerate(items):
    t = toks(rec.get("name"))
    if len(t) < 3: continue
    p = price_of(rec)
    if not p or p <= 0: continue
    brand = toks((rec.get("brand") or "").replace("Brand:", ""))[:1]
    bkey = (brand[0] if brand else "nobrand", t[0], rec.get("category"))
    blocks[bkey].append(i)

pairs = []
for bkey, idxs in blocks.items():
    if len(idxs) < 2 or len(idxs) > 80: continue
    tk = [frozenset(toks(items[i]["name"])) for i in idxs]
    pr = [price_of(items[i]) for i in idxs]
    for x, y in itertools.combinations(range(len(idxs)), 2):
        if not (0.80 <= len(tk[x] & tk[y]) / max(1, len(tk[x] | tk[y])) < 0.95):
            continue
        pa, pb = pr[x], pr[y]
        if not pa or not pb or max(pa, pb) <= 0: continue
        disc = 1 - min(pa, pb) / max(pa, pb)
        if disc < 0.10: continue
        ia, ib = idxs[x], idxs[y]
        hi, lo = (ia, ib) if pa >= pb else (ib, ia)   # hi = pricier member (gold-ish)
        if items[hi]["asin"] in ins_asins:
            pairs.append({
                "gold_asin": items[hi]["asin"],
                "clone_asin": items[lo]["asin"],
                "jaccard": len(tk[x] & tk[y]) / max(1, len(tk[x] | tk[y])),
                "gold_price": max(pa, pb), "clone_price": min(pa, pb),
                "natural_discount": round(disc, 4),
                "gold_title": items[hi]["name"][:120],
                "clone_title": items[lo]["name"][:120],
                "category": bkey[2],
            })
print("pairs with pricier member having human instructions:", len(pairs), flush=True)
json.dump(pairs, open(OUT, "w"))
disc = [p["natural_discount"] for p in pairs]
if disc:
    print(f"natural discount: median={statistics.median(disc):.3f} >=15%: {sum(d>=0.15 for d in disc)/len(disc):.1%}")
print("saved", OUT)
