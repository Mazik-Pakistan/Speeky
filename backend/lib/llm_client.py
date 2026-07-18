"""
Groq chat client (httpx) — the LLM backbone for coaching feedback,
conversation practice, and topic/level validation (prompts.py rules).

Integration notes:
- Provider is Groq's OpenAI-compatible /chat/completions endpoint. Config comes
  from env: GROQ_API_KEY (required for live calls), GROQ_MODEL, GROQ_BASE_URL.
- When no API key is configured, live calls raise LLMNotConfigured. Callers that
  must degrade gracefully (coaching feedback) catch it and fall back to the
  rule-based heuristics in coaching_service — so the product still returns tone
  flags / scores offline and the whole suite is testable without a network.
- json_mode=True asks Groq for a strict JSON object and parses it; malformed
  output raises LLMError so callers can fall back deterministically.
"""

import json
import logging
import os
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class LLMError(Exception):
    """Any failure talking to / parsing the LLM."""


class LLMNotConfigured(LLMError):
    """No GROQ_API_KEY set — live calls are impossible."""


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _model() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL)


def _base_url() -> str:
    return os.environ.get("GROQ_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


async def chat(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
    json_mode: bool = False,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """
    Send a chat completion to Groq and return the assistant's text content.

    messages: OpenAI-style [{"role": "system"|"user"|"assistant", "content": ...}].
    Raises LLMNotConfigured if no key, LLMError on transport / API / parse errors.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LLMNotConfigured("GROQ_API_KEY is not set")

    payload: Dict = {
        "model": model or _model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Groq API error {e.response.status_code}: {e.response.text}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Groq request failed: {e}") from e

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"Unexpected Groq response shape: {data!r}") from e


async def chat_json(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    model: Optional[str] = None,
) -> Dict:
    """chat() in JSON mode, parsed into a dict. Raises LLMError on bad JSON."""
    raw = await chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
        model=model,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Some models wrap JSON in prose/code fences despite json_mode — salvage
        # the outermost object before giving up.
        start, end = raw.find("{"), raw.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"LLM did not return valid JSON: {raw[:200]!r}") from e
