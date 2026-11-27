"""Paper-trading loop. Runs all day; trades only while the market is open.

Every minute during market hours it:
  1. stops and closes everything if the kill switch is off, the daily loss cap is hit,
     or 3 errors happen in a row;
  2. closes everything at 3:50 PM ET;
  3. otherwise checks each watch-list stock for a breakout and places a bracket order
     (entry + stop-loss + profit target sent together, so the stop lives at Alpaca
     even if this program crashes).
"""
import json
import logging
import os
import time as systime
from datetime import date, datetime, timedelta

from bot import data, risk, strategy
from bot.backtest import _flatten_time
from bot.config import api_keys, load_settings

log = logging.getLogger("bot")
STATE_FILE = "state.json"


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(st: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(st, f)


class Trader:
    def __init__(self):
        from alpaca.trading.client import TradingClient

        self.s = load_settings()
        key, secret = api_keys()
        self.tc = TradingClient(key, secret, paper=True)  # paper=True is hard-coded on purpose
        self.state = _load_state()
        self.errors = 0

    # ---------- helpers ----------
    def close_all(self, why: str) -> None:
        log.warning("Closing all positions: %s", why)
        self.tc.close_all_positions(cancel_orders=True)

    def new_day(self, today: date) -> None:
        if self.state.get("day") == str(today):
            return
        wk = list(today.isocalendar()[:2])
        acct = self.tc.get_account()
        if self.state.get("week") != wk:
            self.state["week"], self.state["week_start_equity"] = wk, float(acct.last_equity)
        self.state.update(day=str(today), traded=[], stopped=False, skip=[])
        # morning news check
        for sym in self.s.symbols:
            try:
                if strategy.news_says_skip(self.s, data.recent_headlines(sym)):
                    self.state["skip"].append(sym)
            except Exception as e:  # news is a filter; a failure here should not stop trading
                log.warning("News check failed for %s: %s", sym, e)
        log.info("New day %s. Skipping on news: %s", today, self.state["skip"])
        _save_state(self.state)

    # ---------- one pass ----------
    def tick(self) -> None:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest

        s = load_settings()  # re-read each minute so the on/off switch takes effect quickly
        self.s = s
        now = datetime.now(data.ET)
        self.new_day(now.date())
        st = self.state

        if not s.enabled:
            if not st.get("stopped"):
                self.close_all("kill switch is off")
                st["stopped"] = True
                _save_state(st)
            return
        if st.get("stopped"):
            return
        if now.time() >= _flatten_time(s):
            if self.tc.get_all_positions():
                self.close_all("end of day")
            return

        acct = self.tc.get_account()
        equity, last_eq = float(acct.equity), float(acct.last_equity)
        day_pnl = (equity - last_eq) / last_eq * 100
        week_pnl = (equity - st["week_start_equity"]) / st["week_start_equity"] * 100
        if risk.daily_cap_hit(s, day_pnl):
            self.close_all(f"daily loss cap hit ({day_pnl:.2f}%)")
            st["stopped"] = True
            _save_state(st)
            return

        positions = self.tc.get_all_positions()
        held = {p.symbol for p in positions}
        exposure = sum(abs(float(p.market_value)) for p in positions)
        candidates = [x for x in s.symbols if x not in held and x not in st["traded"] and x not in st["skip"]]
        if not candidates:
            return
        start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        bars = data.fetch_bars(sorted(set(candidates) | {s.market_symbol}), start, now)
        bias = strategy.market_bias(bars.get(s.market_symbol, []))

        for sym in candidates:
            if not risk.may_open_trade(s, day_pnl_pct=day_pnl, week_pnl_pct=week_pnl,
                                       open_positions=len(held), trades_today=len(st["traded"])):
                break
            sig = strategy.check(s, bars.get(sym, []), market_bias=bias)
            if sig is None:
                continue
            if sig.side == "short":
                asset = self.tc.get_asset(sym)
                if not (acct.shorting_enabled and asset.shortable and asset.easy_to_borrow):
                    log.info("Skip short %s: shorting not available", sym)
                    continue
            qty = risk.position_size(s, equity, sig.entry, sig.stop)
            if qty <= 0 or not risk.fits_exposure(equity, exposure, qty * sig.entry):
                continue
            order = MarketOrderRequest(
                symbol=sym, qty=qty, time_in_force=TimeInForce.DAY,
                side=OrderSide.BUY if sig.side == "long" else OrderSide.SELL,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round(sig.target, 2)),
                stop_loss=StopLossRequest(stop_price=round(sig.stop, 2)),
            )
            self.tc.submit_order(order)
            log.info("%s %s x%d @~%.2f stop %.2f target %.2f", sig.side.upper(), sym, qty,
                     sig.entry, sig.stop, sig.target)
            st["traded"].append(sym)
            held.add(sym)
            exposure += qty * sig.entry
            _save_state(st)

    # ---------- main loop ----------
    def run_forever(self) -> None:
        log.info("Bot started (paper trading).")
        while True:
            try:
                clock = self.tc.get_clock()
                if not clock.is_open:
                    wait = (clock.next_open - clock.timestamp).total_seconds()
                    systime.sleep(min(max(wait, 30), 3600))
                    continue
                self.tick()
                self.errors = 0
            except Exception as e:
                self.errors += 1
                log.exception("Error %d in a row: %s", self.errors, e)
                if self.errors >= 3:
                    try:
                        self.close_all("3 errors in a row")
                    finally:
                        raise SystemExit("Stopped after repeated errors.")
            # wake a few seconds after each new minute, when the last bar is complete
            systime.sleep(60 - datetime.now().second + 5)
