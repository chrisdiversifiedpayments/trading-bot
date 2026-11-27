"""Buy the 5 biggest UP movers (2021 large-company list) and hold them.

A) Rolling: every `hold` trading days, sell everything and buy the 5 stocks that rose most over the
   last `look` trading days (equal weight), at the next open. Cost per fill in bps.
B) One-shot: on every trading day, imagine buying that day's 5 biggest up-movers at the next open and
   holding 1 year; compare the average and the spread of outcomes with SPY over the same year.
Prices include dividends. Delisted names are sold at their last price.
"""
import json
import os
import sys
from datetime import date
from statistics import mean, median

sys.path.insert(0, os.path.dirname(__file__))
from universes import LARGE_2021  # noqa: E402

COST = (float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 5) / 1e4
W = json.load(open("data_cache/daily_wide_ohlc.json"))
px = {s: {r[0]: r[1:] for r in W[s]} for s in LARGE_2021 if s in W}
days = sorted({r[0] for r in W["SPY"]})
spy = {r[0]: r[1:] for r in W["SPY"]}
if "--drop-outliers" in sys.argv:
    # robustness check: drop names that ever had a one-day move above 25% (possible data glitches)
    bad = set()
    for s_, x in px.items():
        ds = sorted(x)
        if any(abs(x[b_][3] / x[a_][3] - 1) > 0.25 for a_, b_ in zip(ds, ds[1:])):
            bad.add(s_)
    px = {k: v for k, v in px.items() if k not in bad}
    print("dropped:", sorted(bad))
last = {s: max(x) for s, x in px.items()}


def close(s, d):
    x = px[s]
    return x[d][3] if d in x else x[last[s]][3]


def rolling(look, hold, start="2021-06-01", end="2099-01-01"):
    i0 = next(i for i, d in enumerate(days) if d >= start)
    eq, peak, dd = 1.0, 1.0, 0.0
    i = i0
    while i + hold < len(days) and days[min(i + hold, len(days) - 1)] <= end:
        d0 = days[i]
        movers = sorted(((x[d0][3] / x[days[i - look]][3] - 1, s) for s, x in px.items()
                         if d0 in x and days[i - look] in x and last[s] > d0), reverse=True)[:5]
        buy_day = days[i + 1]
        sell_day = days[min(i + hold, len(days) - 1)]
        rets = []
        for _, s in movers:
            if buy_day not in px[s]:
                continue
            entry = px[s][buy_day][0] * (1 + COST)
            rets.append(close(s, sell_day) * (1 - COST) / entry - 1)
        r = mean(rets) if rets else 0.0
        # mark the drawdown roughly at each rebalance
        eq *= 1 + r
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
        i += hold
    yrs = (date.fromisoformat(days[i]) - date.fromisoformat(days[i0])).days / 365.25
    return 100 * (eq ** (1 / yrs) - 1), 100 * dd


def spy_cagr(a="2021-06-01"):
    ds = [d for d in days if d >= a]
    yrs = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days / 365.25
    return 100 * ((spy[ds[-1]][3] / spy[ds[0]][0]) ** (1 / yrs) - 1)


print(f"cost {COST * 1e4:.0f} bps per fill. Hold SPY Jun 2021-Nov 2026: {spy_cagr():.1f}%/yr")
print("A) Rolling: buy 5 biggest up-movers, hold, repeat")
for look, lname in ((1, "1 day"), (5, "1 week"), (21, "1 month"), (63, "3 months")):
    row = []
    for hold, hname in ((5, "week"), (21, "month"), (63, "3 mo"), (252, "year")):
        r, dd = rolling(look, hold)
        row.append(f"hold {hname}: {r:6.1f}%/yr (drop {dd:4.1f}%)")
    print(f"  movers over {lname:<8} " + " | ".join(row))

print("C) Fair check: settings ranked on Jun 2021-Dec 2023, then the same settings on 2024-Nov 2026")
combos = [(l, h) for l in (1, 5, 21, 63) for h in (5, 21, 63)]
first = sorted(((rolling(l, h, "2021-06-01", "2023-12-31")[0], l, h) for l, h in combos), reverse=True)
for r1, l, h in first:
    r2, dd2 = rolling(l, h, "2024-01-02")
    print(f"  look {l:>2}d hold {h:>2}d   first half {r1:6.1f}%/yr   second half {r2:6.1f}%/yr (drop {dd2:4.1f}%)")
print(f"  SPY: first half 6.4%/yr, second half 16.8%/yr")

print("B) One-shot: buy a day's 5 biggest up-movers, hold 1 year, vs SPY same year")
beats, diffs, outs = 0, [], []
start = next(i for i, d in enumerate(days) if d >= "2021-06-01")
for i in range(start, len(days) - 253):
    d0, b, e = days[i], days[i + 1], days[i + 252]
    movers = sorted(((x[d0][3] / x[days[i - 1]][3] - 1, s) for s, x in px.items()
                     if d0 in x and days[i - 1] in x and last[s] > d0), reverse=True)[:5]
    rs = [close(s, e) * (1 - COST) / (px[s][b][0] * (1 + COST)) - 1 for _, s in movers if b in px[s]]
    if not rs:
        continue
    r = mean(rs)
    sr = spy[e][3] / spy[b][0] - 1
    outs.append(r)
    diffs.append(r - sr)
    beats += r > sr
print(f"  start days tested {len(outs)}; average 1-year return {100 * mean(outs):.1f}% "
      f"(median {100 * median(outs):.1f}%); beat SPY on {100 * beats / len(outs):.0f}% of start days; "
      f"average gap vs SPY {100 * mean(diffs):+.1f} points; worst {100 * min(outs):.1f}%, best {100 * max(outs):.1f}%")
