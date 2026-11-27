"""Pairs trading (classic "distance" method) on the 2021 large-company list.

Every 6 months: look back 12 months, normalize each stock's price, and pick the 10 pairs whose
prices moved most alike. Trade those pairs for the next 6 months only (never on data used to pick them):
when the gap between the two widens past 2 standard deviations, buy the cheap one and short the rich one;
close when the gap is back under 0.5, or past 4 (stop), or at the end of the 6 months.
Each open pair uses 10% of equity on each side. 5 bps cost per fill per leg. Short borrow fees ignored.
"""
import json
import os
import sys
from datetime import date

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from universes import LARGE_2021  # noqa: E402

COST = float(sys.argv[1]) / 1e4 if len(sys.argv) > 1 else 0.0005
W = json.load(open("data_cache/daily_wide_ohlc.json"))
days = sorted({r[0] for r in W["SPY"]})
idx = {d: i for i, d in enumerate(days)}
syms = [s for s in LARGE_2021 if s in W]
P = np.full((len(days), len(syms)), np.nan)
for j, s in enumerate(syms):
    for r in W[s]:
        if r[0] in idx:
            P[idx[r[0]], j] = r[4]

START, END = date(2021, 6, 1), date(2026, 11, 26)
FORM, TRADE = 252, 126
t0 = max(FORM, next(i for i, d in enumerate(days) if date.fromisoformat(d) >= START))  # need 12 months of history first

equity = [10_000.0]
dates = [days[t0 - 1]]
eq = 10_000.0
n_trades = 0
t = t0
while t < len(days):
    f0 = t - FORM
    form = P[f0:t]
    ok = ~np.isnan(form).any(axis=0) & ~np.isnan(P[t:min(t + TRADE, len(days))]).any(axis=0)
    cols = np.where(ok)[0]
    norm = form[:, cols] / form[0, cols]
    # distance between every pair of normalized price paths
    best = []
    for a in range(len(cols)):
        d = ((norm[:, a:a + 1] - norm[:, a + 1:]) ** 2).sum(axis=0)
        for k, v in enumerate(d):
            best.append((v, cols[a], cols[a + 1 + k]))
    best.sort()
    pairs = []
    for v, i, j in best[:10]:
        spread = np.log(form[:, i]) - np.log(form[:, j])
        pairs.append({"i": i, "j": j, "mu": spread.mean(), "sd": spread.std(), "pos": 0})
    end = min(t + TRADE, len(days))
    for k in range(t, end):
        day_ret = 0.0
        for p in pairs:
            i, j = p["i"], p["j"]
            if p["pos"]:
                ri = P[k, i] / P[k - 1, i] - 1
                rj = P[k, j] / P[k - 1, j] - 1
                day_ret += 0.10 * p["pos"] * (ri - rj)
            z = (np.log(P[k, i]) - np.log(P[k, j]) - p["mu"]) / p["sd"]
            last_day = k == end - 1
            if p["pos"] and (abs(z) < 0.5 or abs(z) > 4 or last_day):
                p["pos"] = 0
                day_ret -= 0.10 * 2 * COST
            elif not p["pos"] and not last_day and abs(z) > 2 and abs(z) < 4:
                p["pos"] = -1 if z > 0 else 1  # z>0: i is rich -> short i, long j
                day_ret -= 0.10 * 2 * COST
                n_trades += 1
        eq *= 1 + day_ret
        equity.append(eq)
        dates.append(days[k])
    t = end


def stats(a, b):
    sel = [(d, e) for d, e in zip(dates, equity) if a <= d <= b]
    e = [x for _, x in sel]
    yrs = (date.fromisoformat(sel[-1][0]) - date.fromisoformat(sel[0][0])).days / 365.25
    peak, dd = e[0], 0
    for v in e:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    return f"yearly {100 * ((e[-1] / e[0]) ** (1 / yrs) - 1):5.1f}%  worst drop {100 * dd:4.1f}%"


print(f"cost {COST * 1e4:.0f} bps, pair trades opened: {n_trades}")
for a, b in (("2021-06-01", "2026-11-26"), ("2021-06-01", "2023-12-31"), ("2024-01-01", "2026-11-26")):
    print(f"  {a}..{b}  {stats(a, b)}")
