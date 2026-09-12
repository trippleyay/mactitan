# DrFolio

An AI portfolio copilot for Bitget rToken traders. Before you add a new
position, DrFolio shows you exactly how it reshapes your portfolio's risk —
beta, sector concentration, and correlation to what you already hold — using
your real positions and real Bitget price data.

## Status
Early build — Phase 0/1 (data layer) in progress.

## Stack
Python (price/portfolio computation), LLM API for natural-language
parsing and explanation, web chat + Telegram bot interfaces.

## Structure
- `data/` — static reference data (sector mapping)
- `core/` — price fetching, holdings fetching, portfolio math
- `tests/` — test scripts for the computation engine
