# Trading bot: instructions for Claude

Before doing ANY work in this repo, read `docs/LEARNINGS.md`. It holds every test result so far,
the testing rules to follow, and what has already been ruled out (and why). Update it whenever a new
test finishes, in the same commit as the code.

- Paper trading only. `paper=True` and `mode: paper` stay enforced. Never add live keys.
- API keys come from env vars `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`; never ask for them in chat or commit them.
- Run `python -m pytest -q tests` before pushing.
- The owner is not technical: report results in plain language, after costs, compared with holding SPY.
