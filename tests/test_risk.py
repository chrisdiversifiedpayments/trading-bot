from dataclasses import replace
from bot.config import load_settings
from bot.risk import fits_exposure, may_open_trade, position_size

# Fixed settings so tests don't change when config.yaml is tuned
S = replace(load_settings("config.yaml"), range_minutes=15, volume_mult=1.5, reward_risk=2.0,
            market_filter=False, max_trades_per_day=10, risk_per_trade_pct=0.5, max_position_pct=10,
            max_open_positions=3, daily_loss_cap_pct=2, weekly_loss_cap_pct=5)


def test_size_capped_by_risk():
    # $10k account, 0.5% risk = $50; $1 risk per share -> 50 shares (under the 10% cap of 100)
    assert position_size(S, 10_000, 10, 9) == 50


def test_short_size_uses_distance_above():
    assert position_size(S, 10_000, 10, 11) == 50


def test_size_capped_by_position_limit():
    assert position_size(S, 10_000, 100, 99.99) == 10


def test_daily_loss_cap_blocks_trades():
    assert not may_open_trade(S, day_pnl_pct=-2.0, week_pnl_pct=-2.0, open_positions=0, trades_today=0)
    assert may_open_trade(S, day_pnl_pct=-1.0, week_pnl_pct=-1.0, open_positions=0, trades_today=0)


def test_weekly_cap_and_position_count():
    assert not may_open_trade(S, day_pnl_pct=0, week_pnl_pct=-5.0, open_positions=0, trades_today=0)
    assert not may_open_trade(S, day_pnl_pct=0, week_pnl_pct=0, open_positions=3, trades_today=0)
    assert not may_open_trade(S, day_pnl_pct=0, week_pnl_pct=0, open_positions=0, trades_today=10)


def test_no_borrowing():
    assert fits_exposure(10_000, 9_000, 1_000)
    assert not fits_exposure(10_000, 9_500, -1_000)
