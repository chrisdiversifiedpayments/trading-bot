"""Run the strategy on past data.  Usage:  python backtest.py --years 2 [--start-equity 10000]"""
import argparse
import csv
from datetime import datetime, timedelta

from bot import backtest, data
from bot.config import load_settings

p = argparse.ArgumentParser()
p.add_argument("--years", type=float, default=2)
p.add_argument("--start-equity", type=float, default=10_000)
p.add_argument("--use-cache", action="store_true", help="reuse data_cache/ instead of downloading")
args = p.parse_args()

s = load_settings()
if args.use_cache:
    bars = data.load_cache(s.symbols)
else:
    end = datetime.now(data.ET) - timedelta(minutes=20)  # free data is delayed 15 minutes
    bars = data.fetch_bars(s.symbols, end - timedelta(days=365 * args.years), end)
    data.save_cache(bars)

result = backtest.run(s, bars, args.start_equity)
for k, v in result["summary"].items():
    print(f"{k:>18}: {v}")
with open("backtest_trades.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["symbol", "side", "qty", "entry_time", "entry", "exit_time", "exit", "reason", "pnl"])
    for t in result["trades"]:
        w.writerow([t.symbol, t.side, t.qty, t.entry_time, round(t.entry, 4), t.exit_time,
                    round(t.exit, 4), t.reason, round(t.pnl, 2)])
print("Trades saved to backtest_trades.csv")
