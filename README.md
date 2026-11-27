# Trading bot (paper trading only)

An automated day-trading bot for an Alpaca account. **Paper trading only** until the
go-live checklist in the plan is passed and the owner approves.

Plan: https://claude.ai/artifact/BtH4JptKe2Pjh4nGPkkXWn

## Status
Skeleton only. The strategy is not built yet; it waits on the six decisions in the plan.

## Keys
Alpaca keys are never committed. They are read from environment variables
(`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) set as secrets on the server.
See `.env.example` for names only.
