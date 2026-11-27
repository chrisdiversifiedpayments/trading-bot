"""Load settings and refuse to run anything but paper trading."""
import os
from dataclasses import dataclass

import yaml

PAPER_URL = "https://paper-api.alpaca.markets"


@dataclass(frozen=True)
class Settings:
    mode: str
    long_only: bool
    use_margin: bool
    risk_per_trade_pct: float
    max_position_pct: float
    max_open_positions: int
    daily_loss_cap_pct: float
    weekly_loss_cap_pct: float
    max_trades_per_day: int
    flatten_minutes_before_close: int


def load_settings(path: str = "config.yaml") -> Settings:
    with open(path) as f:
        s = Settings(**yaml.safe_load(f))
    if s.mode != "paper" or os.environ.get("TRADING_MODE", "paper") != "paper":
        raise SystemExit("Live trading is disabled. Only paper mode is allowed.")
    return s


def api_keys() -> tuple[str, str]:
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("Alpaca paper keys are not set as secrets yet.")
    return key, secret
