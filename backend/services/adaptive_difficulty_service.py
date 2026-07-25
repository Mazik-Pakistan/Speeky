"""
Adaptive Difficulty Progression Service for Targeted Exercises.

CONTRACT & ARCHITECTURAL NOTE:
This module CONSUMES scored attempts from whatever external module eventually owns
pronunciation / accent scoring (e.g. PronunciationCoach or AccentAssessment).
It defines a decoupled interface (ScoredAttemptRequest) so upstream components can submit
scored attempts (metric name e.g. 'th_sound', 'rising_intonation', score 0-100, drill item phrase)
without needing to modify this service.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from lib import kv_store, llm_client, prompts
from schemas.adaptive_difficulty_schemas import (
    EscalationEvent,
    EscalationHistoryResponse,
    GenerateDrillRequest,
    GenerateDrillResponse,
    MetricProgressionState,
    ScoredAttemptRequest,
    ScoredAttemptResponse,
)

logger = logging.getLogger(__name__)

STATE_NS = "adaptive_difficulty_state"
HISTORY_NS = "adaptive_difficulty_history"

MASTERY_THRESHOLD = 85.0
REGRESSION_THRESHOLD = 60.0
MASTERY_CONSECUTIVE_REQUIRED = 3
MASTERY_DISTINCT_ITEMS_REQUIRED = 2

# Static fallback drill phrases per metric and difficulty level
STATIC_DRILL_FALLBACKS: Dict[str, Dict[int, str]] = {
    "th_sound": {
        1: "Thirty-three thin turtles in the theater.",
        2: "I thought about visiting the theater three times this Thursday.",
        3: "Thirty-three thousand thoughtful thinkers thoroughly thought through thirty thousand themes.",
    },
    "rising_intonation": {
        1: "Are you coming with us tonight?",
        2: "Could you clarify whether the deadline is on Monday or Tuesday?",
        3: "Would you mind double-checking if the conference call was rescheduled for tomorrow afternoon?",
    },
    "r_l_distinction": {
        1: "Light red roses fall along the road.",
        2: "Really rare light blue ribbon rolls readily down the long hill.",
        3: "Literally legendary royal laurels roll rapidly along rolling green lawns.",
    },
    "vowel_clarity": {
        1: "Keep the deep green leaf clean.",
        2: "Please seat the team near the clean stream before three.",
        3: "Elite speakers seamlessly execute crystal-clear vowel distinctions under pressure.",
    },
}

DEFAULT_STATIC_FALLBACKS: Dict[int, str] = {
    1: "Practice saying: 'The quick brown fox jumps over the lazy dog.'",
    2: "Practice saying: 'Clear, confident articulation improves professional communication every day.'",
    3: "Practice saying: 'Sophisticated pronunciation mastery requires deliberate, repeated, and varied practice across complex sentences.'",
}


def _storage_key(user_id: str, metric_name: str) -> str:
    return f"{user_id}:{metric_name.strip().lower()}"


def _get_static_drill(metric_name: str, level: int) -> Tuple[str, str]:
    normalized_metric = metric_name.strip().lower()
    metric_fallbacks = STATIC_DRILL_FALLBACKS.get(normalized_metric, DEFAULT_STATIC_FALLBACKS)
    drill = metric_fallbacks.get(level, DEFAULT_STATIC_FALLBACKS.get(level, DEFAULT_STATIC_FALLBACKS[1]))
    notes = f"Static offline fallback drill tailored for metric '{metric_name}' at difficulty Level {level}."
    return drill, notes


async def get_metric_state(metric_name: str, user_id: str) -> MetricProgressionState:
    key = _storage_key(user_id, metric_name)
    raw = await kv_store.store.get(STATE_NS, key)
    if not raw:
        return MetricProgressionState(
            metric_name=metric_name,
            current_level=1,
            consecutive_mastery_count=0,
            recent_drill_items=[],
            total_attempts=0,
            last_score=None,
            last_attempt_at=None,
        )
    return MetricProgressionState(**raw)


async def get_escalation_history(metric_name: str, user_id: str) -> EscalationHistoryResponse:
    key = _storage_key(user_id, metric_name)
    raw_history = await kv_store.store.get(HISTORY_NS, key)
    history_events: List[EscalationEvent] = []
    if raw_history and isinstance(raw_history, dict) and "events" in raw_history:
        history_events = [EscalationEvent(**e) for e in raw_history["events"]]
    
    state = await get_metric_state(metric_name, user_id)
    return EscalationHistoryResponse(
        metric_name=metric_name,
        current_level=state.current_level,
        history=history_events,
    )


async def record_attempt(payload: ScoredAttemptRequest, user_id: str) -> ScoredAttemptResponse:
    metric_name = payload.metric_name.strip().lower()
    key = _storage_key(user_id, metric_name)
    state = await get_metric_state(metric_name, user_id)

    previous_level = state.current_level
    current_level = previous_level
    consecutive_count = state.consecutive_mastery_count
    recent_items = list(state.recent_drill_items)
    score = payload.score
    drill_item = payload.drill_item.strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    escalated = False
    regressed = False
    message = "Attempt recorded."

    history_key = _storage_key(user_id, metric_name)
    history_data = await kv_store.store.get(HISTORY_NS, history_key) or {"events": []}
    events = history_data.get("events", [])

    # Log initial baseline event if this is the first attempt
    if state.total_attempts == 0 and not events:
        events.append(
            EscalationEvent(
                metric_name=metric_name,
                event_type="initial",
                from_level=1,
                to_level=1,
                reached_at=now_iso,
                trigger_reason="Started tracking metric at baseline Level 1",
            ).model_dump()
        )

    # 1. Mastery Path (Score >= 85.0)
    if score >= MASTERY_THRESHOLD:
        consecutive_count += 1
        recent_items.append(drill_item)

        if consecutive_count >= MASTERY_CONSECUTIVE_REQUIRED:
            distinct_items = len(set(recent_items))
            if distinct_items >= MASTERY_DISTINCT_ITEMS_REQUIRED:
                # Escalation criteria met!
                current_level += 1
                escalated = True
                consecutive_count = 0
                recent_items = []
                message = f"Mastery achieved on 3 consecutive attempts across {distinct_items} distinct drill items! Escalated to Level {current_level}."

                events.append(
                    EscalationEvent(
                        metric_name=metric_name,
                        event_type="escalation",
                        from_level=previous_level,
                        to_level=current_level,
                        reached_at=now_iso,
                        trigger_reason=f"3 consecutive scores >= {MASTERY_THRESHOLD} on {distinct_items} distinct drill items",
                    ).model_dump()
                )
            else:
                # Anti-gaming rule triggered: 3 repeats of identical phrase
                message = f"3 consecutive scores >= {MASTERY_THRESHOLD} reached, but used only 1 distinct drill item. Alternate drill items required to level up."
        else:
            message = f"High score recorded ({score:.1f}/100). {consecutive_count}/{MASTERY_CONSECUTIVE_REQUIRED} consecutive mastery attempts."

    # 2. Regression Path (Score < 60.0)
    elif score < REGRESSION_THRESHOLD:
        consecutive_count = 0
        recent_items = []

        if current_level > 1:
            current_level -= 1
            regressed = True
            message = f"Score ({score:.1f}/100) below regression threshold ({REGRESSION_THRESHOLD}). Stepped down to Level {current_level}."

            events.append(
                EscalationEvent(
                    metric_name=metric_name,
                    event_type="regression",
                    from_level=previous_level,
                    to_level=current_level,
                    reached_at=now_iso,
                    trigger_reason=f"Score {score:.1f} below threshold {REGRESSION_THRESHOLD} at Level {previous_level}",
                ).model_dump()
            )
        else:
            message = f"Score ({score:.1f}/100) below threshold, but already at minimum Level 1."

    # 3. Neutral Path (60.0 <= Score < 85.0)
    else:
        consecutive_count = 0
        recent_items = []
        message = f"Score ({score:.1f}/100) recorded. Consecutive mastery count reset."

    # Update state blob
    new_state = MetricProgressionState(
        metric_name=metric_name,
        current_level=current_level,
        consecutive_mastery_count=consecutive_count,
        recent_drill_items=recent_items,
        total_attempts=state.total_attempts + 1,
        last_score=score,
        last_attempt_at=now_iso,
    )

    # Save to kv_store
    if await kv_store.store.get(STATE_NS, key) is None:
        await kv_store.store.create(STATE_NS, key, new_state.model_dump())
    else:
        await kv_store.store.update(STATE_NS, key, new_state.model_dump())

    if await kv_store.store.get(HISTORY_NS, history_key) is None:
        await kv_store.store.create(HISTORY_NS, history_key, {"events": events})
    else:
        await kv_store.store.update(HISTORY_NS, history_key, {"events": events})

    distinct_count = len(set(recent_items)) if recent_items else 0

    return ScoredAttemptResponse(
        user_id=user_id,
        metric_name=metric_name,
        score=score,
        drill_item=drill_item,
        previous_level=previous_level,
        current_level=current_level,
        escalated=escalated,
        regressed=regressed,
        consecutive_mastery_count=consecutive_count,
        distinct_drill_items_count=distinct_count,
        message=message,
    )


async def generate_drill(payload: GenerateDrillRequest, user_id: str) -> GenerateDrillResponse:
    metric_name = payload.metric_name.strip().lower()
    
    if payload.level is not None:
        level = payload.level
    else:
        state = await get_metric_state(metric_name, user_id)
        level = state.current_level

    prompt_text = prompts.build_adaptive_drill_prompt(metric_name, level)

    try:
        raw_json_str = await llm_client.chat_json(
            [{"role": "user", "content": prompt_text}],
            temperature=0.4,
            max_tokens=256,
        )
        parsed = json.loads(raw_json_str) if isinstance(raw_json_str, str) else raw_json_str
        drill_phrase = parsed.get("drill_phrase", "").strip()
        complexity_notes = parsed.get("complexity_notes", f"LLM generated for Level {level}").strip()

        if drill_phrase:
            return GenerateDrillResponse(
                metric_name=metric_name,
                level=level,
                drill_phrase=drill_phrase,
                source="llm",
                complexity_notes=complexity_notes,
            )
    except llm_client.LLMError as e:
        logger.warning("LLM drill generation failed (%s); using static fallback for metric '%s' level %d", e, metric_name, level)
    except Exception as e:
        logger.warning("Unexpected error during drill generation (%s); using static fallback", e)

    # Graceful degradation fallback
    fallback_phrase, fallback_notes = _get_static_drill(metric_name, level)
    return GenerateDrillResponse(
        metric_name=metric_name,
        level=level,
        drill_phrase=fallback_phrase,
        source="static_fallback",
        complexity_notes=fallback_notes,
    )
