"""Hard risk limits, checked before every order. Works for buys and short sales."""
from bot.config import Settings


def position_size(s: Settings, equity: float, entry: float, stop: float) -> int:
    """Shares so a stop-out loses at most risk_per_trade_pct, capped by max_position_pct."""
    per_share_risk = abs(entry - stop)
    if per_share_risk <= 0 or entry <= 0 or equity <= 0:
        return 0
    by_risk = (equity * s.risk_per_trade_pct / 100) / per_share_risk
    by_size = (equity * s.max_position_pct / 100) / entry
    return int(min(by_risk, by_size))


def may_open_trade(s: Settings, *, day_pnl_pct: float, week_pnl_pct: float,
                   open_positions: int, trades_today: int) -> bool:
    return (s.enabled
            and day_pnl_pct > -s.daily_loss_cap_pct
            and week_pnl_pct > -s.weekly_loss_cap_pct
            and open_positions < s.max_open_positions
            and trades_today < s.max_trades_per_day)


def fits_exposure(equity: float, current_exposure: float, new_value: float) -> bool:
    """No borrowing: the total value of all positions (longs and shorts) stays within equity."""
    return current_exposure + abs(new_value) <= equity


def daily_cap_hit(s: Settings, day_pnl_pct: float) -> bool:
    return day_pnl_pct <= -s.daily_loss_cap_pct
