"""
ai_client.generate(...) adapter — the LLM entry point the ported feature services
(interview_coach, session_memory) were written against. Wraps the Groq lib.llm_client
with a deterministic offline fallback so the features run (and tests pass) without a key,
mirroring how coaching_service degrades.
"""

from lib import llm_client


def _offline(system_prompt: str, user_message: str) -> str:
    """Deterministic stand-in when Groq isn't configured/reachable.

    Keeps the conversational features moving with a neutral, on-shape response rather
    than raising. Intentionally generic — real phrasing comes from Groq when keyed.
    """
    return "Thanks — could you tell me a bit more about that, with a specific example?"


async def generate(
    system_prompt: str,
    user_message: str = "",
    *,
    max_tokens: int = 600,
    temperature: float = 0.4,
) -> str:
    if not llm_client.is_configured():
        return _offline(system_prompt, user_message)
    try:
        return await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except llm_client.LLMError:
        return _offline(system_prompt, user_message)
