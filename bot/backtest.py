"""Replay past 1-minute bars through the strategy and the risk limits.

Assumptions (deliberately pessimistic):
- Entries fill at the NEXT bar's open, not the signal price.
- Every fill is worse than the quoted price by slippage_bps.
- If one bar touches both the stop and the target, we assume the stop hit first.
- Everything is sold/covered at flatten time (3:50 PM ET); nothing is held overnight.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from bot import risk, strategy
from bot.config import Settings
from bot.strategy import Bar


@dataclass
class Position:
    symbol: str
    side: str
    qty: int
    stop: float
    target: float
    entry: Optional[float] = None  # None until filled at next bar open
    entry_time: Optional[datetime] = None


@dataclass
class Trade:
    symbol: str
    side: str
    qty: int
    entry_time: datetime
    entry: float
    exit_time: datetime
    exit: float
    reason: str

    @property
    def pnl(self) -> float:
        sign = 1 if self.side == "long" else -1
        return sign * (self.exit - self.entry) * self.qty


def _slip(s: Settings, price: float, buying: bool) -> float:
    f = s.slippage_bps / 10_000
    return price * (1 + f) if buying else price * (1 - f)


def _flatten_time(s: Settings) -> time:
    return (datetime.combine(date.min, time(16, 0)) - timedelta(minutes=s.flatten_minutes_before_close)).time()


def run(s: Settings, bars_by_symbol: dict[str, list[Bar]], start_equity: float = 10_000.0,
        skip_days: Optional[set] = None, skip_symbol_days: Optional[set] = None) -> dict:
    """bars_by_symbol: regular-session 1-minute bars per symbol (US/Eastern), any number of days.

    skip_days: dates with no new trades (calendar / market-mood filters).
    skip_symbol_days: (symbol, date) pairs to skip (e.g. earnings days)."""
    skip_days = skip_days or set()
    skip_symbol_days = skip_symbol_days or set()
    by_day: dict[date, dict[str, list[Bar]]] = defaultdict(lambda: defaultdict(list))
    for sym, bars in bars_by_symbol.items():
        for b in sorted(bars, key=lambda b: b.t):
            by_day[b.t.date()][sym].append(b)

    equity = start_equity
    trades: list[Trade] = []
    curve: list[tuple[date, float]] = []
    week_key, week_start_eq = None, equity
    flat_t = _flatten_time(s)

    for day in sorted(by_day):
        day_bars = by_day[day]
        wk = day.isocalendar()[:2]
        if wk != week_key:
            week_key, week_start_eq = wk, equity
        day_start_eq = equity
        positions: dict[str, Position] = {}
        traded_today: set[str] = set()
        seen: dict[str, list[Bar]] = defaultdict(list)
        vol_sum: dict[str, float] = defaultdict(float)
        mkt_pv = mkt_v = 0.0
        bias = None
        stopped = False
        last_px: dict[str, float] = {}
        timeline = sorted({b.t for bars in day_bars.values() for b in bars})
        index = {sym: {b.t: b for b in bars} for sym, bars in day_bars.items()}

        def close(p: Position, t: datetime, px: float, reason: str):
            nonlocal equity
            exit_px = _slip(s, px, buying=(p.side == "short"))
            tr = Trade(p.symbol, p.side, p.qty, p.entry_time, p.entry, t, exit_px, reason)
            equity += tr.pnl
            trades.append(tr)
            positions.pop(p.symbol, None)

        def mark() -> float:
            u = 0.0
            for p in positions.values():
                if p.entry is not None:
                    sign = 1 if p.side == "long" else -1
                    u += sign * (last_px.get(p.symbol, p.entry) - p.entry) * p.qty
            return equity + u

        for t in timeline:
            # 1. manage open positions
            for sym, p in list(positions.items()):
                b = index[sym].get(t)
                if b is None:
                    continue
                if p.entry is None:  # fill pending entry at this bar's open
                    p.entry = _slip(s, b.o, buying=(p.side == "long"))
                    p.entry_time = t
                if t.time() >= flat_t:
                    close(p, t, b.o, "close of day")
                    continue
                if p.side == "long":
                    if b.l <= p.stop:
                        close(p, t, min(p.stop, b.o), "stop")
                    elif b.h >= p.target:
                        close(p, t, max(p.target, b.o), "target")
                else:
                    if b.h >= p.stop:
                        close(p, t, max(p.stop, b.o), "stop")
                    elif b.l <= p.target:
                        close(p, t, min(p.target, b.o), "target")
            for sym in index:
                if t in index[sym]:
                    b = index[sym][t]
                    if seen[sym]:
                        vol_sum[sym] += seen[sym][-1].v
                    seen[sym].append(b)
                    last_px[sym] = b.c
                    if sym == s.market_symbol:
                        mkt_pv += (b.h + b.l + b.c) / 3 * b.v
                        mkt_v += b.v
                        bias = ("up" if b.c > mkt_pv / mkt_v else "down") if mkt_v > 0 else None

            # 2. daily loss cap
            day_pnl_pct = (mark() - day_start_eq) / day_start_eq * 100
            if not stopped and risk.daily_cap_hit(s, day_pnl_pct):
                for p in list(positions.values()):
                    if p.entry is None:
                        positions.pop(p.symbol)
                    else:
                        close(p, t, last_px[p.symbol], "daily loss cap")
                stopped = True
            if stopped or t.time() >= flat_t or day in skip_days:
                continue

            # 3. look for new trades
            week_pnl_pct = (mark() - week_start_eq) / week_start_eq * 100
            for sym in day_bars:
                if sym in positions or sym in traded_today or t not in index[sym] or (sym, day) in skip_symbol_days:
                    continue
                if not risk.may_open_trade(s, day_pnl_pct=day_pnl_pct, week_pnl_pct=week_pnl_pct,
                                           open_positions=len(positions), trades_today=len(traded_today)):
                    break
                sig = strategy.check(s, seen[sym], vol_sum[sym], bias)
                if sig is None:
                    continue
                qty = position_size_for(s, mark(), sig)
                exposure = sum(p.qty * last_px.get(p.symbol, 0) for p in positions.values())
                if qty <= 0 or not risk.fits_exposure(mark(), exposure, qty * sig.entry):
                    continue
                positions[sym] = Position(sym, sig.side, qty, sig.stop, sig.target)
                traded_today.add(sym)

        # end of data for the day: close anything left at its last price
        for p in list(positions.values()):
            if p.entry is not None:
                close(p, timeline[-1], last_px[p.symbol], "end of data")
        curve.append((day, equity))

    return {"trades": trades, "equity_curve": curve, "summary": summarize(trades, curve, start_equity)}


def position_size_for(s: Settings, equity: float, sig: strategy.Signal) -> int:
    return risk.position_size(s, equity, sig.entry, sig.stop)


def summarize(trades: list[Trade], curve: list[tuple[date, float]], start_equity: float) -> dict:
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]
    peak, max_dd = start_equity, 0.0
    for _, eq in curve:
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100)
    end_eq = curve[-1][1] if curve else start_equity
    return {
        "days": len(curve),
        "trades": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if trades else 0.0,
        "total_return_pct": round((end_eq - start_equity) / start_equity * 100, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(sum(wins) / -sum(losses), 2) if losses and sum(losses) < 0 else None,
        "long_trades": sum(1 for t in trades if t.side == "long"),
        "short_trades": sum(1 for t in trades if t.side == "short"),
        "end_equity": round(end_eq, 2),
    }
