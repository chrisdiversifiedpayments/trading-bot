from dataclasses import replace

from bot.config import load_settings
from bot.strategy import check, news_says_skip
from tests.helpers import day_bars

S = load_settings("config.yaml")
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
