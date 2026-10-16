import csv, math, random
from collections import defaultdict

R = "results_csv/"
def rows(fn):
    out = []
    for r in csv.DictReader(open(R + fn)):
        if not r["task_id"] or r.get("chosen_kind", "").find("SKIPPED") >= 0:
            continue
        out.append(r)
    return out

def syn(r):
    return int(r.get("chosen_is_synthetic", r.get("is_synthetic", "0")))

FILES = {
    "orig": "p1_forced_choice.csv",
    "B": "p1_probeB.csv",
    "C": "p1_probeC.csv",
    "BC": "p1_probeBC.csv",
    "f90": "p1_price90.csv",
    "f80": "p1_price80.csv",
    "f70": "p1_price70.csv",
}
data = {}
for k, fn in FILES.items():
    rs = rows(fn)
    data[k] = rs
    tasks = sorted(set(r["task_id"] for r in rs))
    print(f"{k}: {len(rs)} duels, {len(tasks)} tasks")

def clone_rows(rs):
    return [r for r in rs if r.get("family") == "clone"]

# cluster bootstrap over task clusters
def cluster_ci(rows_subset, key_fn=lambda r: r["task_id"], B=20000, seed=2027):
    by = defaultdict(list)
    for r in rows_subset:
        by[key_fn(r)].append(syn(r))
    clusters = sorted(by)
    n_duel = len(rows_subset)
    p_hat = sum(sum(v) for v in by.values()) / n_duel
    rng = random.Random(seed)
    stats = []
    for _ in range(B):
        acc = 0; cnt = 0
        for _ in range(len(clusters)):
            v = by[rng.choice(clusters)]
            acc += sum(v); cnt += len(v)
        if cnt:
            stats.append(acc / cnt)
    stats.sort()
    lo = stats[int(0.025 * B)]; hi = stats[int(0.975 * B)]
    se = (lambda xs: (sum((x - sum(xs)/len(xs))**2 for x in xs) / (len(xs)-1)) ** 0.5)(stats)
    return p_hat, lo, hi, se, len(clusters), n_duel

print("\n== point estimates + task-cluster bootstrap 95% CI ==")
res = {}
for k in FILES:
    sub = clone_rows(data[k]) if k != "orig" else data[k]
    if k == "orig":
        p, lo, hi, se, nc, nd = cluster_ci(data[k])
        z = (p - 0.5) / se
        from math import erf, sqrt
        p2 = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
        print(f"overall: sigma={p:.3f} clusterCI=[{lo:.3f},{hi:.3f}] se={se:.4f} z={z:.2f} p={p2:.2e} clusters={nc} duels={nd}")
        res["overall"] = (p, lo, hi, p2)
    else:
        p, lo, hi, se, nc, nd = cluster_ci(sub)
        print(f"{k}: sigma={p:.3f} clusterCI=[{lo:.3f},{hi:.3f}] se={se:.4f} clusters={nc} duels={nd}")
        res[k] = (p, lo, hi)

# per-family on orig
print("\n== per-family (orig file) ==")
fams = sorted(set(r["family"] for r in data["orig"]))
for fam in fams:
    sub = [r for r in data["orig"] if r["family"] == fam]
    p, lo, hi, se, nc, nd = cluster_ci(sub)
    print(f"{fam}: sigma={p:.3f} clusterCI=[{lo:.3f},{hi:.3f}] duels={nd}")

# paired contrasts, matched by (task_id, pair_seed), clone rows only
def matched(a, b):
    ka = {(r["task_id"], r["pair_seed"]): syn(r) for r in clone_rows(data[a])}
    kb = {(r["task_id"], r["pair_seed"]): syn(r) for r in clone_rows(data[b])}
    keys = sorted(set(ka) & set(kb))
    return [(ka[k], kb[k]) for k in keys], ka, kb

def mcnemar(pairs):
    b = sum(1 for x, y in pairs if x == 0 and y == 1)
    c = sum(1 for x, y in pairs if x == 1 and y == 0)
    n = b + c
    if n == 0: return b, c, 1.0
    from math import comb
    p = sum(comb(n, k) for k in range(0, min(b, c) + 1)) / 2**n * 2
    return b, c, min(1.0, p)

def paired_cluster(a, b, B=20000, seed=2027):
    pairs, ka, kb = matched(b, a)  # pairs = (val_a, val_b) = (orig, arm)
    keys = sorted(set(ka) & set(kb))
    dmap = {k: (ka[k], kb[k]) for k in keys}
    tasks = sorted(set(k[0] for k in keys))
    rng = random.Random(seed)
    deltas = []
    for _ in range(B):
        acc = 0.0; cnt = 0
        for _ in range(len(tasks)):
            t = rng.choice(tasks)
            for k in keys:
                if k[0] == t:
                    acc += dmap[k][1] - dmap[k][0]; cnt += 1
        if cnt:
            deltas.append(acc / cnt)
    deltas.sort()
    lo = deltas[int(0.025 * B)]; hi = deltas[int(0.975 * B)]
    m = sum(deltas) / len(deltas)
    se = (sum((x - m) ** 2 for x in deltas) / (len(deltas) - 1)) ** 0.5
    from math import erf, sqrt
    point = sum(y for x, y in pairs) / len(pairs) - sum(x for x, y in pairs) / len(pairs)
    z = point / se if se > 0 else 0.0
    p2 = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return len(pairs), point, lo, hi, z, p2

print("\n== paired contrasts (clone duels, matched by task+pair_seed) ==")
for a, b, label in [("orig", "B", "priceParity-orig"), ("orig", "C", "ratingParity-orig"),
                    ("orig", "BC", "both-orig"), ("B", "f90", "f90-f1.0"),
                    ("B", "f80", "f80-f1.0"), ("B", "f70", "f70-f1.0"),
                    ("f90", "f80", "f80-f90"), ("f90", "f70", "f70-f90")]:
    n, point, lo, hi, z, p2 = paired_cluster(a, b)
    bb, cc, pm = mcnemar(matched(b, a)[0])
    print(f"{label}: n={n} delta={point:+.3f} clusterCI=[{lo:+.3f},{hi:+.3f}] z={z:.2f} p={p2:.3f} | flips arm_only={cc} orig_only={bb} mcnemarP={pm:.4f}")
