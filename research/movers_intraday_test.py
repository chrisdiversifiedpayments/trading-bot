"""Run the day-trading breakout bot on only each day's 10 biggest opening movers (Nov 2024-Nov 2026).

Uses current config.yaml (risk level 75, sit-out filters), SPY bars for the market-direction filter.
Years split at 2025-11-27 like the other day-trading tests.
"""
import json
import sys
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")
import filter_test as ft  # noqa: E402
from bot import backtest, data  # noqa: E402
from bot.strategy import Bar  # noqa: E402

ET = ZoneInfo("America/New_York")
M = json.load(open("data_cache/movers_minute.json"))
bars = {}
for d, by_sym in M.items():
    for s, rows in by_sym.items():
        for t, o, h, l, c, v in rows:
            bars.setdefault(s, []).append(Bar(datetime.fromisoformat(f"{d}T{t}").replace(tzinfo=ET), o, h, l, c, v))
spy = data.load_cache(["SPY"])["SPY"]
mover_days = set(M)
bars["SPY"] = [b for b in spy if b.t.date().isoformat() in mover_days]
skip = ft.vix_skip_days(0.05) | ft.calendar_days(["FOMC", "CPI", "JOBS"])
S = ft.S
# SPY is only there for the direction filter: never trade it here
spy_only_days = {(("SPY"), b.t.date()) for b in bars["SPY"]}
for label, keep in (("year 1", lambda d: d < ft.SPLIT), ("year 2", lambda d: d >= ft.SPLIT)):
    sub = {k: [b for b in v if keep(b.t.date())] for k, v in bars.items()}
    for filt in (True, False):
        for bps in (5, 2):
            r = backtest.run(replace(S, slippage_bps=bps), sub, 10_000, skip if filt else set(), spy_only_days)["summary"]
            print(f"{label} {'sit-out on ' if filt else 'sit-out off'} {bps}bps  return {r['total_return_pct']:6.1f}%  "
                  f"worst drop {r['max_drawdown_pct']:5.1f}%  trades {r['trades']}  win {r['win_rate_pct']}%")
