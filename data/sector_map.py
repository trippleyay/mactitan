"""
Static rToken ticker -> sector mapping, using Bitget's native rToken naming
(e.g. "rAAPL", not "AAPL") as the canonical key throughout this codebase —
this is a Bitget-specific product, so there's no reason to strip and re-add
the "r" prefix internally.

This list is not exhaustive (Bitget supports 500+ rTokens) — it covers
liquid, well-known names across major GICS sectors, which is realistically
what most retail portfolios will actually hold. Extend as needed.

IMPORTANT: ticker availability should be spot-checked against Bitget's live
/api/v2/spot/market/instruments endpoint before assuming any specific rToken
is actually tradable — this list is built from known real-equity sector
classifications, not scraped from Bitget's live catalog directly.
"""

SECTOR_MAP = {
    # Technology
    "rAAPL": "Technology", "rMSFT": "Technology", "rNVDA": "Technology",
    "rGOOGL": "Technology", "rGOOG": "Technology", "rMETA": "Technology",
    "rAMD": "Technology", "rCRM": "Technology", "rORCL": "Technology",
    "rADBE": "Technology", "rAVGO": "Technology", "rCSCO": "Technology",
    "rINTC": "Technology", "rIBM": "Technology", "rQCOM": "Technology",
    "rTXN": "Technology", "rNOW": "Technology", "rPANW": "Technology",
    "rSNOW": "Technology", "rPLTR": "Technology", "rSHOP": "Technology",
    "rUBER": "Technology", "rABNB": "Technology", "rDELL": "Technology",
    "rMU": "Technology", "rAMAT": "Technology", "rLRCX": "Technology",

    # Consumer Discretionary
    "rAMZN": "Consumer Discretionary", "rTSLA": "Consumer Discretionary",
    "rNKE": "Consumer Discretionary", "rSBUX": "Consumer Discretionary",
    "rMCD": "Consumer Discretionary", "rHD": "Consumer Discretionary",
    "rDIS": "Consumer Discretionary", "rLOW": "Consumer Discretionary",
    "rBKNG": "Consumer Discretionary", "rTGT": "Consumer Discretionary",
    "rGM": "Consumer Discretionary", "rF": "Consumer Discretionary",
    "rRIVN": "Consumer Discretionary", "rLULU": "Consumer Discretionary",

    # Consumer Staples
    "rPG": "Consumer Staples", "rKO": "Consumer Staples",
    "rPEP": "Consumer Staples", "rWMT": "Consumer Staples",
    "rCOST": "Consumer Staples", "rCL": "Consumer Staples",
    "rMDLZ": "Consumer Staples", "rKHC": "Consumer Staples",
    "rPM": "Consumer Staples", "rMO": "Consumer Staples",

    # Financials
    "rJPM": "Financials", "rBAC": "Financials", "rGS": "Financials",
    "rMS": "Financials", "rV": "Financials", "rMA": "Financials",
    "rCOIN": "Financials", "rWFC": "Financials", "rC": "Financials",
    "rAXP": "Financials", "rSCHW": "Financials", "rBLK": "Financials",
    "rPYPL": "Financials", "rHOOD": "Financials",

    # Healthcare
    "rJNJ": "Healthcare", "rUNH": "Healthcare", "rPFE": "Healthcare",
    "rLLY": "Healthcare", "rABBV": "Healthcare", "rMRK": "Healthcare",
    "rTMO": "Healthcare", "rABT": "Healthcare", "rDHR": "Healthcare",
    "rCVS": "Healthcare", "rMDT": "Healthcare", "rAMGN": "Healthcare",

    # Energy
    "rXOM": "Energy", "rCVX": "Energy", "rSLB": "Energy",
    "rOXY": "Energy", "rCOP": "Energy", "rPSX": "Energy",

    # Industrials
    "rBA": "Industrials", "rCAT": "Industrials", "rGE": "Industrials",
    "rUPS": "Industrials", "rHON": "Industrials", "rLMT": "Industrials",
    "rRTX": "Industrials", "rDE": "Industrials", "rMMM": "Industrials",
    "rUNP": "Industrials",

    # Communication Services
    "rNFLX": "Communication Services", "rT": "Communication Services",
    "rVZ": "Communication Services", "rCMCSA": "Communication Services",
    "rTMUS": "Communication Services",

    # Materials
    "rLIN": "Materials", "rSHW": "Materials", "rNEM": "Materials",
    "rFCX": "Materials",

    # Utilities
    "rNEE": "Utilities", "rDUK": "Utilities", "rSO": "Utilities",

    # Real Estate
    "rAMT": "Real Estate", "rPLD": "Real Estate", "rSPG": "Real Estate",

    # Crypto-linked equities (distinct from broad Financials given the
    # correlation profile these tend to actually exhibit)
    "rMSTR": "Crypto-Linked Equity", "rMARA": "Crypto-Linked Equity",
    "rRIOT": "Crypto-Linked Equity",

    # Broad market / index ETFs (own pseudo-sector — doesn't belong in
    # any single GICS bucket)
    "rSPY": "Index/ETF", "rQQQ": "Index/ETF", "rVOO": "Index/ETF",
    "rIWM": "Index/ETF", "rDIA": "Index/ETF",
}

# Benchmark used for beta calculations across the whole engine.
BENCHMARK_TICKER = "rSPY"


def normalize_ticker(ticker: str) -> str:
    """Normalize any casing (raapl, RAAPL, rAapl) to canonical 'rAAPL' form."""
    ticker = ticker.strip()
    if ticker[:1].lower() == "r":
        return "r" + ticker[1:].upper()
    return ticker.upper()


def get_sector(ticker: str) -> str:
    """Return the sector for a ticker (e.g. 'rAAPL', any casing), or 'Unknown' if not mapped."""
    return SECTOR_MAP.get(normalize_ticker(ticker), "Unknown")


def known_tickers() -> list[str]:
    """All tickers we have sector data for (used for universe scans)."""
    return list(SECTOR_MAP.keys())
