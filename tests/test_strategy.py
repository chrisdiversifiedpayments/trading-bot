from dataclasses import replace

from bot.config import load_settings
from bot.strategy import check, news_says_skip
from tests.helpers import day_bars

# Fixed settings so tests don't change when config.yaml is tuned
S = replace(load_settings("config.yaml"), range_minutes=15, volume_mult=1.5, reward_risk=2.0,
            market_filter=False, max_trades_per_day=10)
RANGE = [100.0, 100.5, 99.5, 100.2] * 4  # 16 bars: range high 100.55, low 99.45, mid 100.0


def test_long_breakout_on_volume():
    bars = day_bars(RANGE[:15] + [100.3, 101.0], [1000] * 16 + [3000])
    sig = check(S, bars)
    assert sig.side == "long" and sig.stop == 100.0 and sig.target == 101.0 + 2 * 1.0


def test_short_breakout_on_volume():
    bars = day_bars(RANGE[:15] + [100.3, 99.0], [1000] * 16 + [3000])
    sig = check(S, bars)
    assert sig.side == "short" and sig.stop == 100.0 and sig.target == 99.0 - 2 * 1.0


def test_no_short_when_disabled():
    bars = day_bars(RANGE[:15] + [100.3, 99.0], [1000] * 16 + [3000])
    assert check(replace(S, allow_short=False), bars) is None


def test_no_signal_without_volume():
    bars = day_bars(RANGE[:15] + [100.3, 101.0])
    assert check(S, bars) is None


def test_no_signal_inside_opening_range():
    bars = day_bars(RANGE[:14] + [101.0], [1000] * 14 + [5000])
    assert check(S, bars) is None


def test_news_filter():
    assert news_says_skip(S, ["Apple beats on Earnings, shares jump"])
    assert not news_says_skip(S, ["Apple opens new store in Ohio"])


def test_market_filter_blocks_trades_against_the_market():
    bars = day_bars(RANGE[:15] + [100.3, 101.0], [1000] * 16 + [3000])
    on = replace(S, market_filter=True)
    assert check(on, bars, market_bias="down") is None
    assert check(on, bars, market_bias="up").side == "long"
    short_bars = day_bars(RANGE[:15] + [100.3, 99.0], [1000] * 16 + [3000])
    assert check(on, short_bars, market_bias="up") is None
    assert check(on, short_bars, market_bias="down").side == "short"


def test_fear_and_calendar_filters():
    from bot.strategy import calendar_skip, fear_is_high
    calm = [10.0] * 21
    assert not fear_is_high(calm, 5)
    assert fear_is_high([10.0] * 20 + [10.6], 5)
    assert not fear_is_high([10.0] * 20 + [10.6], 0)
    assert calendar_skip("2026-11-10", {"CPI": ["2026-11-10"]})
    assert not calendar_skip("2026-11-11", {"CPI": ["2026-11-10"]})
