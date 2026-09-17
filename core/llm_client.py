"""
LLM client — OpenAI-compatible, provider-agnostic.

Works with any provider that speaks the OpenAI chat-completions API shape:
Bitget's hackathon Qwen endpoint, DeepSeek, Groq, OpenAI itself, etc.
Swapping providers is an env var change, not a code change — nothing here
is hardcoded to any specific provider.

Required env vars:
    LLM_BASE_URL — e.g. https://hackathon.bitgetops.com/v1 (for the Bitget
        hackathon Qwen endpoint), or https://api.deepseek.com/v1, etc.
    LLM_API_KEY  — the provider's key
    LLM_MODEL    — e.g. "qwen3.8-max", "deepseek-chat", etc.
"""

import os
from openai import OpenAI


def get_client() -> OpenAI:
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")

    if not base_url or not api_key:
        raise RuntimeError("LLM_BASE_URL and LLM_API_KEY must be set in the environment")

    return OpenAI(base_url=base_url, api_key=api_key)


def get_model() -> str:
    model = os.environ.get("LLM_MODEL")
    if not model:
        raise RuntimeError("LLM_MODEL must be set in the environment")
    return model
