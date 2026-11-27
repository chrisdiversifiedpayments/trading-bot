from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.strategy import Bar

ET = ZoneInfo("America/New_York")


def day_bars(prices, volumes=None, day=(2026, 3, 2)):
    """1-minute bars from 9:30 ET. Each price p gives a bar with o=c=p, h=p+0.05, l=p-0.05."""
    start = datetime(*day, 9, 30, tzinfo=ET)
    volumes = volumes or [1000] * len(prices)
    return [Bar(start + timedelta(minutes=i), p, p + 0.05, p - 0.05, p, v)
            for i, (p, v) in enumerate(zip(prices, volumes))]
