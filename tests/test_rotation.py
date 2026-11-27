from datetime import date

import pytest

from bot import rotation
from bot.rotation import RotationSettings, pick, run_week

R = RotationSettings(enabled=True, top=2, look_days=3, batches=4, budget_pct=100, max_changes_per_month=1)
DAYS = ["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23"]


def series(start, end):
    step = (end - start) / 4
    return {d: start + step * i for i, d in enumerate(DAYS)}


class FakeBroker:
    def __init__(self, open_=True):
        self.open_, self.cash_, self.pos, self.orders = open_, 100_000.0, {}, []
        self.closes = {"SPY": series(500, 510), "AAPL": series(100, 130), "MSFT": series(100, 90),
                       "NVDA": series(100, 120), "KO": series(100, 101)}

    def market_open(self): return self.open_
    def equity(self): return 100_000.0
    def cash(self): return self.cash_
    def positions(self): return dict(self.pos)
    def daily_closes(self, symbols, days): return self.closes
    def last_price(self, sym): return 50.0

    def sell(self, sym, qty):
        self.orders.append(("sell", sym, qty))
        self.pos[sym] -= qty
        self.cash_ += qty * 50
        return {"status": "filled", "qty": qty, "price": 50.0}

    def buy(self, sym, dollars, ref):
        self.orders.append(("buy", sym, dollars))
        self.pos[sym] = self.pos.get(sym, 0) + dollars / 50
        self.cash_ -= dollars
        return {"status": "filled", "qty": dollars / 50, "price": 50.1}


@pytest.fixture(autouse=True)
def tmp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(rotation, "JOURNAL", str(tmp_path / "j.csv"))
    monkeypatch.setattr(rotation, "SCORECARD", str(tmp_path / "s.csv"))


def fresh():
    return {"next_batch": 0, "batches": {}, "last_run_week": None, "start": None, "changes": []}


def test_pick_ranks_by_gain_and_ignores_spy():
    b = FakeBroker()
    assert pick(b.closes, DAYS, 2, 3) == ["AAPL", "NVDA"]


def test_first_week_buys_a_quarter_of_the_account():
    b, st = FakeBroker(), fresh()
    out = run_week(b, R, True, date(2026, 11, 24), st)
    assert out["done"] and out["picks"] == ["AAPL", "NVDA"]
    assert sum(x[2] for x in b.orders) == pytest.approx(25_000)
    assert st["next_batch"] == 1 and set(st["batches"]["0"]["holdings"]) == {"AAPL", "NVDA"}
    assert out["journal"][0]["slippage_bps"] == 20.0  # paid 50.10 vs 50.00


def test_second_run_same_week_does_nothing():
    b, st = FakeBroker(), fresh()
    run_week(b, R, True, date(2026, 11, 24), st)
    out = run_week(b, R, True, date(2026, 11, 25), st)
    assert not out["done"] and len(b.orders) == 2


def test_batch_comes_back_after_four_weeks_and_sells_first():
    b, st = FakeBroker(), fresh()
    for wk in range(5):
        run_week(b, R, True, date(2026, 11, 2 + 7 * wk), st)
    sells = [o for o in b.orders if o[0] == "sell"]
    assert {o[1] for o in sells} == {"AAPL", "NVDA"} and st["next_batch"] == 1
    assert b.cash_ >= 0


def test_kill_switch_and_closed_market_stop_trading():
    b = FakeBroker()
    assert not run_week(b, R, False, date(2026, 11, 24), fresh())["done"]
    off = RotationSettings(**{**R.__dict__, "enabled": False})
    assert not run_week(b, off, True, date(2026, 11, 24), fresh())["done"]
    assert not run_week(FakeBroker(open_=False), R, True, date(2026, 11, 24), fresh())["done"]
    assert b.orders == []


def test_dry_run_sends_nothing_and_saves_nothing():
    b, st = FakeBroker(), fresh()
    out = run_week(b, R, True, date(2026, 11, 24), st, dry_run=True)
    assert out["done"] and b.orders == [] and st["batches"] == {} and st["last_run_week"] is None
    assert run_week(FakeBroker(open_=False), R, True, date(2026, 11, 24), fresh(), dry_run=True)["done"]


def test_never_spends_more_than_cash():
    b, st = FakeBroker(), fresh()
    b.cash_ = 1_000
    run_week(b, R, True, date(2026, 11, 24), st)
    assert sum(x[2] for x in b.orders if x[0] == "buy") <= 1_000
