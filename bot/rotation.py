"""Weekly top-risers rotation (paper only).

Each week ONE of 4 batches is redone: sell what that batch holds, then buy the 5 stocks from the
2021 large-company list that rose most over the last 21 trading days (equal money each). Each batch
therefore holds its picks for about 4 weeks. This is the strategy in research/movers_tranches.py.

State (which batch is next, what each batch holds) lives in data/rotation_state.json so it survives
between runs. Every order goes to data/journal.csv; every run adds a line to data/scorecard.csv
comparing the account with holding SPY.
"""
import csv
import json
import logging
import os
import time as systime
from dataclasses import dataclass
from datetime import date

import yaml

from research.universes import LARGE_2021

log = logging.getLogger("rotation")
STATE = "data/rotation_state.json"
JOURNAL = "data/journal.csv"
SCORECARD = "data/scorecard.csv"
JOURNAL_COLS = ["date", "batch", "side", "symbol", "qty", "ref_price", "fill_price", "slippage_bps", "status"]
SCORE_COLS = ["date", "equity", "spy_close", "bot_pct", "spy_pct", "batch_done", "picks", "note"]


@dataclass(frozen=True)
class RotationSettings:
    enabled: bool
    top: int
    look_days: int
    batches: int
    budget_pct: float
    max_changes_per_month: int


def load_rotation_settings(path: str = "rotation.yaml") -> RotationSettings:
    with open(path) as f:
        r = RotationSettings(**yaml.safe_load(f))
    if not 0 < r.budget_pct <= 100:
        raise SystemExit("budget_pct must be between 0 and 100 (no borrowing).")
    return r


def pick(closes: dict, spy_days: list, top: int, look: int) -> list:
    """closes: {symbol: {date_iso: close}}; spy_days: trading days (SPY), oldest first.
    Rank by close on the last day vs `look` trading days earlier, like the backtest."""
    if len(spy_days) <= look:
        return []
    d, d0 = spy_days[-1], spy_days[-1 - look]
    ranked = sorted(((c[d] / c[d0] - 1, s) for s, c in closes.items()
                     if s != "SPY" and d in c and d0 in c and c[d0] > 0), reverse=True)
    return [s for _, s in ranked[:top]]


def load_state(path: str = STATE) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"next_batch": 0, "batches": {}, "last_run_week": None, "start": None, "changes": []}


def save_state(st: dict, path: str = STATE) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(st, f, indent=2, sort_keys=True)


def _append(path: str, cols: list, rows: list) -> None:
    if not rows:
        return
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerows(rows)


def _slip(side: str, ref: float, fill: float) -> float:
    """Cost of the fill vs the price when the order was sent, in bps (positive = worse for us)."""
    if not ref or not fill:
        return 0.0
    x = (fill / ref - 1) * 1e4
    return round(x if side == "buy" else -x, 1)


def run_week(broker, r: RotationSettings, kill_switch_on: bool, today: date, state: dict,
             dry_run: bool = False) -> dict:
    """Redo one batch. Returns a summary dict. Safe to call more than once a week (second call does nothing)."""
    week = "%d-W%02d" % today.isocalendar()[:2]
    if not (r.enabled and kill_switch_on):
        return {"done": False, "why": "kill switch is off"}
    if state.get("last_run_week") == week:
        return {"done": False, "why": "already traded this week"}
    if not dry_run and not broker.market_open():
        return {"done": False, "why": "market closed today; the same batch runs next week"}

    closes = broker.daily_closes(LARGE_2021 + ["SPY"], days=r.look_days + 15)
    spy_days = sorted(closes.get("SPY", {}))
    picks = pick(closes, spy_days, r.top, r.look_days)
    if len(picks) < r.top:
        return {"done": False, "why": "not enough price data to rank stocks"}
    spy_close = closes["SPY"][spy_days[-1]]
    equity = broker.equity()
    if state.get("start") is None:
        state["start"] = {"date": str(today), "equity": equity, "spy_close": spy_close,
                          "budget": equity * r.budget_pct / 100}

    k = str(state.get("next_batch", 0) % r.batches)
    held = state["batches"].get(k, {}).get("holdings", {})
    journal, proceeds, note = [], 0.0, ""
    positions = broker.positions()

    # 1) sell what this batch holds (never more than the account actually has)
    for sym, qty in held.items():
        qty = min(qty, positions.get(sym, 0.0))
        if qty <= 0:
            continue
        ref = broker.last_price(sym)
        fill = {"status": "dry_run", "qty": qty, "price": ref} if dry_run else broker.sell(sym, qty)
        proceeds += fill["qty"] * (fill["price"] or ref)
        positions[sym] = positions.get(sym, 0.0) - fill["qty"]
        journal.append(dict(date=str(today), batch=k, side="sell", symbol=sym, qty=round(fill["qty"], 6),
                            ref_price=ref, fill_price=fill["price"], slippage_bps=_slip("sell", ref, fill["price"]),
                            status=fill["status"]))
    unsold = [j for j in journal if j["status"] not in ("filled", "dry_run")]
    if unsold:
        note = "some sells did not fill; buying skipped this week"
        picks_bought = {}
    else:
        # 2) buy the new picks: a new batch gets 1/batches of the budget; an old one reuses its proceeds
        money = proceeds if k in state["batches"] else state["start"]["budget"] / r.batches
        money = min(money, broker.cash() * 0.99)  # never borrow
        each = money / len(picks)
        picks_bought = {}
        for sym in picks:
            ref = broker.last_price(sym)
            if not ref or each < 1:
                continue
            fill = ({"status": "dry_run", "qty": each / ref, "price": ref} if dry_run
                    else broker.buy(sym, each, ref))
            if fill["qty"] > 0:
                picks_bought[sym] = picks_bought.get(sym, 0.0) + fill["qty"]
            journal.append(dict(date=str(today), batch=k, side="buy", symbol=sym, qty=round(fill["qty"], 6),
                                ref_price=ref, fill_price=fill["price"], slippage_bps=_slip("buy", ref, fill["price"]),
                                status=fill["status"]))

    start = state["start"]
    row = dict(date=str(today), equity=round(equity, 2), spy_close=spy_close,
               bot_pct=round((equity / start["equity"] - 1) * 100, 2),
               spy_pct=round((spy_close / start["spy_close"] - 1) * 100, 2),
               batch_done=k, picks=" ".join(picks), note=("DRY RUN " if dry_run else "") + note)
    if dry_run:
        return {"done": True, "dry_run": True, "batch": k, "picks": picks, "journal": journal, "score": row}

    state["batches"][k] = {"holdings": picks_bought, "bought": str(today)}
    state["next_batch"] = (int(k) + 1) % r.batches
    state["last_run_week"] = week
    _append(JOURNAL, JOURNAL_COLS, journal)
    _append(SCORECARD, SCORE_COLS, [row])
    return {"done": True, "batch": k, "picks": picks, "journal": journal, "score": row}


