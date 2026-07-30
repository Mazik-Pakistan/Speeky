"""Shared test setup. Forces the LLM offline so the suite is deterministic and network-free
(coaching grading falls back to the heuristic grader). Tests that want the LLM path
monkeypatch lib.llm_client explicitly."""

import os

import pytest


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    yield


@pytest.fixture(autouse=True)
def _memory_store():
    """Swap the persistent prisma-backed KV store for an in-process one, so the ported
    feature services (interview_coach / session_memory / resume_jd) run without a DB.
    Fresh per test for isolation."""
    from lib import kv_store

    original = kv_store.store
    kv_store.store = kv_store.InMemoryKvStore()
    yield
    kv_store.store = original
