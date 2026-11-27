from bot.config import load_settings
from bot.risk import may_open_trade, position_size

S = load_settings("config.yaml")


def test_size_capped_by_risk():
    # $10k account, 0.5% risk = $50; $1 risk per share -> 50 shares, under 10% cap ($1000/ $10 = 100)
    assert position_size(S, 10_000, 10, 9) == 50


def test_size_capped_by_position_limit():
    # tiny stop would allow huge size; 10% cap at $100/share = 10 shares
    assert position_size(S, 10_000, 100, 99.99) == 10


def test_daily_loss_cap_blocks_trades():
    assert not may_open_trade(S, day_pnl_pct=-2.0, week_pnl_pct=-2.0, open_positions=0, trades_today=0)
    assert may_open_trade(S, day_pnl_pct=-1.0, week_pnl_pct=-1.0, open_positions=0, trades_today=0)
