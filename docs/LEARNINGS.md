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

## Combined setups (`research/combo_test.py`), core = 50% SPY + 50% VYM, monthly rebalance
| Mix | Jun 2021-Nov 2026 (cautious / low) | Nov 2024-Nov 2026 (cautious / low) | Worst drop |
| --- | --- | --- | --- |
| SPY only | 11.7% | 10.5% | 24.5% / 18.7% |
| Core funds only | 11.3% | 11.0% | 19.6% / 16.5% |
| 80% core + 20% dip-buy | 10.4% / 11.3% | 9.0% / 10.0% | ~17% |
| 80% core + 10% dip + 10% day bot | n/a | 9.8% / 10.5% | 13.4% |
| 25% core + 75% dip-buy | 7.6% / 10.8% | 3.2% / 6.4% | ~17% |
| 25% core + 37.5% dip + 37.5% day bot | n/a | 3.2% / 5.8% | 9.4% |
Adding bots lowers the worst drop a little but also lowers return. More bot money = less return.

## Risk level 75/100 (owner, 2026-11-26)
Config now: 1.5% risk/trade, 25% max position, 5 positions, 4% daily / 8% weekly cap, still no
borrowing, paper only. Day bot Y2: -4.0% cautious / +3.5% low, worst drop 9.6% (was -1.1% / +1.5%, 3.1%).
Y1: -6.3% / +0.7%. Higher risk magnifies swings, it does not add edge.

## Options (checked 2026-11-26)
Alpaca supports options trading on paper via API. Option-income funds as a proxy for selling options,
Jun 2021-Nov 2026: JEPI 7.6%/yr (worst drop 13.7%), XYLD 6.9%, QYLD 6.8% vs SPY 11.7%.
SPY weekly options test (`research/options_test.py`, Feb 2024-Nov 2026, Alpaca daily option closes,
fills worsened by 5% of option price, held to expiry). SPY hold = 14.9%/yr, worst drop 16.8%:
| Strategy | Per year | Worst drop | Winning weeks |
| --- | --- | --- | --- |
| Sell weekly put 2% below (cash-secured; cash interest not counted) | 5.2% | 6.5% | 92% |
| Covered call 2% above | 10.7% | 15.5% | 59% |
| Buy ATM calls in uptrends, 5% of account/week | -17.4% | 48.3% | 37% |
| Buy ATM puts in downtrends, 5%/week | -3.7% | 35.4% | 29% |
Selling options = smoother, less return. Buying short-dated options lost badly (time decay + spreads).
Not yet tested: 0DTE day-trading options (needs minute option data).

## Top movers (`research/movers_*.py`, 2021 large-company list), added 2026-11-26
- Day-trade the 10 biggest opening movers (with or against the move), Jun 2021-Nov 2026: -7% to -26%/yr
  cautious, -14% to +0.2% low. Gross edge ~0; 10 trades/day pay costs 10x.
- Breakout bot on only the 10 movers (minute data): Y1 -18.2% / -12.2%, Y2 -14.2% / -7.9% (cautious / low).
- Buy & hold the 5 biggest UP movers, rolling (`movers_hold.py`): best setting picked on Jun 2021-Dec 2023
  was "movers over the past month, hold 1 month": 24.2%/yr first half, 35.8% second half (SPY 6.4% / 16.8%).
  BUT very sensitive to which day of the month you rebalance: across 11 start days, first half -1.2% to
  24.7% (median 6.9%), second half 8.8% to 41.4% (median 26.2%). Drawdowns only measured monthly
  (understated). Second half rode the 2024-26 AI winners. Most promising lead so far; needs staggered
  rebalancing (split money into 4 weekly tranches) and paper trading before trusting it.
- Data caution: some IEX daily bars show huge one-day jumps (e.g. MRNA +177% on 2026-08-19) that may be
  glitches; dropping every name with a >25% day gave 13.2% / 36.5% for the same setting.

### Top-5 risers in 4 weekly batches (`research/movers_tranches.py`), daily-valued drawdowns
| Period | Strategy cautious / low | Worst drop | SPY | SPY worst drop |
| --- | --- | --- | --- | --- |
| Jun 2021-Nov 2026 | 20.2% / 21.1% | 34.3% | 11.6% | 24.5% |
| Jun 2021-Dec 2023 | 16.2% / 17.1% | 34.3% | 6.4% | 24.5% |
| 2024-Nov 2026 | 26.7% / 27.6% | 23.0% | 16.8% | 18.7% |
Neighbouring settings all beat SPY too (top 3: 26.6%, top 10: 13.7%, look 10d: 15.9%, look 42d: 12.7%,
hold 10d: 19.7%, hold 42d: 13.4%), always with bigger worst drops (33-39%). Dropping every name with a
>25% one-day move: 15.1% (5.4% in 2021-23, 25.8% in 2024-26). First strategy to beat SPY in a fair test;
it is concentrated (5 stocks) and riskier. Only trades weekly, so it can run on a scheduled job.

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
