"""Load settings and refuse to run anything but paper trading."""
import os
from dataclasses import dataclass, field
from datetime import time

import yaml


@dataclass(frozen=True)
class Settings:
    mode: str
    enabled: bool
    allow_short: bool
    use_margin: bool
    risk_per_trade_pct: float
    max_position_pct: float
    max_open_positions: int
    daily_loss_cap_pct: float
    weekly_loss_cap_pct: float
    max_trades_per_day: int
    flatten_minutes_before_close: int
    range_minutes: int
    volume_mult: float
    reward_risk: float
    last_entry_time: str
    slippage_bps: float
    symbols: list = field(default_factory=list)
    news_skip_words: list = field(default_factory=list)
    market_filter: bool = False
    market_symbol: str = "SPY"
    skip_calendar_days: bool = False
    fear_filter_pct: float = 0

    @property
    def last_entry(self) -> time:
        h, m = self.last_entry_time.split(":")
        return time(int(h), int(m))


def load_settings(path: str = "config.yaml") -> Settings:
    with open(path) as f:
        s = Settings(**yaml.safe_load(f))
    if s.mode != "paper" or os.environ.get("TRADING_MODE", "paper") != "paper":
        raise SystemExit("Live trading is disabled. Only paper mode is allowed.")
    if s.use_margin:
        raise SystemExit("use_margin must stay false.")
    return s


def api_keys() -> tuple[str, str]:
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("Alpaca paper keys are not set as secrets yet.")
    return key, secret
