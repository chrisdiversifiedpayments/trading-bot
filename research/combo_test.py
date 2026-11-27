"""Core funds + bots, mixed together and rebalanced monthly.

Core = 50% SPY + 50% VYM (dividends reinvested). VYM is used as the "typical" broad dividend fund,
not HDV, to avoid picking the best performer with hindsight.
Bots: dip-buy (2021 company list) and the day-trading bot (current config, sit-out filters on).
Day-trading data only covers Nov 2024-Nov 2026, so mixes with it use that window.
"""
import os
import sys
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, ".")
sys.argv = sys.argv[:1]
import dipbuy_plus as dp  # noqa: E402
from bot import backtest, data  # noqa: E402

ET = ZoneInfo("America/New_York")


def core_curve():
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    r = c.get_stock_bars(StockBarsRequest(symbol_or_symbols=["SPY", "VYM"], timeframe=TimeFrame.Day,
                                          start=datetime(2021, 5, 1, tzinfo=ET), end=datetime(2026, 11, 26, tzinfo=ET),
                                          feed=DataFeed.IEX, adjustment=Adjustment.ALL)).data
    return {s: {b.timestamp.astimezone(ET).date().isoformat(): b.close for b in r[s]} for s in ("SPY", "VYM")}


def rets(curve: dict) -> dict:
    ds = sorted(curve)
    return {d: curve[d] / curve[p] - 1 for p, d in zip(ds, ds[1:])}


def mix(parts, start, end):
    """parts: list of (weight, daily-return dict). Monthly rebalance."""
    days = sorted(set.intersection(*[set(r) for _, r in parts]))
    days = [d for d in days if start <= d <= end]
    vals = [w * 10_000 for w, _ in parts]
    curve, month = [], days[0][:7]
    for d in days:
        if d[:7] != month:
            tot = sum(vals)
            vals = [w * tot for w, _ in parts]
            month = d[:7]
        vals = [v * (1 + r[d]) for v, (_, r) in zip(vals, parts)]
        curve.append(sum(vals))
    yrs = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days / 365.25
    peak, dd = curve[0], 0
    for v in curve:
        peak = max(peak, v)
        dd = max(dd, 1 - v / peak)
    return 100 * ((curve[-1] / 10_000) ** (1 / yrs) - 1), 100 * dd


core = core_curve()
spy, vym = rets(core["SPY"]), rets(core["VYM"])
core_r = {d: 0.5 * spy[d] + 0.5 * vym[d] for d in spy if d in vym}
dip = {}
for bps in (5, 2):
    dp.simulate(None, False, exit_bps=bps)
    dip[bps] = rets(dp.simulate.last_curve)

import filter_test as ft  # noqa: E402
bars = data.load_cache(ft.S.symbols)
skip = ft.vix_skip_days(0.05) | ft.calendar_days(["FOMC", "CPI", "JOBS"])
day = {}
for bps in (5, 2):
    eqc = backtest.run(replace(ft.S, slippage_bps=bps), bars, 10_000, skip)["equity_curve"]
    c = {d.isoformat(): e for d, e in eqc}
    first = min(c)
    day[bps] = {**{first: 0.0}, **rets(c)}

for label, (a, b) in (("Jun 2021-Nov 2026", ("2021-06-01", "2026-11-26")), ("Nov 2024-Nov 2026", ("2024-11-27", "2026-11-26"))):
    print(f"=== {label}")
    for bps in (5, 2):
        rows = [("SPY only", [(1, spy)]), ("Core (50% SPY + 50% VYM)", [(1, core_r)]),
                ("80% core + 20% dip-buy", [(0.8, core_r), (0.2, dip[bps])]),
                ("25% core + 75% dip-buy", [(0.25, core_r), (0.75, dip[bps])]),
                ("100% dip-buy", [(1, dip[bps])])]
        if a >= "2024-11-27":
            rows += [("80% core + 10% dip + 10% day bot", [(0.8, core_r), (0.1, dip[bps]), (0.1, day[bps])]),
                     ("80% core + 20% day bot", [(0.8, core_r), (0.2, day[bps])]),
                     ("25% core + 37.5% dip + 37.5% day bot", [(0.25, core_r), (0.375, dip[bps]), (0.375, day[bps])])]
        for name, parts in rows:
            r, dd = mix(parts, a, b)
            print(f"  {bps}bps  {name:<36} yearly {r:5.1f}%  worst drop {dd:5.1f}%")
