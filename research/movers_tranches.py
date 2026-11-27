"""Top-5 1-month risers, held 1 month, with the money split into 4 batches that rebalance on
different weeks (removes most "which day of the month" luck). Valued every day for honest drawdowns.

Signal at a close: the 5 stocks (2021 large-company list) with the highest return over the last
`look` trading days. Trade at the next open. Each batch rebalances every `hold` trading days, the 4
batches offset by hold/4 days. Cost per fill in bps. Delisted names are sold at their last price.
Usage: python research/movers_tranches.py [cost_bps] [--drop-outliers] [--top N] [--look L] [--hold H]
"""
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from universes import LARGE_2016, LARGE_2021  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("cost", nargs="?", type=float, default=5)
ap.add_argument("--drop-outliers", action="store_true")
ap.add_argument("--top", type=int, default=5)
ap.add_argument("--look", type=int, default=21)
ap.add_argument("--hold", type=int, default=21)
ap.add_argument("--since2016", action="store_true", help="2016 company list and SIP data back to 2016")
a = ap.parse_args()
COST = a.cost / 1e4

W = json.load(open("data_cache/daily_2016.json" if a.since2016 else "data_cache/daily_wide_ohlc.json"))
UNI = LARGE_2016 if a.since2016 else LARGE_2021
px = {s: {r[0]: r[1:] for r in W[s]} for s in UNI if s in W}
if a.drop_outliers:
    bad = {s for s, x in px.items() for p, d in zip(sorted(x), sorted(x)[1:]) if abs(x[d][3] / x[p][3] - 1) > 0.25}
    px = {k: v for k, v in px.items() if k not in bad}
days = sorted({r[0] for r in W["SPY"]})
spy = {r[0]: r[1:] for r in W["SPY"]}
last = {s: max(x) for s, x in px.items()}
lastpx = {}


def run(start, end):
    i0 = next(i for i, d in enumerate(days) if d >= start)
    i1 = max(i for i, d in enumerate(days) if d <= end)
    n = 4
    tr = [{"cash": 10_000.0 / n, "pos": {}} for _ in range(n)]
    curve, pending = [], {}
    for i in range(i0, i1 + 1):
        d = days[i]
        for s, x in px.items():
            if d in x:
                lastpx[s] = x[d]
        # execute pending rebalances at the open
        for k, picks in list(pending.items()):
            t = tr[k]
            for s, q in t["pos"].items():
                p = px[s][d][0] if d in px[s] else lastpx[s][3]
                t["cash"] += q * p * (1 - COST)
            t["pos"] = {}
            buy = [s for s in picks if d in px[s]]
            if buy:
                each = t["cash"] / len(buy)
                for s in buy:
                    t["pos"][s] = each * (1 - COST) / px[s][d][0]
                t["cash"] = 0.0
            del pending[k]
        # delisted names: cash out
        for t in tr:
            for s in [s for s in t["pos"] if last[s] < d]:
                t["cash"] += t["pos"].pop(s) * lastpx[s][3] * (1 - COST)
        value = sum(t["cash"] + sum(q * lastpx[s][3] for s, q in t["pos"].items()) for t in tr)
        curve.append((d, value))
        # signals at the close
        for k in range(n):
            if (i - i0 - k * (a.hold // n)) % a.hold == 0 and i - i0 >= k * (a.hold // n) and i + 1 <= i1:
                ranked = sorted(((x[d][3] / x[days[i - a.look]][3] - 1, s) for s, x in px.items()
                                 if d in x and days[i - a.look] in x and last[s] > d), reverse=True)
                pending[k] = [s for _, s in ranked[:a.top]]
    v = [x for _, x in curve]
    peak, dd = v[0], 0.0
    for x in v:
        peak = max(peak, x)
        dd = max(dd, 1 - x / peak)
    yrs = (date.fromisoformat(curve[-1][0]) - date.fromisoformat(curve[0][0])).days / 365.25
    return 100 * ((v[-1] / 10_000) ** (1 / yrs) - 1), 100 * dd


def spy_stats(start, end):
    ds = [d for d in days if start <= d <= end]
    c = [spy[d][3] for d in ds]
    peak, dd = c[0], 0.0
    for x in c:
        peak = max(peak, x)
        dd = max(dd, 1 - x / peak)
    yrs = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days / 365.25
    return 100 * ((c[-1] / spy[ds[0]][0]) ** (1 / yrs) - 1), 100 * dd


print(f"top {a.top}, look {a.look}d, hold {a.hold}d, cost {a.cost} bps{' , outlier names dropped' if a.drop_outliers else ''}")
PERIODS = ((("Feb 2016-Nov 2026", ("2016-02-03", "2026-11-26")), ("2016-2020", ("2016-02-03", "2020-12-31")),
            ("2021-Nov 2026", ("2021-01-04", "2026-11-26")))
           + tuple((str(y), (f"{y}-01-01" if y > 2016 else "2016-02-03", f"{y}-12-31")) for y in range(2016, 2027))
           if a.since2016 else
           (("Jun 2021-Nov 2026", ("2021-06-01", "2026-11-26")), ("Jun 2021-Dec 2023", ("2021-06-01", "2023-12-31")),
            ("2024-Nov 2026", ("2024-01-02", "2026-11-26"))))
for label, (s, e) in PERIODS:
    r, dd = run(s, e)
    sr, sdd = spy_stats(s, e)
    print(f"  {label:<18} strategy {r:6.1f}%/yr  worst drop {dd:5.1f}%   |  SPY {sr:5.1f}%/yr  worst drop {sdd:5.1f}%")
