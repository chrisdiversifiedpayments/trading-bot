from bot.backtest import run
from bot.config import load_settings
from tests.helpers import day_bars

S = load_settings("config.yaml")
RANGE = [100.0, 100.5, 99.5, 100.2] * 4
DAY_BARS = 390  # a full 9:30-4:00 session


def _day(after, vol_at_break=3000, rest_price=None, **kw):
    prices = RANGE[:15] + [100.3] + after
    prices += [rest_price or prices[-1]] * (DAY_BARS - len(prices))
    vols = [1000] * 16 + [vol_at_break] + [1000] * (len(prices) - 17)
    return day_bars(prices, vols, **kw)


def test_long_hits_target():
    bars = _day([101.0, 101.2, 102.0, 103.5])
    r = run(S, {"AAA": bars}, 10_000)
    t = r["trades"][0]
    assert t.side == "long" and t.reason == "target" and t.pnl > 0


def test_short_hits_stop():
    bars = _day([99.0, 99.2, 100.5])
    r = run(S, {"AAA": bars}, 10_000)
    t = r["trades"][0]
    assert t.side == "short" and t.reason == "stop" and t.pnl < 0
    # a stop-out loses about the 0.5% risk budget, not more than ~1%
    assert -100 < t.pnl < 0


def test_closed_before_end_of_day():
    bars = _day([101.0, 101.2])  # never reaches stop or target
    r = run(S, {"AAA": bars}, 10_000)
    assert r["trades"][0].reason == "close of day"
    assert r["trades"][0].exit_time.strftime("%H:%M") == "15:50"


def test_one_trade_per_symbol_per_day():
    bars = _day([101.0, 103.5, 100.3, 101.0])
    r = run(S, {"AAA": bars}, 10_000)
    assert len(r["trades"]) == 1
