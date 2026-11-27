"""Test calendar and market-mood filters with the tuned settings. Thresholds picked on year 1, checked on year 2.

Needs data_cache/ (bars), data_cache/filters.json (VIXY closes + headlines) and data/calendar.json.
"""
import json
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from multiprocessing import Pool

from bot import backtest, data
from bot.config import load_settings

SPLIT = date(2025, 11, 27)
S = load_settings()
F = json.load(open("data_cache/filters.json"))
CAL = json.load(open("data/calendar.json"))
BARS = {}


def vix_skip_days(jump: float) -> set:
    """Days after VIXY closed more than `jump` above its 20-day average (fear rising). Uses only prior-day data."""
    closes = sorted((date.fromisoformat(d), c) for d, c in F["vixy"].items())
    out = set()
    for i in range(20, len(closes) - 1):
        avg = sum(c for _, c in closes[i - 20:i]) / 20
        if closes[i][1] > avg * (1 + jump):
            out.add(closes[i + 1][0])
    return out


def calendar_days(kinds) -> set:
    return {date.fromisoformat(d) for k in kinds for d in CAL[k]}


def earnings_symbol_days() -> set:
    """(symbol, day) where a results headline came out after 4 PM the day before or before 9:30 that day."""
    out = set()
    for sym, items in F.get("news", {}).items():
        for ts, _, head in items:
            h = head.lower()
            if "results" not in h and "earnings" not in h:
                continue
            t = datetime.fromisoformat(ts)
            if t.time() >= time(16, 0):
                out.add((sym, t.date() + timedelta(days=1 if t.weekday() < 4 else 7 - t.weekday())))
            elif t.time() < time(9, 30):
                out.add((sym, t.date()))
    return out


def _run(job):
    name, which, bps, skip_days, skip_sym = job
    r = backtest.run(replace(S, slippage_bps=bps), BARS[which], 10_000, skip_days, skip_sym)["summary"]
    return name, which, bps, r


def main():
    allbars = data.load_cache(S.symbols)
    BARS["y1"] = {k: [b for b in v if b.t.date() < SPLIT] for k, v in allbars.items()}
    BARS["y2"] = {k: [b for b in v if b.t.date() >= SPLIT] for k, v in allbars.items()}
    news_start = min(date.fromisoformat(x[0][:10]) for v in F["news"].values() for x in v) if F.get("news") else SPLIT
    BARS["recent"] = {k: [b for b in v if b.t.date() >= news_start] for k, v in allbars.items()}

    filters = {"none": (set(), set())}
    for j in (0.05, 0.10, 0.20):
        filters[f"fear>{int(j*100)}%"] = (vix_skip_days(j), set())
    filters["fed days"] = (calendar_days(["FOMC"]), set())
    filters["fed+cpi+jobs"] = (calendar_days(["FOMC", "CPI", "JOBS"]), set())
    jobs = [(n, w, bps, d, sy) for n, (d, sy) in filters.items() for w in ("y1", "y2") for bps in (5, 2)]
    ed = earnings_symbol_days()
    jobs += [(n, "recent", 5, set(), sy) for n, sy in (("none", set()), ("earnings skip", ed))]
    with Pool() as pool:
        res = pool.map(_run, jobs)
    print(f"news covers from {news_start}; earnings skip pairs: {len(ed)}")
    for name, which, bps, r in res:
        print(f"{name:<14} {which:<6} {bps}bps  ret {r['total_return_pct']:>6}%  dd {r['max_drawdown_pct']:>5}%  "
              f"trades {r['trades']:>4}  win {r['win_rate_pct']}%  pf {r['profit_factor']}")


if __name__ == "__main__":
    main()
