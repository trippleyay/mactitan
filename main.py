"""
MacTitan backend API. /chat for the web frontend, /telegram/webhook for the
Telegram bot — both wrap the same core.assistant.ask().

The web endpoint is stateless (frontend sends history back each request).
The Telegram endpoint holds per-chat history in memory, since Telegram has
no equivalent of a frontend managing that state — see TELEGRAM_HISTORY
below for the tradeoff this implies.

Run with: uvicorn main:app --host 0.0.0.0 --port 8000
"""

import os

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.assistant import ask
from core.telegram_format import to_telegram_text
from core.chat_storage import get_history, save_history

app = FastAPI(title="MacTitan API")

# CORS: allow the production frontend domain plus localhost for local dev.
# Update ALLOWED_ORIGINS once the Vercel frontend domain is finalized.
ALLOWED_ORIGINS = [
    "https://mactitan.useomniagents.xyz",
    "http://localhost:3000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    answer: str
    history: list[dict]
    tools_used: list[str]


@app.get("/health")
def health():
    """Basic liveness check — useful for judges/monitoring to confirm the
    service is up without triggering an LLM call."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    try:
        result = ask(request.message, conversation_history=request.history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assistant error: {str(e)}")

    return ChatResponse(
        answer=result["answer"],
        history=result["history"],
        tools_used=[t["tool"] for t in result["tool_calls_made"]],
    )


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------
# Per-chat history is persisted to a local SQLite file (core/chat_storage.py)
# so it survives restarts and redeploys.


def _telegram_api_url(method: str) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment")
    return f"https://api.telegram.org/bot{token}/{method}"


def _send_telegram_message(chat_id: int, text: str) -> None:
    resp = requests.post(
        _telegram_api_url("sendMessage"),
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    if not resp.ok:
        # If Markdown parsing fails (e.g. unescaped special characters),
        # retry once as plain text rather than losing the reply entirely.
        requests.post(
            _telegram_api_url("sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()

    message = update.get("message")
    if not message or "text" not in message:
        return {"ok": True}  # ignore non-text updates (photos, stickers, etc.)

    chat_id = message["chat"]["id"]
    user_text = message["text"]

    history = get_history(chat_id)

    try:
        result = ask(user_text, conversation_history=history)
    except Exception as e:
        _send_telegram_message(chat_id, f"Something went wrong: {str(e)}")
        return {"ok": True}

    save_history(chat_id, result["history"])

    telegram_safe_answer = to_telegram_text(result["answer"])
    _send_telegram_message(chat_id, telegram_safe_answer)

    return {"ok": True}