class AlpacaBroker:
    """Thin wrapper over Alpaca paper trading. paper=True is hard-coded."""

    def __init__(self, key: str, secret: str):
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient

        self.tc = TradingClient(key, secret, paper=True)
        self.dc = StockHistoricalDataClient(key, secret)
        self._frac = {}

    def market_open(self) -> bool:
        return bool(self.tc.get_clock().is_open)

    def equity(self) -> float:
        return float(self.tc.get_account().equity)

    def cash(self) -> float:
        return float(self.tc.get_account().cash)

    def positions(self) -> dict:
        return {p.symbol: float(p.qty) for p in self.tc.get_all_positions() if float(p.qty) > 0}

    def daily_closes(self, symbols: list, days: int) -> dict:
        """Completed daily closes only (today's unfinished bar is excluded)."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        et = ZoneInfo("America/New_York")
        today = datetime.now(et).replace(hour=0, minute=0, second=0, microsecond=0)
        out = {}
        for i in range(0, len(symbols), 50):
            req = StockBarsRequest(symbol_or_symbols=symbols[i:i + 50], timeframe=TimeFrame.Day,
                                   start=today - timedelta(days=days * 2), end=today, feed=DataFeed.SIP)
            for sym, bars in self.dc.get_stock_bars(req).data.items():
                out[sym] = {b.timestamp.astimezone(et).date().isoformat(): float(b.close) for b in bars
                            if b.timestamp.astimezone(et).date() < today.date()}
        return out

    def last_price(self, sym: str) -> float:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestTradeRequest

        t = self.dc.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=sym, feed=DataFeed.IEX))
        return float(t[sym].price)

    def _wait(self, order_id, timeout: int = 90) -> dict:
        for _ in range(timeout // 3):
            o = self.tc.get_order_by_id(order_id)
            if str(o.status).split(".")[-1].lower() in ("filled", "canceled", "rejected", "expired"):
                break
            systime.sleep(3)
        status = str(o.status).split(".")[-1].lower()
        return {"status": status, "qty": float(o.filled_qty or 0),
                "price": float(o.filled_avg_price) if o.filled_avg_price else None}

    def _order(self, sym: str, side: str, qty=None, notional=None) -> dict:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        req = MarketOrderRequest(symbol=sym, side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                                 time_in_force=TimeInForce.DAY, qty=qty, notional=notional)
        try:
            return self._wait(self.tc.submit_order(req).id)
        except Exception as e:  # noqa: BLE001 - log and move on; one bad symbol must not stop the run
            log.error("%s %s failed: %s", side, sym, e)
            return {"status": "error", "qty": 0.0, "price": None}

    def sell(self, sym: str, qty: float) -> dict:
        return self._order(sym, "sell", qty=round(qty, 6))

    def buy(self, sym: str, dollars: float, ref: float) -> dict:
        a = self.tc.get_asset(sym)
        if not a.tradable:
            return {"status": "not_tradable", "qty": 0.0, "price": None}
        if a.fractionable:
            return self._order(sym, "buy", notional=round(dollars, 2))
        whole = int(dollars // ref)
        return self._order(sym, "buy", qty=whole) if whole else {"status": "too_small", "qty": 0.0, "price": None}
