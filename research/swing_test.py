"""Quick daily (swing) strategy tests vs. buying and holding SPY. Long only, 5 bps cost per fill.

A. Momentum: each month, if SPY is above its 200-day average, hold the 5 stocks with the best
   6-month return (equal weight); otherwise hold cash.
B. Dip-buy: buy a stock that is above its 200-day average after a sharp 2-day drop (RSI(2) < 10),
   sell when it closes above its 5-day average or after 10 days. Up to 5 positions, 20% each.
Signals use the close; trades happen at the next day's open.
"""
import json
import sys
from datetime import date

COST = 0.0005
D = json.load(open("data_cache/daily.json"))
START = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2021, 6, 1)
END = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 11, 26)

days = sorted({r[0] for r in D["SPY"]})
px = {s: {r[0]: (r[1], r[2]) for r in rows} for s, rows in D.items()}


def closes_until(s, i, n):
    out = [px[s][d][1] for d in days[max(0, i - n + 1): i + 1] if d in px[s]]
    return out


def sma(s, i, n):
    c = closes_until(s, i, n)
    return sum(c) / len(c) if len(c) == n else None


def rsi2(s, i):
    c = closes_until(s, i, 3)
    if len(c) < 3:
        return None
    g = [max(c[k] - c[k - 1], 0) for k in (1, 2)]
    l = [max(c[k - 1] - c[k], 0) for k in (1, 2)]
    return 100.0 if sum(l) == 0 else 100 - 100 / (1 + sum(g) / sum(l))


def stats(curve, trades):
    eq = [e for _, e in curve]
    years = (date.fromisoformat(curve[-1][0]) - date.fromisoformat(curve[0][0])).days / 365.25
    peak, dd = eq[0], 0
    for e in eq:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)
    return f"yearly {100 * ((eq[-1] / eq[0]) ** (1 / years) - 1):6.1f}%  total {100 * (eq[-1] / eq[0] - 1):6.1f}%  worst drop {100 * dd:5.1f}%  trades {trades}"


def simulate(strategy):
    cash, pos, curve, trades, held_days = 10_000.0, {}, [], 0, {}
    pending = None
    for i, d in enumerate(days):
        if not (START <= date.fromisoformat(d) <= END):
            continue
        # execute yesterday's orders at today's open
        if pending is not None:
            sells, buys = pending
            for s in sells:
                if s in pos and d in px[s]:
                    cash += pos.pop(s) * px[s][d][0] * (1 - COST)
                    held_days.pop(s, None)
                    trades += 1
            value = cash + sum(q * px[s][d][0] for s, q in pos.items() if d in px[s])
            for s, weight in buys:
                if s not in pos and d in px[s]:
                    spend = min(cash, value * weight)
                    if spend > 1:
                        pos[s] = spend * (1 - COST) / px[s][d][0]
                        cash -= spend
                        held_days[s] = 0
                        trades += 1
            pending = None
        for s in held_days:
            held_days[s] += 1
        value = cash + sum(q * px[s][d][1] for s, q in pos.items() if d in px[s])
        curve.append((d, value))
        pending = strategy(i, d, pos, held_days)
    return curve, trades


def momentum(i, d, pos, held):
    if i % 21:
        return None
    spy_ma = sma("SPY", i, 200)
    if spy_ma is None or px["SPY"][d][1] < spy_ma:
        return (list(pos), [])
    ranked = []
    for s in px:
        if s == "SPY":
            continue
        c = closes_until(s, i, 127)
        if len(c) == 127:
            ranked.append((c[-1] / c[0], s))
    top = [s for _, s in sorted(ranked, reverse=True)[:5]]
    return ([s for s in pos if s not in top], [(s, 0.2) for s in top])


def dipbuy(i, d, pos, held):
    sells = []
    for s in pos:
        ma5 = sma(s, i, 5)
        if (ma5 and px[s][d][1] > ma5) or held.get(s, 0) >= 10:
            sells.append(s)
    buys = []
    slots = 5 - (len(pos) - len(sells))
    cands = []
    for s in px:
        if s in pos or d not in px[s]:
            continue
        ma200, r = sma(s, i, 200), rsi2(s, i)
        if ma200 and r is not None and px[s][d][1] > ma200 and r < 10:
            cands.append((r, s))
    for _, s in sorted(cands)[:max(slots, 0)]:
        buys.append((s, 0.2))
    return (sells, buys)


def buy_hold(i, d, pos, held):
    return ([], [("SPY", 1.0)]) if not pos else None


for name, f in (("Hold SPY (benchmark)", buy_hold), ("A. Momentum monthly", momentum), ("B. Dip-buy", dipbuy)):
    curve, n = simulate(f)
    print(f"{name:<22} {stats(curve, n)}")
