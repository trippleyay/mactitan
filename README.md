# MacTitan

An AI-powered macro-quant research workbench for Bitget rToken traders.
Ask natural-language questions about how a stock has actually reacted,
historically, to real macro events (CPI, Fed rate decisions, jobs reports,
and more) — answered with real computed statistics from real data, not
narrated commentary.

## Status
Phase 0-2 (data layer + computation engine) built and tested for both:
- Portfolio Copilot foundation (price fetch, sector mapping, correlation/beta math)
- Macro-quant engine (real FRED macro data + real Bitget price reaction analysis)

## Stack
Python (computation), FRED API (free, real macro data), Bitget public API
(free, real rToken price data), LLM API for natural-language parsing and
explanation, web chat + Telegram interfaces (planned).

## Structure
- `data/sector_map.py` — static rToken ticker -> sector mapping (rToken-native naming)
- `core/price_fetch.py` — real rToken price history from Bitget (public, no key)
- `core/holdings_fetch.py` — real user holdings from Bitget (private, read-only key)
- `core/stats.py` — beta, correlation, sector-weight math
- `core/portfolio.py` — portfolio evaluation + universe diversification ranking
- `core/macro_data.py` — real macro event data from FRED (CPI, PCE, PPI, jobs,
  GDP, retail sales, sentiment, treasury yield, housing — free, no hardcoding)
- `core/event_reaction.py` — computes real stock price/volatility reactions
  around real macro event dates

## Setup
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in:
   - `FRED_API_KEY` — free at https://fred.stlouisfed.org/docs/api/api_key.html
   - `BITGET_API_KEY` / `SECRET` / `PASSPHRASE` — only needed for holdings_fetch (read-only key)
