# Learnings: read this before any work on the trading bot

Last updated 2026-11-27. Everything below was backtested; numbers are after trading costs unless noted.
"Cautious" cost = 0.05% per fill, "low" = 0.02% per fill. Plan doc with full tables:
https://claude.ai/artifact/BtH4JptKe2Pjh4nGPkkXWn

## Bottom line
Nothing tested so far beats simply holding SPY (11.7%/yr, Jun 2021-Nov 2026, worst drop 24.5%).
Dividend funds gave the smoothest ride (HDV 12.3%/yr, VYM 10.6%, SCHD 9.8%, worst drops 15-17%).
Trading costs decide almost every result.

## Rules for testing (keep doing this)
1. Always include costs; show cautious and low.
2. Tune on one period, judge on a later period the tuning never saw.
3. No survivorship bias: use `research/universes.py` `LARGE_2021` (stocks as they stood in 2021, incl.
   delisted), not today's winners. The 20-symbol list in `config.yaml` made dip-buy look twice as good.
4. Value open positions at the last known price, never a later one (a lookahead bug happened once).
5. Always compare against holding SPY and dividend funds over the same dates.

## Day trading: opening-range breakout (`bot/`, `backtest.py`, `tune.py`, `filter_test.py`)
| Version | Test period | Cautious | Low |
| --- | --- | --- | --- |
| v1 (15m range, 10 trades/day) | Nov 2024-Nov 2026 | -17.0% | -2.8% |
| Tuned (30m range, 2.5x volume, 3/day, 1.5x target, SPY direction filter) | Year 2 (unseen) | -2.9% | +0.1% |
| + sit-out filters (Fed/CPI/jobs days, VIXY > 5% over 20-day avg) | Year 2 | -1.1% | +1.5% |
| Same, 25% of account per trade, 2/day | Year 2 | -3.2% | +2.0% |
| Same, 50% per trade, 2/day | Year 2 | -6.4% | +4.1% |

Why it can't do better: gross edge is ~0.06% per trade; a round trip costs 0.04-0.10%. Buys earned
0.10%/trade gross, shorts only 0.02%. Bigger bets magnify, they don't add edge. Earnings-day skip:
no effect, but only 7 months of Alpaca news existed to test it.

## Swing / other strategies (`research/`), Jun 2021-Nov 2026, 2021 company list
| Strategy | Per year | Worst drop |
| --- | --- | --- |
| Hold SPY | 11.7% | 24.5% |
| Dip-buy (RSI(2) < 10 above 200-day avg, exit above 5-day avg or 10 days), low cost | 10.6% | 17.5% |
| Dip-buy, cautious cost | 6.4% | 18.2% |
| Dip-buy with limit entry 1% below close | 5.2% (unstable: 2.3% then 9.0%) | 14.5% |
| Dip-buy + idle cash in SPY | 5.6% (bot is ~86% invested; SPY churn costs) | 24.8% |
| Monthly momentum, top 5 | 3.4% | 42.0% |
| Pairs trading (12m pick / 6m trade) | -2.1% | 14.5% |
| Grid, day-only, index funds (Y1 / Y2) | -3.0% / -1.7% | 4.8% |
| Grid, multi-day, index funds (Y1 / Y2) | +9.0% / +2.1% vs hold +11.7% / +6.6% | 25.0% |

## Signals researched (not all tested yet)
- Political headlines: Alpaca news (free, history from ~Apr 2026 only on this account). Use as a pause rule.
- Crowd mood: ApeWisdom / Reddit API (free, little history) -> record during paper trading.
- Insider buying: SEC EDGAR Form 4 (free, filed within 2 business days). Needs a contact email: ask the owner.
- Congress trades: Quiver $30/mo, filed up to 45 days late -> not useful for day trading.
- Truth Social instant feed: $60-100k/month -> out.
- Options flow needs paid real-time data; short interest and 13F are too slow.

## Open items
Always-on server for paper trading (owner must sign up, ~$5-10/mo), nightly email report card,
sector-leaders test, dividend-capture test, proper earnings calendar, insider/sentiment tests.
Paper trading only; never add live keys or the live Alpaca host without the owner's explicit go-ahead.
