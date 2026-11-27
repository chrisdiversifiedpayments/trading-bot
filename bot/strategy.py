"""Opening-range breakout, in plain terms:

1. Note the highest and lowest price in the first 15 minutes after the 9:30 ET open.
2. If a later 1-minute bar closes ABOVE that high on heavy volume, buy.
   If it closes BELOW that low on heavy volume, short-sell (when allowed).
3. Stop-loss sits at the middle of the opening range. Profit target = 2x that distance.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

from bot.config import Settings

MARKET_OPEN = time(9, 30)


@dataclass(frozen=True, slots=True)
class Bar:
    t: datetime  # bar start, US/Eastern
    o: float
    h: float
    l: float
    c: float
    v: float


@dataclass(frozen=True)
class Signal:
    side: str  # "long" or "short"
    entry: float
    stop: float
    target: float


def range_end(s: Settings) -> time:
    return (datetime.combine(datetime.min, MARKET_OPEN) + timedelta(minutes=s.range_minutes)).time()


def check(s: Settings, bars: list[Bar], prior_volume_sum: Optional[float] = None,
          market_bias: Optional[str] = None) -> Optional[Signal]:
    """bars = today's regular-session 1-minute bars so far, oldest first. Looks only at the latest bar.

    prior_volume_sum (optional) = total volume of bars[:-1], passed in by the backtester for speed.
    market_bias = "up" / "down" from market_bias(); with market_filter on, trades only go with the market."""
    if len(bars) < 2:
        return None
    end = range_end(s)
    last = bars[-1]
    if not (end <= last.t.time() < s.last_entry):
        return None
    opening = [b for b in bars[: s.range_minutes + 1] if MARKET_OPEN <= b.t.time() < end]
    if len(opening) < s.range_minutes * 0.6:  # too many missing bars to trust the range
        return None
    if prior_volume_sum is None:
        prior_volume_sum = sum(b.v for b in bars[:-1])
    avg_vol = prior_volume_sum / (len(bars) - 1)
    if avg_vol <= 0 or last.v < s.volume_mult * avg_vol:
        return None
    hi, lo = max(b.h for b in opening), min(b.l for b in opening)
    mid = (hi + lo) / 2
    want_long = not s.market_filter or market_bias == "up"
    want_short = not s.market_filter or market_bias == "down"
    if last.c > hi and want_long:
        risk = last.c - mid
        return Signal("long", last.c, mid, last.c + s.reward_risk * risk)
    if s.allow_short and want_short and last.c < lo:
        risk = mid - last.c
        return Signal("short", last.c, mid, last.c - s.reward_risk * risk)
    return None


def news_says_skip(s: Settings, headlines: list[str]) -> bool:
    text = " ".join(headlines).lower()
    return any(w in text for w in s.news_skip_words)


def market_bias(market_bars: list[Bar]) -> Optional[str]:
    """'up' if the market (SPY) trades above its average price so far today (VWAP), else 'down'."""
    vol = sum(b.v for b in market_bars)
    if not market_bars or vol <= 0:
        return None
    vwap = sum((b.h + b.l + b.c) / 3 * b.v for b in market_bars) / vol
    return "up" if market_bars[-1].c > vwap else "down"
