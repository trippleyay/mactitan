"""
LLM-facing tools: simple wrapper functions around the already-tested core
engine, plus their OpenAI-compatible function-calling schemas.

Covers 20 macro indicators (see data/macro_calendar.py for exact coverage
status per indicator — all either COMPLETE for the full 2026 year with real
official dates, or COMPUTED from a confirmed fixed institutional rule).
Nothing here is guessed or estimated.
"""

from datetime import date

from core.price_fetch import fetch_price_history, fetch_closes
from core.event_reaction import compute_event_reactions, summarize_reactions
from core.sector_sensitivity import rank_sector_sensitivity
from core.stats import compute_recent_volatility
from core.bls_data import get_cpi_breakdown
from core.fed_speeches import get_recent_fed_speeches
from core.potus_schedule import fetch_potus_schedule
from data.macro_calendar import (
    CPI_2026_DATES_CONFIRMED,
    FOMC_2026_DATES,
    PPI_2026_DATES_CONFIRMED,
    NONFARM_PAYROLLS_2026_DATES,
    UNEMPLOYMENT_2026_DATES,
    RETAIL_SALES_2026_DATES,
    INDUSTRIAL_PRODUCTION_2026_DATES,
    PCE_2026_DATES_CONFIRMED,
    GDP_2026_DATES_CONFIRMED,
    HOUSING_STARTS_2026_DATES_CONFIRMED,
    MICHIGAN_SENTIMENT_PRELIM_2026_DATES,
    MICHIGAN_SENTIMENT_FINAL_2026_DATES,
    JOLTS_2026_DATES_CONFIRMED,
    DURABLE_GOODS_2026_DATES_CONFIRMED,
    TRADE_BALANCE_2026_DATES_CONFIRMED,
    ISM_MANUFACTURING_2026_DATES,
    ISM_SERVICES_2026_DATES,
    INITIAL_JOBLESS_CLAIMS_2026_DATES,
    CONSUMER_CONFIDENCE_2026_DATES,
    next_fomc_date,
    next_cpi_date,
    next_ppi_date,
    next_nonfarm_payrolls_date,
    next_unemployment_date,
    next_retail_sales_date,
    next_industrial_production_date,
    next_pce_date,
    next_gdp_date,
    next_housing_starts_date,
    next_consumer_sentiment_prelim_date,
    next_consumer_sentiment_final_date,
    next_jolts_date,
    next_durable_goods_date,
    next_trade_balance_date,
    next_ism_manufacturing_date,
    next_ism_services_date,
    next_initial_jobless_claims_date,
    next_consumer_confidence_date,
)
from data.sector_map import known_tickers, get_sector

EVENT_DATE_SOURCES = {
    "cpi": CPI_2026_DATES_CONFIRMED,
    "fomc": FOMC_2026_DATES,
    "ppi": PPI_2026_DATES_CONFIRMED,
    "nonfarm_payrolls": NONFARM_PAYROLLS_2026_DATES,
    "unemployment": UNEMPLOYMENT_2026_DATES,
    "retail_sales": RETAIL_SALES_2026_DATES,
    "industrial_production": INDUSTRIAL_PRODUCTION_2026_DATES,
    "pce": PCE_2026_DATES_CONFIRMED,
    "gdp": GDP_2026_DATES_CONFIRMED,
    "housing_starts": HOUSING_STARTS_2026_DATES_CONFIRMED,
    "consumer_sentiment_preliminary": MICHIGAN_SENTIMENT_PRELIM_2026_DATES,
    "consumer_sentiment_final": MICHIGAN_SENTIMENT_FINAL_2026_DATES,
    "jolts": JOLTS_2026_DATES_CONFIRMED,
    "durable_goods": DURABLE_GOODS_2026_DATES_CONFIRMED,
    "trade_balance": TRADE_BALANCE_2026_DATES_CONFIRMED,
    "ism_manufacturing": ISM_MANUFACTURING_2026_DATES,
    "ism_services": ISM_SERVICES_2026_DATES,
    "initial_jobless_claims": INITIAL_JOBLESS_CLAIMS_2026_DATES,
    "consumer_confidence": CONSUMER_CONFIDENCE_2026_DATES,
}

_UPCOMING_LOOKUP = {
    "cpi": next_cpi_date,
    "fomc": next_fomc_date,
    "ppi": next_ppi_date,
    "nonfarm_payrolls": next_nonfarm_payrolls_date,
    "unemployment": next_unemployment_date,
    "retail_sales": next_retail_sales_date,
    "industrial_production": next_industrial_production_date,
    "pce": next_pce_date,
    "gdp": next_gdp_date,
    "housing_starts": next_housing_starts_date,
    "consumer_sentiment_preliminary": next_consumer_sentiment_prelim_date,
    "consumer_sentiment_final": next_consumer_sentiment_final_date,
    "jolts": next_jolts_date,
    "durable_goods": next_durable_goods_date,
    "trade_balance": next_trade_balance_date,
    "ism_manufacturing": next_ism_manufacturing_date,
    "ism_services": next_ism_services_date,
    "initial_jobless_claims": next_initial_jobless_claims_date,
    "consumer_confidence": next_consumer_confidence_date,
}

