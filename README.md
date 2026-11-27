# Trading bot (paper trading only)

An automated day-trading bot for an Alpaca account. **Paper trading only** until the
go-live checklist in the plan is passed and the owner approves.

Plan: https://claude.ai/artifact/BtH4JptKe2Pjh4nGPkkXWn

## What it does
Opening-range breakout on 20 large, heavily traded stocks and ETFs (`config.yaml`):
buys when a stock breaks above its first-15-minute range on heavy volume, short-sells
when it breaks below, with a stop-loss and a 2x profit target on every trade.
Skips stocks with major news that day. Closes everything at 3:50 PM ET.

## Safety
- Paper only: `mode: paper` is enforced in code, and the Alpaca client is created with `paper=True`.
- Risk limits live in `config.yaml` and are checked before every order
  (0.5% risk per trade, 10% max position, 3 positions, 2% daily and 5% weekly loss caps, 10 trades/day).
- No borrowing: total positions never exceed account value.
- Kill switch: set `enabled: false` in `config.yaml`; the bot closes everything within a minute.
  It also stops itself after 3 errors in a row.
- Stop-loss orders are placed at Alpaca with each entry, so they work even if the bot crashes.

## Keys
Never committed. Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` (paper keys) as secrets on the server.

## Commands
    pip install -r requirements.txt
    python -m pytest -q tests           # tests, no keys needed
    python backtest.py --years 2        # test on past prices (needs paper keys)
    python run.py                       # paper trading loop (needs paper keys)
