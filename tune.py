"""Tune strategy settings on year 1 only, then check the best few on year 2 (never seen while tuning).

Usage:  python tune.py --split 2025-11-27
Needs data_cache/ from `python backtest.py --years 2`.
"""
import argparse
import itertools
from dataclasses import replace
from datetime import date
from multiprocessing import Pool

from bot import backtest, data
from bot.config import load_settings

GRID = {
    "range_minutes": [15, 30],
    "volume_mult": [1.5, 2.5, 4.0],
    "market_filter": [False, True],
    "max_trades_per_day": [3, 10],
    "reward_risk": [1.5, 2.0, 3.0],
}

S = load_settings()
BARS = {}


def _split(bars, split, first):
    return {k: [b for b in v if (b.t.date() < split) == first] for k, v in bars.items()}


def _run(args):
    params, which = args
    s = replace(S, **params)
    return params, backtest.run(s, BARS[which], 10_000)["summary"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="2025-11-27")
    p.add_argument("--top", type=int, default=5)
    a = p.parse_args()
    split = date.fromisoformat(a.split)
    allbars = data.load_cache(S.symbols)
    BARS["y1"], BARS["y2"] = _split(allbars, split, True), _split(allbars, split, False)

    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    with Pool() as pool:
        y1 = pool.map(_run, [(c, "y1") for c in combos])
    y1.sort(key=lambda r: r[1]["total_return_pct"], reverse=True)
    print(f"YEAR 1 (tuning, before {split}): best {a.top} of {len(combos)}")
    for params, sm in y1[: a.top]:
        print(" ", params, sm)
    with Pool() as pool:
        y2 = pool.map(_run, [(params, "y2") for params, _ in y1[: a.top]])
    print(f"YEAR 2 (check, from {split}) for those same settings")
    for params, sm in y2:
        print(" ", params, sm)
    worst = y1[-1]
    print("Year 1 worst setting:", worst[0], worst[1]["total_return_pct"])


if __name__ == "__main__":
    main()
