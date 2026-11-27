# Weekly review: how the bot "watches, learns and adjusts"

The weekly scheduled task runs `python run_rotation.py` (paper only), then reviews. Rules:

## Watch (every week)
1. Read `docs/LEARNINGS.md`, this file, `data/scorecard.csv`, `data/journal.csv`.
2. Note in the "Live paper log" table of LEARNINGS.md: account % vs SPY % since start, this week's
   picks, average fill cost (slippage_bps) vs the 5 bps the backtest assumed, and anything odd
   (failed orders, a pick that jumped or crashed >25% in a day, missing data).

## Learn (keep a running tally)
3. Compare live results with what the backtest expects. One month of live results is mostly luck:
   the backtest's monthly results swing by about +/-6%. Do not react to a single week or month.
4. Re-run `research/movers_tranches.py` with fresh data once a month to see whether the edge still holds.

## Adjust (only within these guardrails)
5. Allowed to change, in `rotation.yaml` only: `top` (3-10), `look_days` (10-63), and, if fills keep
   costing more than 10 bps on average over 4+ weeks, the trade time of day.
6. A change needs ALL of: (a) a written reason in LEARNINGS.md, (b) a backtest where the new value
   beats the current one in BOTH halves of the 2016-now period after cautious costs, (c) at most
   `max_changes_per_month` changes in the last 30 days (logged in `rotation_state.json` "changes").
7. Never change: paper-only mode, the no-borrowing rule, `budget_pct`, the kill switches, risk limits,
   or the company list. Never add live keys or the live Alpaca address. Those need the owner.
8. Stop and tell the owner (and set `enabled: false` in rotation.yaml) if the account falls more than
   20% below where SPY would have put it, or if orders fail two weeks in a row.
