"""
Real-time inline grammar correction.

Correction itself goes through Groq (lib/llm_client) via prompts.build_grammar_correction_prompt
— no local grammar/NLP dependency, matching the rest of this backend (Groq + offline
fallback, see lib/ai_client.py). Offline fallback is "no correction available" rather than
a fake correction, since there's no local grammar engine to fall back to.

The "single highest-impact chip" diff logic is pure stdlib (difflib) and independent of
whether an LLM is available.
"""

import difflib
from typing import Dict, List, Optional

from lib import llm_client, prompts


async def correct(text: str) -> Optional[str]:
    """Return corrected text, or None if uncorrectable/unconfigured/unchanged."""
    if not text.strip() or not llm_client.is_configured():
        return None
    try:
        corrected = await llm_client.chat(
            [{"role": "user", "content": prompts.build_grammar_correction_prompt(text)}],
            temperature=0.0,
            max_tokens=min(300, len(text.split()) * 4 + 50),
        )
    except llm_client.LLMError:
        return None
    corrected = corrected.strip().strip('"')
    return corrected if corrected and corrected != text.strip() else None


def _impact(candidate: Dict[str, str]) -> int:
    return len(candidate["from"]) + len(candidate["to"])


def pick_chip(original: str, corrected: str) -> Optional[Dict[str, str]]:
    """diff original vs. corrected word-by-word, cap to ONE highest-impact chip."""
    original_words = original.split()
    corrected_words = corrected.split()
    matcher = difflib.SequenceMatcher(a=original_words, b=corrected_words)
    candidates: List[Dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        candidates.append({
            "from": " ".join(original_words[i1:i2]),
            "to": " ".join(corrected_words[j1:j2]),
        })
    if not candidates:
        return None
    return max(candidates, key=_impact)


async def get_correction_chip(text: str, *, show_corrections: bool, is_voice_mode: bool) -> Dict:
    """Returns {"chip": {...}|None, "suppressed_reason": str|None}.

    chips suppressed in voice mode (still computed, for the end-of-session summary).
    Off by default — caller must pass show_corrections=True (opt-in toggle).
    """
    if not show_corrections:
        return {"chip": None, "suppressed_reason": "toggle_off"}

    corrected = await correct(text)
    if corrected is None:
        return {"chip": None, "suppressed_reason": "no_correction_needed"}

    chip = pick_chip(text, corrected)
    if is_voice_mode:
        return {"chip": None, "suppressed_reason": "voice_mode"}
    return {"chip": chip, "suppressed_reason": None}
