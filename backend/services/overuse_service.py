"""
Healthy Engagement Safeguard / overuse nudge (US-170 / GAP-09).

Tracks *continuous* unbroken sitting time per user via periodic heartbeats from
whatever feature session is active (chat, pronunciation coach, daily challenge, ...).
A gap between heartbeats longer than OVERUSE_IDLE_BREAK_MINUTES counts as a break and
resets the continuous timer — this is what keeps several short sessions from summing
into a false trigger (E-03), since only unbroken sitting time is tracked, never total
daily practice time.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Depends

from lib import kv_store
from lib.prompts import (
    OVERUSE_FOLLOWUP_INTERVAL_MINUTES,
    OVERUSE_FOLLOWUP_NUDGE_MESSAGE,
    OVERUSE_IDLE_BREAK_MINUTES,
    OVERUSE_NUDGE_MESSAGE,
    OVERUSE_THRESHOLD_MINUTES,
)
from middlewares.auth_middleware import require_auth
from schemas.overuse_schemas import (
    DismissNudgeResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    OveruseNudgePayload,
)

STATE_NS = "overuse_state"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_state(user_id: str) -> Optional[Dict]:
    return await kv_store.store.get(STATE_NS, user_id)


async def _save_state(user_id: str, state: Dict) -> None:
    if await kv_store.store.get(STATE_NS, user_id) is None:
        await kv_store.store.create(STATE_NS, user_id, state)
    else:
        await kv_store.store.update(STATE_NS, user_id, state)


def _fresh_state(user_id: str, now: datetime) -> Dict:
    return {
        "user_id": user_id,
        "continuous_started_at": now,
        "last_activity_at": now,
        "nudge_shown_at": None,
        "dismissed_at": None,
        "followup_shown": False,
    }


async def _record_heartbeat(user_id: str, now: Optional[datetime] = None) -> HeartbeatResponse:
    now = now or _now()
    state = await _get_state(user_id)

    if state is None or (now - state["last_activity_at"]) > timedelta(minutes=OVERUSE_IDLE_BREAK_MINUTES):
        # No prior state, or an idle gap longer than the break threshold: this is a
        # fresh unbroken sitting, not a continuation (E-03).
        state = _fresh_state(user_id, now)
    else:
        state["last_activity_at"] = now

    continuous_minutes = (now - state["continuous_started_at"]).total_seconds() / 60

    nudge = None
    if continuous_minutes >= OVERUSE_THRESHOLD_MINUTES:
        if state["nudge_shown_at"] is None:
            nudge = OveruseNudgePayload(message=OVERUSE_NUDGE_MESSAGE, is_followup=False)
            state["nudge_shown_at"] = now
        elif (
            state["dismissed_at"] is not None
            and not state["followup_shown"]
            and (now - state["nudge_shown_at"]) >= timedelta(minutes=OVERUSE_FOLLOWUP_INTERVAL_MINUTES)
        ):
            # E-01: at most ONE follow-up nudge after a further extended interval.
            nudge = OveruseNudgePayload(message=OVERUSE_FOLLOWUP_NUDGE_MESSAGE, is_followup=True)
            state["nudge_shown_at"] = now
            state["followup_shown"] = True

    await _save_state(user_id, state)
    return HeartbeatResponse(continuous_minutes=round(continuous_minutes, 2), nudge=nudge)


async def _dismiss_nudge(user_id: str, now: Optional[datetime] = None) -> DismissNudgeResponse:
    now = now or _now()
    state = await _get_state(user_id)
    if state is None:
        state = _fresh_state(user_id, now)
    state["dismissed_at"] = now
    await _save_state(user_id, state)
    return DismissNudgeResponse(dismissed=True, dismissed_at=now)


def order_gamification_events(milestone: Optional[dict], overuse_nudge: Optional[OveruseNudgePayload]) -> list:
    """E-04: when a milestone and an overuse nudge coincide, the milestone celebration
    must render first and the wellbeing nudge as a separate, secondary message after."""
    events = []
    if milestone is not None:
        events.append({"kind": "milestone", **milestone})
    if overuse_nudge is not None:
        events.append({"kind": "overuse_nudge", **overuse_nudge.model_dump()})
    return events


# ── controllers (auth-gated) ────────────────────────────────────────────────
async def record_heartbeat(payload: HeartbeatRequest, user_id: str = Depends(require_auth)):
    return await _record_heartbeat(user_id)


async def dismiss_nudge(user_id: str = Depends(require_auth)):
    return await _dismiss_nudge(user_id)
