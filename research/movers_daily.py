"""Trade only the day's 10 biggest movers among large S&P 500 companies (2021 list, ~100 names).

"Movers" are picked with information available at the 9:30 open (no peeking):
  gap  = today's open vs. yesterday's close (the 10 largest jumps or drops)
  prev = yesterday's close vs. the day before (yesterday's 10 biggest movers)
Each mover gets 10% of the account, bought or shorted at the open and closed at the close.
  with = trade in the direction of the move; fade = bet against it; long-ups = only buy the up-movers.
Cost per fill in bps on the command line (each trade pays it twice).
"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from universes import LARGE_2021  # noqa: E402

COST = (float(sys.argv[1]) if len(sys.argv) > 1 else 5) / 1e4
W = json.load(open("data_cache/daily_wide_ohlc.json"))
px = {s: {r[0]: r[1:] for r in W[s]} for s in LARGE_2021 if s in W}  # (o,h,l,c)
days = sorted({r[0] for r in W["SPY"]})
spy = {r[0]: r for r in W["SPY"]}


def run(pick, mode, start, end):
    eq, peak, dd, n = 1.0, 1.0, 0.0, 0
    sel = [d for d in days if start <= d <= end]
    for i in range(2, len(days)):
        d, p1, p2 = days[i], days[i - 1], days[i - 2]
        if d not in sel:
            continue
        cands = []
        for s, x in px.items():
            if d in x and p1 in x and (pick == "gap" or p2 in x):
                move = x[d][0] / x[p1][3] - 1 if pick == "gap" else x[p1][3] / x[p2][3] - 1
                cands.append((abs(move), move, s))
        top = sorted(cands, reverse=True)[:10]
        rs = []
        for _, move, s in top:
            oc = px[s][d][3] / px[s][d][0] - 1
            side = 1 if move > 0 else -1
            if mode == "fade":
                side = -side
            if mode == "long-ups" and move <= 0:
                continue
            rs.append(side * oc - 2 * COST)
        day_r = 0.1 * sum(rs)
        n += len(rs)
        eq *= 1 + day_r
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
    yrs = (date.fromisoformat(sel[-1]) - date.fromisoformat(sel[0])).days / 365.25
    return 100 * (eq ** (1 / yrs) - 1), 100 * dd, n


def spy_hold(start, end):
    sel = [d for d in days if start <= d <= end]
    yrs = (date.fromisoformat(sel[-1]) - date.fromisoformat(sel[0])).days / 365.25
    return 100 * ((spy[sel[-1]][4] / spy[sel[0]][1]) ** (1 / yrs) - 1)


for label, (a, b) in (("Jun 2021-Nov 2026", ("2021-06-01", "2026-11-26")),
                      ("Jun 2021-Dec 2023", ("2021-06-01", "2023-12-31")),
                      ("2024-Nov 2026", ("2024-01-01", "2026-11-26"))):
    print(f"== {label}  (hold SPY {spy_hold(a, b):.1f}%/yr), cost {COST * 1e4:.0f} bps")
    for pick in ("gap", "prev"):
        for mode in ("with", "fade", "long-ups"):
            r, dd, n = run(pick, mode, a, b)
            print(f"   {pick:<4} {mode:<9} per year {r:7.1f}%  worst drop {dd:5.1f}%  trades {n}")
