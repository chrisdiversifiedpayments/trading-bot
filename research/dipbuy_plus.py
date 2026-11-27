"""Dip-buy with the two cost/idle-cash changes, on the 2021 large-company list.

Changes tested:
1. Limit entries: instead of buying at the next open (market order, 5 bps cost), place a limit order
   `offset` below the signal-day close. It fills only if the next day's low reaches it, at the
   better of the open or the limit; 1 bp cost. Unfilled orders expire that day.
2. Park idle cash in SPY: money not in dip trades sits in SPY (bought/sold with 5 bps cost).
Exits stay pessimistic: market order at the next open with 5 bps cost.
"""
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from universes import LARGE_2021  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("start", nargs="?", default="2021-06-01")
ap.add_argument("end", nargs="?", default="2026-11-26")
a = ap.parse_args()
START, END = date.fromisoformat(a.start), date.fromisoformat(a.end)

W = json.load(open("data_cache/daily_wide_ohlc.json"))
D = {k: v for k, v in W.items() if k in set(LARGE_2021) | {"SPY"}}
days = sorted({r[0] for r in D["SPY"]})
px = {s: {r[0]: tuple(r[1:]) for r in rows} for s, rows in D.items()}  # (open, high, low, close)
last_day = {s: rows[-1][0] for s, rows in D.items()}
O, H, L, C = 0, 1, 2, 3


def closes(s, i, n):
    return [px[s][d][C] for d in days[max(0, i - n + 1): i + 1] if d in px[s]]


def sma(s, i, n):
    c = closes(s, i, n)
    return sum(c) / n if len(c) == n else None


def rsi2(s, i):
    c = closes(s, i, 3)
    if len(c) < 3:
        return None
    g = sum(max(c[k] - c[k - 1], 0) for k in (1, 2))
    l = sum(max(c[k - 1] - c[k], 0) for k in (1, 2))
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def simulate(limit_offset, park_spy, slots=5, weight=0.2, exit_bps=5, spy_bps=5):
    cash, spy, pos, held = 10_000.0, 0.0, {}, {}
    sells, orders, curve, fills, missed = [], [], [], 0, 0
    last_close = {}

    def spy_px(d, k):
        return px["SPY"][d][k]

    for i, d in enumerate(days):
        if not (START <= date.fromisoformat(d) <= END):
            continue
        # exits at the open
        for s in sells:
            if s in pos and d in px[s]:
                cash += pos.pop(s) * px[s][d][O] * (1 - exit_bps / 1e4)
                held.pop(s, None)
        for s in [s for s in pos if last_day[s] < d]:  # bought out / delisted
            cash += pos.pop(s) * px[s][last_day[s]][C] * (1 - exit_bps / 1e4)
            held.pop(s, None)
        # entries (positions are valued at their latest known price)
        total = cash + spy * spy_px(d, O) + sum(q * (px[s][d][O] if d in px[s] else last_close[s]) for s, q in pos.items())
        for s, ref_close in orders:
            if s in pos or d not in px[s]:
                continue
            o, h, l, c = px[s][d]
            if limit_offset is None:
                fill, cost = o, 5
            else:
                lim = ref_close * (1 - limit_offset)
                if l > lim:
                    missed += 1
                    continue
                fill, cost = min(o, lim), 1
            spend = total * weight
            if cash < spend and park_spy and spy > 0:  # sell SPY to fund it
                need = min(spend - cash, spy * spy_px(d, O))
                spy -= need / spy_px(d, O)
                cash += need * (1 - spy_bps / 1e4)
            spend = min(spend, cash)
            if spend > 1:
                pos[s] = spend * (1 - cost / 1e4) / fill
                last_close[s] = fill
                cash -= spend
                held[s] = 0
                fills += 1
        # park leftover cash in SPY at the close
        if park_spy and cash > 100:
            spy += cash * (1 - spy_bps / 1e4) / spy_px(d, C)
            cash = 0.0
        for s in held:
            held[s] += 1
        for s in pos:
            if d in px[s]:
                last_close[s] = px[s][d][C]
        value = cash + spy * spy_px(d, C) + sum(q * last_close[s] for s, q in pos.items())
        curve.append(value)
        # signals at the close for tomorrow
        sells = [s for s in pos if (sma(s, i, 5) and px[s][d][C] > sma(s, i, 5)) or held[s] >= 10]
        free = slots - (len(pos) - len(sells))
        cands = []
        for s in px:
            if s == "SPY" or s in pos or d not in px[s] or last_day[s] <= d:
                continue
            m, r = sma(s, i, 200), rsi2(s, i)
            if m and r is not None and px[s][d][C] > m and r < 10:
                cands.append((r, s))
        orders = [(s, px[s][d][C]) for _, s in sorted(cands)[:max(free, 0)]]
    years = (END - START).days / 365.25
    peak, dd = curve[0], 0
    for v in curve:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    return 100 * ((curve[-1] / 10_000) ** (1 / years) - 1), 100 * dd, fills, missed


def spy_hold():
    ds = [d for d in days if START <= date.fromisoformat(d) <= END]
    c = [px["SPY"][d][C] for d in ds]
    peak, dd = c[0], 0
    for v in c:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    years = (END - START).days / 365.25
    return 100 * ((c[-1] / px["SPY"][ds[0]][O]) ** (1 / years) - 1), 100 * dd


r, dd = spy_hold()
print(f"{'Hold SPY':<40} yearly {r:5.1f}%  worst drop {dd:5.1f}%")
for name, off in (("market entry", None), ("limit at close", 0.0), ("limit 0.5% below", 0.005), ("limit 1% below", 0.01)):
    for park in (False, True):
        r, dd, f, m = simulate(off, park)
        label = f"{name}{' + idle cash in SPY' if park else ''}"
        print(f"{label:<40} yearly {r:5.1f}%  worst drop {dd:5.1f}%  fills {f}  unfilled {m}")
