"""Fetch 1-minute bars and headlines from Alpaca (free IEX feed). Needs paper keys in env."""
import csv
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.config import api_keys
from bot.strategy import Bar, MARKET_OPEN

ET = ZoneInfo("America/New_York")
CACHE = "data_cache"


def _regular_session(b: Bar) -> bool:
    return MARKET_OPEN <= b.t.time() < datetime.strptime("16:00", "%H:%M").time()


def fetch_bars(symbols: list[str], start: datetime, end: datetime) -> dict[str, list[Bar]]:
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    key, secret = api_keys()
    client = StockHistoricalDataClient(key, secret)
    out: dict[str, list[Bar]] = {}
    for sym in symbols:
        req = StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute, start=start, end=end,
                               feed=DataFeed.IEX, adjustment=Adjustment.ALL)
        raw = client.get_stock_bars(req).data.get(sym, [])
        bars = [Bar(r.timestamp.astimezone(ET), r.open, r.high, r.low, r.close, r.volume) for r in raw]
        out[sym] = [b for b in bars if _regular_session(b)]
    return out


def save_cache(bars: dict[str, list[Bar]]) -> None:
    os.makedirs(CACHE, exist_ok=True)
    for sym, rows in bars.items():
        with open(f"{CACHE}/{sym}.csv", "w", newline="") as f:
            w = csv.writer(f)
            for b in rows:
                w.writerow([b.t.isoformat(), b.o, b.h, b.l, b.c, b.v])


def load_cache(symbols: list[str]) -> dict[str, list[Bar]]:
    out = {}
    for sym in symbols:
        path = f"{CACHE}/{sym}.csv"
        if os.path.exists(path):
            with open(path) as f:
                out[sym] = [Bar(datetime.fromisoformat(r[0]), *map(float, r[1:])) for r in csv.reader(f)]
    return out


def recent_headlines(symbol: str, hours: int = 24) -> list[str]:
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest

    key, secret = api_keys()
    client = NewsClient(key, secret)
    req = NewsRequest(symbols=symbol, start=datetime.now(ET) - timedelta(hours=hours), limit=50)
    news = client.get_news(req)
    items = news.data.get("news", []) if hasattr(news, "data") else []
    return [n.headline for n in items]


def daily_closes(symbol: str, days: int = 40) -> list[float]:
    """Completed daily closes (oldest first), excluding today."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    key, secret = api_keys()
    now = datetime.now(ET)
    req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
                           start=now - timedelta(days=days), end=now, feed=DataFeed.IEX)
    bars = StockHistoricalDataClient(key, secret).get_stock_bars(req).data.get(symbol, [])
    return [b.close for b in bars if b.timestamp.astimezone(ET).date() < now.date()]
