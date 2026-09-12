"""
Fetches the user's real rToken holdings from Bitget's private account API.
Requires a read-only API key (key, secret, passphrase) — this is per-user,
private data, never shared across users.

Bitget's private endpoints use HMAC-SHA256 signing over
(timestamp + method + requestPath + body), base64-encoded, per their
standard REST auth scheme (same pattern used across their spot/futures APIs).
"""

import base64
import hashlib
import hmac
import time

import requests

BASE_URL = "https://api.bitget.com"
ASSETS_ENDPOINT = "/api/v2/spot/account/assets"


def _sign(timestamp: str, method: str, request_path: str, body: str, secret: str) -> str:
    message = f"{timestamp}{method.upper()}{request_path}{body}"
    mac = hmac.new(secret.encode(), message.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def _headers(api_key: str, api_secret: str, passphrase: str, method: str, request_path: str, body: str = "") -> dict:
    timestamp = str(int(time.time() * 1000))
    sign = _sign(timestamp, method, request_path, body, api_secret)
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
    }


def fetch_holdings(api_key: str, api_secret: str, passphrase: str) -> list[dict]:
    """
    Fetch the user's current rToken spot holdings.

    Returns a list of dicts:
        {"ticker": str (canonical rToken form, e.g. "rAAPL"),
         "quantity": float}

    Only returns holdings whose base coin is an rToken (starts with 'r') —
    plain crypto holdings are filtered out, since this product is scoped to
    rToken portfolio analysis only. Ticker is normalized to "r" + uppercase
    stock ticker (e.g. "rAAPL") regardless of the exact casing Bitget returns.

    Raises requests.HTTPError on a failed request, ValueError on an API-level
    error response.
    """
    headers = _headers(api_key, api_secret, passphrase, "GET", ASSETS_ENDPOINT)
    resp = requests.get(BASE_URL + ASSETS_ENDPOINT, headers=headers, timeout=10)
    resp.raise_for_status()
    body = resp.json()

    if body.get("code") != "00000":
        raise ValueError(f"Bitget API error fetching holdings: {body.get('msg')}")

    holdings = []
    for asset in body.get("data", []):
        coin = asset.get("coin", "")
        if coin.upper().startswith("R") and len(coin) > 1:
            qty = float(asset.get("available", 0)) + float(asset.get("frozen", 0))
            if qty > 0:
                normalized_ticker = "r" + coin[1:].upper()  # canonical "rAAPL" form
                holdings.append({
                    "ticker": normalized_ticker,
                    "quantity": qty,
                })
    return holdings