_EVENT_TYPE_ENUM = list(EVENT_DATE_SOURCES.keys())


def tool_event_reaction(ticker: str, event_type: str) -> dict:
    """How a specific rToken has historically reacted to a type of macro event."""
    if event_type not in EVENT_DATE_SOURCES:
        return {"error": f"Unknown event_type '{event_type}'. Use one of: {_EVENT_TYPE_ENUM}."}

    event_dates = EVENT_DATE_SOURCES[event_type]
    if not event_dates:
        return {"error": f"No confirmed dates for '{event_type}'."}

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
        return {"error": f"Unknown event_type '{event_type}'. Use one of: {_EVENT_TYPE_ENUM}."}

    event_dates = EVENT_DATE_SOURCES[event_type]
    if not event_dates:
        return {"error": f"No confirmed dates for '{event_type}'."}

    ranked = rank_sector_sensitivity(event_dates, fetch_price_history, tickers=known_tickers())
    return {"event_type": event_type, "sector_ranking": ranked}


def tool_current_volatility(ticker: str) -> dict:
    """Whether a ticker's current volatility is elevated relative to its own recent baseline."""
    closes = fetch_closes(ticker, "1day", 60)
    result = compute_recent_volatility(closes, recent_window=10)
    return {"ticker": ticker, **result}


def tool_upcoming_event(event_type: str) -> dict:
    """The next known date for a type of macro event, from the official calendar for that indicator."""
    if event_type not in _UPCOMING_LOOKUP:
        return {"error": f"Unknown event_type '{event_type}'. Use one of: {_EVENT_TYPE_ENUM}."}

    today = date.today().isoformat()
    next_date = _UPCOMING_LOOKUP[event_type](today)
    return {"event_type": event_type, "next_date": next_date}


def tool_cpi_breakdown() -> dict:
    """Latest CPI reading broken into categories (headline, core, food, energy, shelter)."""
    breakdown = get_cpi_breakdown(start_year="2026", end_year="2026")
    from core.bls_data import join_breakdown_to_release_dates
    joined = join_breakdown_to_release_dates(breakdown)
    if not joined:
        return {"error": "No CPI breakdown data available"}
    return {"latest": joined[-1], "recent_history": joined[-6:]}


def tool_recent_fed_speeches(speaker: str | None = None) -> dict:
    """Recent Fed speeches, live from the Fed's own feed — optionally filtered to one official."""
    try:
        speeches = get_recent_fed_speeches(speaker_filter=speaker, limit=10)
    except Exception as e:
        return {"error": f"Could not fetch Fed speeches feed: {str(e)}"}
    return {
        "speaker_filter": speaker,
        "speeches": speeches,
        "note": "This is a live, rolling feed of the ~20 most recent Fed speeches, not a forward calendar — it shows what's recent or already announced, not what's scheduled months out.",
    }


def tool_potus_schedule() -> dict:
    """Live check of the current White House daily schedule, via a third-party feed (see core/potus_schedule.py)."""
    try:
        schedule = fetch_potus_schedule()
    except Exception as e:
        return {"error": f"Could not fetch POTUS schedule feed: {str(e)}"}
    return {
        "schedule": schedule,
        "note": "This shows what's currently published on the schedule feed right now — it cannot show a future date that hasn't been published yet, and it is not an official government source (see core/potus_schedule.py for the sourcing).",
    }


TOOL_DISPATCH = {
    "get_event_reaction": tool_event_reaction,
    "get_sector_sensitivity": tool_sector_sensitivity,
    "get_current_volatility": tool_current_volatility,
    "get_upcoming_event": tool_upcoming_event,
    "get_cpi_breakdown": tool_cpi_breakdown,
    "get_recent_fed_speeches": tool_recent_fed_speeches,
    "get_potus_schedule": tool_potus_schedule,
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_event_reaction",
            "description": "Get how a specific rToken has historically reacted (price move, volatility) around a real macro event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "rToken ticker, e.g. 'rNVDA', 'rAAPL'"},
                    "event_type": {"type": "string", "enum": _EVENT_TYPE_ENUM, "description": "Type of macro event"},
                },
                "required": ["ticker", "event_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_sensitivity",
            "description": "Rank sectors by how much they've actually moved around a type of macro event, using real historical price data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "enum": _EVENT_TYPE_ENUM, "description": "Type of macro event"},
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
            "description": "Get the next scheduled date for a type of macro event, from the official calendar for that indicator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "enum": _EVENT_TYPE_ENUM, "description": "Type of macro event"},
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
    {
        "type": "function",
        "function": {
            "name": "get_recent_fed_speeches",
            "description": "Get recent Fed official speeches, live from the Fed's own feed. Not a forward calendar — shows what's recent or already announced, since Fed speeches aren't published as a full-year schedule the way CPI/FOMC dates are.",
            "parameters": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "description": "Optional: filter to one official, e.g. 'Powell'"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_potus_schedule",
            "description": "Live check of the current White House daily schedule, via a credible third-party tracker (not an official government feed). Only shows what's published right now — cannot answer about future or past dates.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
