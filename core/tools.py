"""
LLM-facing tools: simple wrapper functions around the already-tested core
engine, plus their OpenAI-compatible function-calling schemas.

Each wrapper binds the real data-fetch functions (Bitget price data) so the
LLM only ever needs to pass simple arguments (ticker, event_type) — it never
sees or controls the underlying data-fetching mechanics.
"""

from datetime import date

from core.price_fetch import fetch_price_history, fetch_closes
from core.event_reaction import compute_event_reactions, summarize_reactions
from core.sector_sensitivity import rank_sector_sensitivity
from core.stats import compute_recent_volatility
from core.bls_data import get_cpi_breakdown
from data.macro_calendar import CPI_2026_DATES_CONFIRMED, FOMC_2026_DATES, next_fomc_date, next_cpi_date
from data.sector_map import known_tickers, get_sector

EVENT_DATE_SOURCES = {
    "cpi": CPI_2026_DATES_CONFIRMED,
    "fomc": FOMC_2026_DATES,
}


def tool_event_reaction(ticker: str, event_type: str) -> dict:
    """How a specific rToken has historically reacted to a type of macro event."""
    if event_type not in EVENT_DATE_SOURCES:
        return {"error": f"Unknown event_type '{event_type}'. Use 'cpi' or 'fomc'."}

    event_dates = EVENT_DATE_SOURCES[event_type]
    reactions = compute_event_reactions(ticker, event_dates, fetch_price_history)
    summary = summarize_reactions(reactions)
    return {
        "ticker": ticker,
        "event_type": event_type,
        "individual_reactions": reactions,
        "summary": summary,
    }


def tool_sector_sensitivity(event_type: str) -> dict:
    """Ranks sectors by how much they've actually moved around a type of macro event."""
    if event_type not in EVENT_DATE_SOURCES:
        return {"error": f"Unknown event_type '{event_type}'. Use 'cpi' or 'fomc'."}

    event_dates = EVENT_DATE_SOURCES[event_type]
    ranked = rank_sector_sensitivity(event_dates, fetch_price_history, tickers=known_tickers())
    return {"event_type": event_type, "sector_ranking": ranked}


def tool_current_volatility(ticker: str) -> dict:
    """Whether a ticker's current volatility is elevated relative to its own recent baseline."""
    closes = fetch_closes(ticker, "1day", 60)
    result = compute_recent_volatility(closes, recent_window=10)
    return {"ticker": ticker, **result}


def tool_upcoming_event(event_type: str) -> dict:
    """The next known date for a type of macro event, from the official Fed/BLS calendar."""
    today = date.today().isoformat()
    if event_type == "cpi":
        return {"event_type": "cpi", "next_date": next_cpi_date(today)}
    elif event_type == "fomc":
        return {"event_type": "fomc", "next_date": next_fomc_date(today)}
    return {"error": f"Unknown event_type '{event_type}'. Use 'cpi' or 'fomc'."}


def tool_cpi_breakdown() -> dict:
    """Latest CPI reading broken into categories (headline, core, food, energy, shelter)."""
    breakdown = get_cpi_breakdown(start_year="2026", end_year="2026")
    from core.bls_data import join_breakdown_to_release_dates
    joined = join_breakdown_to_release_dates(breakdown)
    if not joined:
        return {"error": "No CPI breakdown data available"}
    return {"latest": joined[-1], "recent_history": joined[-6:]}


TOOL_DISPATCH = {
    "get_event_reaction": tool_event_reaction,
    "get_sector_sensitivity": tool_sector_sensitivity,
    "get_current_volatility": tool_current_volatility,
    "get_upcoming_event": tool_upcoming_event,
    "get_cpi_breakdown": tool_cpi_breakdown,
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_event_reaction",
            "description": "Get how a specific rToken has historically reacted (price move, volatility) around real macro events like CPI releases or FOMC decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "rToken ticker, e.g. 'rNVDA', 'rAAPL'"},
                    "event_type": {"type": "string", "enum": ["cpi", "fomc"], "description": "Type of macro event"},
                },
                "required": ["ticker", "event_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_sensitivity",
            "description": "Rank sectors by how much they've actually moved around a type of macro event (CPI or FOMC), using real historical price data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "enum": ["cpi", "fomc"], "description": "Type of macro event"},
                },
                "required": ["event_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_volatility",
            "description": "Check whether a ticker's current volatility is elevated relative to its own recent baseline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "rToken ticker, e.g. 'rTSLA'"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_event",
            "description": "Get the next scheduled date for a type of macro event (CPI release or FOMC decision), from the official Fed/BLS calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "enum": ["cpi", "fomc"], "description": "Type of macro event"},
                },
                "required": ["event_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cpi_breakdown",
            "description": "Get the latest CPI reading broken into categories (headline, core, food, energy, shelter) to see what's actually driving inflation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
