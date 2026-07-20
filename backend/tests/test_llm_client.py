"""Groq client (lib/llm_client) — config gating + JSON salvage."""

import json

import pytest

from lib import llm_client


def test_not_configured_without_key():
    assert llm_client.is_configured() is False  # conftest strips GROQ_API_KEY


async def test_chat_raises_when_unconfigured():
    with pytest.raises(llm_client.LLMNotConfigured):
        await llm_client.chat([{"role": "user", "content": "hi"}])


async def test_chat_json_salvages_wrapped_json(monkeypatch):
    async def fake_chat(messages, **kw):
        return 'Here you go:\n```json\n{"professional_tone": 80}\n```'
    monkeypatch.setattr(llm_client, "chat", fake_chat)
    out = await llm_client.chat_json([{"role": "user", "content": "x"}])
    assert out["professional_tone"] == 80


async def test_chat_json_raises_on_garbage(monkeypatch):
    async def fake_chat(messages, **kw):
        return "no json at all here"
    monkeypatch.setattr(llm_client, "chat", fake_chat)
    with pytest.raises(llm_client.LLMError):
        await llm_client.chat_json([{"role": "user", "content": "x"}])
