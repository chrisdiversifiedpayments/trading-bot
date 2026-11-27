"""Options strategies on SPY, Feb 2024 - Nov 2026, using Alpaca's historical option prices (daily closes).

Each week, at Friday's close (or the last trading day of the week), open a position in options that
expire at the next week's last trading day; hold to expiration.
A. Sell a put about 2% below the price, fully cash-secured (income; you'd buy SPY if it falls).
B. Covered call: own SPY, sell a call about 2% above the price (income; gains capped).
C. Buy an at-the-money call with 5% of the account, only when SPY is above its 50-day average (leveraged bet).
D. Buy an at-the-money put with 5% of the account, only when SPY is below its 50-day average.
Fill prices: daily close, made worse by 5% of the option price (min $0.02) to stand in for the bid/ask gap.
Results are % per year of the money committed; compared with holding SPY (price + dividends).
"""
import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CACHE = "data_cache/options_spy.json"


def clients():
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    k, s = os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    return StockHistoricalDataClient(k, s), OptionHistoricalDataClient(k, s)


def spy_daily(sc, adj):
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    r = sc.get_stock_bars(StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame.Day, start=datetime(2023, 10, 1, tzinfo=ET),
                                           end=datetime(2026, 11, 26, tzinfo=ET), feed=DataFeed.IEX, adjustment=adj)).data["SPY"]
    return {b.timestamp.astimezone(ET).date().isoformat(): b.close for b in r}


def occ(exp: str, cp: str, strike: float) -> str:
    d = date.fromisoformat(exp)
    return f"SPY{d:%y%m%d}{cp}{int(round(strike * 1000)):08d}"


def main():
    from alpaca.data.enums import Adjustment
    from alpaca.data.requests import OptionBarsRequest
    from alpaca.data.timeframe import TimeFrame
    sc, oc = clients()
    raw = spy_daily(sc, Adjustment.RAW)
    tot = spy_daily(sc, Adjustment.ALL)
    days = sorted(raw)
    # last trading day of each week
    weeks = {}
    for d in days:
        y, w, _ = date.fromisoformat(d).isocalendar()
        weeks[(y, w)] = d
    ends = [weeks[k] for k in sorted(weeks)]
    ends = [d for d in ends if d >= "2024-02-09"]
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    def price(sym, d):
        key = f"{sym}|{d}"
        if key not in cache:
            try:
                b = oc.get_option_bars(OptionBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Day,
                                                         start=datetime.fromisoformat(d).replace(tzinfo=ET) - timedelta(days=3),
                                                         end=datetime.fromisoformat(d).replace(tzinfo=ET) + timedelta(hours=23))).data.get(sym, [])
                b = [x for x in b if x.timestamp.astimezone(ET).date().isoformat() == d]
                cache[key] = b[-1].close if b else None
            except Exception:
                cache[key] = None
        return cache[key]

    def bad(p, buying):
        slip = max(0.02, 0.05 * p)
        return p + slip if buying else max(p - slip, 0.0)

    res = {k: [] for k in "ABCDS"}
    for d0, d1 in zip(ends, ends[1:]):
        s0, s1 = raw[d0], raw[d1]
        i = days.index(d0)
        ma50 = sum(raw[x] for x in days[i - 49:i + 1]) / 50
        res["S"].append((d0, tot[d1] / tot[d0] - 1))
        # A: short put ~2% OTM
        k = float(int(s0 * 0.98))
        p = price(occ(d1, "P", k), d0)
        if p:
            prem = bad(p, False)
            res["A"].append((d0, (prem - max(0.0, k - s1)) / k))
        # B: covered call ~2% OTM
        k = float(int(s0 * 1.02) + 1)
        p = price(occ(d1, "C", k), d0)
        if p:
            prem = bad(p, False)
            res["B"].append((d0, (min(s1, k) - s0 + prem + (tot[d1] / tot[d0] - s1 / s0) * s0) / s0))
        # C/D: buy ATM call above MA50 / put below MA50, 5% of account
        k = float(round(s0))
        if s0 > ma50:
            p = price(occ(d1, "C", k), d0)
            if p:
                cost = bad(p, True)
                res["C"].append((d0, 0.05 * (max(0.0, s1 - k) - cost) / cost))
        else:
            p = price(occ(d1, "P", k), d0)
            if p:
                cost = bad(p, True)
                res["D"].append((d0, 0.05 * (max(0.0, k - s1) - cost) / cost))
    json.dump(cache, open(CACHE, "w"))

    names = {"S": "Hold SPY (comparison)", "A": "A. Sell weekly put 2% below", "B": "B. Covered call 2% above",
             "C": "C. Buy calls in uptrends (5%/wk)", "D": "D. Buy puts in downtrends (5%/wk)"}
    print(f"weeks: {len(ends) - 1}")
    for half, (a, b) in (("all", ("2024-02-09", "2026-12-31")), ("2024-25", ("2024-02-09", "2025-06-30")), ("2025-26", ("2025-07-01", "2026-12-31"))):
        print(f"== {half}")
        for k in "SABCD":
            rs = [r for d, r in res[k] if a <= d <= b]
            if not rs:
                continue
            eq, peak, dd = 1.0, 1.0, 0.0
            for r in rs:
                eq *= 1 + r
                peak = max(peak, eq)
                dd = max(dd, 1 - eq / peak)
            yrs = len([d for d, _ in res["S"] if a <= d <= b]) / 52
            print(f"  {names[k]:<36} per year {100 * (eq ** (1 / yrs) - 1):6.1f}%  worst drop {100 * dd:5.1f}%  "
                  f"weeks traded {len(rs)}  win weeks {100 * sum(r > 0 for r in rs) / len(rs):4.1f}%")


if __name__ == "__main__":
    main()
