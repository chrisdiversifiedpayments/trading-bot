"""Download 1-minute bars for each day's 10 biggest opening movers (2021 list), Nov 2024-Nov 2026."""
import json
import os
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from universes import LARGE_2021  # noqa: E402

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

ET = ZoneInfo("America/New_York")
W = json.load(open("data_cache/daily_wide_ohlc.json"))
px = {s: {r[0]: r[1:] for r in W[s]} for s in LARGE_2021 if s in W}
days = sorted({r[0] for r in W["SPY"]})
c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
out_path = "data_cache/movers_minute.json"
out = json.load(open(out_path)) if os.path.exists(out_path) else {}
for i in range(1, len(days)):
    d, p = days[i], days[i - 1]
    if d < "2024-11-27" or d in out:
        continue
    cands = sorted(((abs(x[d][0] / x[p][3] - 1), s) for s, x in px.items() if d in x and p in x), reverse=True)[:10]
    syms = [s for _, s in cands]
    day0 = datetime.fromisoformat(d).replace(tzinfo=ET)
    r = c.get_stock_bars(StockBarsRequest(symbol_or_symbols=syms, timeframe=TimeFrame.Minute,
                                          start=day0 + timedelta(hours=9, minutes=30), end=day0 + timedelta(hours=16),
                                          feed=DataFeed.IEX, adjustment=Adjustment.ALL)).data
    out[d] = {s: [[b.timestamp.astimezone(ET).strftime("%H:%M"), b.open, b.high, b.low, b.close, b.volume]
                  for b in r.get(s, [])] for s in syms}
    if i % 25 == 0:
        json.dump(out, open(out_path, "w"))
        print(d, flush=True)
json.dump(out, open(out_path, "w"))
print("done", len(out))
