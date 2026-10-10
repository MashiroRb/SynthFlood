"""Metrics: success, regret, susceptibility, calibration, DD-AUC, epsilon50."""
import math


def dd_auc(points):
    """points: list of (eps, success_rate). Area under success-eps curve,
    normalized to [0,1]: 1.0 means no degradation anywhere."""
    pts = sorted(points)
    if len(pts) < 2:
        return float("nan")
    area = 0.0
    for (e0, s0), (e1, s1) in zip(pts, pts[1:]):
        area += (e1 - e0) * (s0 + s1) / 2.0
    return area / pts[-1][0] if pts[-1][0] > 0 else float("nan")


def epsilon50(points, random_floor):
    """Smallest eps at which success drops below the midpoint of the
    clean-to-random gap."""
    pts = sorted(points)
    if len(pts) < 2:
        return float("nan")
    clean = pts[0][1]
    mid = (clean + random_floor) / 2.0
    for e, s in pts:
        if s <= mid:
            return e
    return float("nan")


def susceptibility(n_synth_available, n_synth_chosen, n_trials):
    """P(choose synthetic | synthetic in candidates), with Wilson 95% CI."""
    if n_trials == 0 or n_synth_available == 0:
        return float("nan"), (float("nan"), float("nan"))
    p = n_synth_chosen / n_synth_available
    z = 1.96
    den = 1 + z * z / n_synth_available
    c = (p + z * z / (2 * n_synth_available)) / den
    h = z * math.sqrt(p * (1 - p) / n_synth_available +
                      z * z / (4 * n_synth_available ** 2)) / den
    return p, (max(0.0, c - h), min(1.0, c + h))


def ece(confidences, corrects, n_bins=10):
    """Expected calibration error for scalar confidences in [0,1]."""
    if not confidences:
        return float("nan")
    bins = [[] for _ in range(n_bins)]
    for c, y in zip(confidences, corrects):
        bins[min(n_bins - 1, int(c * n_bins))].append((c, y))
    e = 0.0
    n = len(confidences)
    for b in bins:
        if not b:
            continue
        acc = sum(y for _, y in b) / len(b)
        conf = sum(c for c, _ in b) / len(b)
        e += len(b) / n * abs(acc - conf)
    return e


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_p(b, c):
    """Exact-ish two-sided binomial McNemar test p-value (normal approx)."""
    if b + c == 0:
        return 1.0
    from math import sqrt, erf
    z = (b - c) / sqrt(b + c)
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def bootstrap_ci(values, stat=lambda v: sum(v) / len(v), B=2000, seed=0):
    import random
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(B):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(stat(sample))
    stats.sort()
    return (stats[int(0.025 * B)], stats[int(0.975 * B)])