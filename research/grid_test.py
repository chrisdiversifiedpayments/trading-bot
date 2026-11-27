"""Grid trading on index funds (SPY, QQQ, IWM, DIA) using 2 years of 1-minute prices.

Each morning a grid is set around the opening price: buy limit orders every `step` below the open
(up to 5 levels, 20% of the account each), and each filled buy gets a sell order one step higher.
Day version: anything still held is sold at the 3:50 PM price. Multi-day version: holdings and the
grid carry over (grid re-centred only when nothing is held).
Fills: a buy fills when the minute low touches the level; a sell when the minute high reaches its
target. Cost per fill in bps given on the command line. Pick settings on year 1, check on year 2.
"""
import sys
from datetime import date, time

sys.path.insert(0, ".")
from bot import data  # noqa: E402

SPLIT = date(2025, 11, 27)
ETFS = ["SPY", "QQQ", "IWM", "DIA"]
BARS = data.load_cache(ETFS)


def run(sym, step, cost_bps, carry, first_year):
    cost = cost_bps / 1e4
    cash, lots, ref = 10_000.0, [], None  # lots: (buy_price, qty, sell_target, level_price)
    eq_curve, fills = [], 0
    by_day = {}
    for b in BARS[sym]:
        if (b.t.date() < SPLIT) == first_year:
            by_day.setdefault(b.t.date(), []).append(b)
    for d in sorted(by_day):
        bars = by_day[d]
        if not lots or ref is None or not carry:
            ref = bars[0].o
        levels = [ref * (1 - step * k) for k in range(1, 6)]
        for b in bars:
            if b.t.time() >= time(15, 50):
                if not carry:
                    for bp, q, tgt, lv in lots:
                        cash += q * b.o * (1 - cost)
                        fills += 1
                    lots = []
                last = b.o
                break
            # sells first
            keep = []
            for bp, q, tgt, lv in lots:
                if b.h >= tgt:
                    cash += q * tgt * (1 - cost)
                    fills += 1
                else:
                    keep.append((bp, q, tgt, lv))
            lots = keep
            held_levels = {round(lv, 6) for *_, lv in lots}
            for lv in levels:
                if b.l <= lv and round(lv, 6) not in held_levels:
                    value = cash + sum(q * b.c for _, q, _, _ in lots)
                    spend = min(cash, value * 0.2)
                    if spend > 1:
                        q = spend * (1 - cost) / lv
                        cash -= spend
                        lots.append((lv, q, lv * (1 + step), lv))
                        held_levels.add(round(lv, 6))
                        fills += 1
            last = b.c
        eq_curve.append(cash + sum(q * last for _, q, _, _ in lots))
    peak, dd = eq_curve[0], 0
    for v in eq_curve:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    return 100 * (eq_curve[-1] / 10_000 - 1), 100 * dd, fills


def hold(sym, first_year):
    bs = [b for b in BARS[sym] if (b.t.date() < SPLIT) == first_year]
    return 100 * (bs[-1].c / bs[0].o - 1)


cost = float(sys.argv[1]) if len(sys.argv) > 1 else 2
for carry in (False, True):
    print(f"=== {'multi-day' if carry else 'day-only'} grid, cost {cost} bps per fill (average of 4 funds)")
    for year in (True, False):
        h = sum(hold(s, year) for s in ETFS) / 4
        print(f"  {'year 1' if year else 'year 2'}: just holding the 4 funds {h:5.1f}%")
        for step in (0.0025, 0.005, 0.01):
            rs = [run(s, step, cost, carry, year) for s in ETFS]
            print(f"    step {step * 100:.2f}%  return {sum(r[0] for r in rs) / 4:6.1f}%  "
                  f"worst drop {max(r[1] for r in rs):5.1f}%  fills {sum(r[2] for r in rs)}")
