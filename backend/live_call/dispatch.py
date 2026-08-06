"""Per-room dispatch: parses feature + session id out of the LiveKit room name (minted
by services/live_call_service.py) and builds everything worker.py needs to start an
AgentSession for that specific call. Live Call is scoped to free-flowing chat features
only — conversation / interview_coach / scenario / coaching (roleplay scenarios only) —
deliberately not the assessment/scoring exercises (pronunciation coach, accent
assessment, public speaking, coaching's draft-and-grade scenarios) where a scripted
read-and-score flow doesn't fit a live back-and-forth call.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi.responses import JSONResponse

from lib import ai_client, prompts
from lib.prisma_client import db
from schemas.coaching_schemas import RoleplayTurnSchema
from schemas.conversation_schemas import SendMessageSchema
from schemas.interview_coach_schemas import AnswerRequest
from schemas.scenario_schemas import ScenarioTurnSchema
from services import coaching_service, conversation_service, interview_coach_service, scenario_service
from utils.feature_errors import SessionNotFoundError

_FEATURES = ("conversation", "interview_coach", "scenario", "coaching")


@dataclass
class LiveCallSetup:
    instructions: str
    opening_line: str
    turn_handler: Callable[[str], Awaitable[str]]


def parse_room_name(room_name: str) -> tuple[str, str]:
    """"livecall_{feature}_{session_id}" (services/live_call_service.py). Matched against
    the known feature list rather than a blind split — "interview_coach" and
    "public_speaking" contain underscores themselves, so a plain split(_, 2) would cut
    the feature name in the wrong place."""
    body = room_name.removeprefix("livecall_")
    for feature in _FEATURES:
        prefix = f"{feature}_"
        if body.startswith(prefix):
            return feature, body[len(prefix):]
    raise ValueError(f"Unrecognized Live Call room name: {room_name!r}")


async def build_setup(feature: str, session_id: str, user_id: str) -> LiveCallSetup:
    if feature == "conversation":
        return await _build_conversation_setup(session_id, user_id)
    if feature == "interview_coach":
        return await _build_interview_coach_setup(session_id, user_id)
    if feature == "scenario":
        return await _build_scenario_setup(session_id, user_id)
    if feature == "coaching":
        return await _build_coaching_setup(session_id, user_id)
    raise NotImplementedError(f"Live Call not wired up yet for feature={feature!r}")


async def _build_conversation_setup(session_id: str, user_id: str) -> LiveCallSetup:
    session = await conversation_service._get_session(session_id, user_id)
    instructions = conversation_service._build_system_prompt(session)
    opening_line = await ai_client.generate(
        system_prompt=instructions,
        user_message=(
            "Greet the caller warmly in one short sentence, like you just answered a "
            "phone call, and invite them to start talking about this topic."
        ),
        max_tokens=60,
    )

    async def turn_handler(user_text: str) -> str:
        # Same function a typed or push-to-talk turn already goes through — safety
        # checks, prompt-building, and turn persistence all happen inside it, so a Live
        # Call turn lands in the session's normal history exactly like any other input
        # mode. This is also what makes "End Call" (as opposed to "End Session") a no-op
        # on the backend: nothing extra needs to be flushed, every turn already persisted
        # as it happened.
        req = SendMessageSchema(text=user_text, input_mode="audio")
        result = await conversation_service._send_message(user_id, session_id, req)
        return result["reply"]

    return LiveCallSetup(instructions=instructions, opening_line=opening_line, turn_handler=turn_handler)


async def _build_interview_coach_setup(session_id: str, user_id: str) -> LiveCallSetup:
    session = await interview_coach_service._get_session(session_id, user_id)
    # Interview Coach builds its system prompt fresh per-turn inside _submit_answer's
    # own call chain (_generate_next_question etc, keyed off live round/persona state) —
    # there's no single static session-level prompt the way Conversation has one.
    # `instructions` here is framework bookkeeping only; turn_handler below never reads
    # it, so it doesn't need to (and can't cheaply) mirror that per-turn logic.
    instructions = f"You are conducting {interview_coach_service._persona_description(session)}."
    exchanges = session["exchanges"]
    # _start_session always seeds exchanges[0] with the opening question — the caller
    # either hasn't answered it yet (fresh join) or has (re-joining mid-interview via
    # Live Call after some text turns); either way it's the last thing the AI said,
    # which is the natural thing to speak first on connect.
    opening_line = exchanges[-1]["question"] if exchanges else "Let's begin — tell me about yourself."

    async def turn_handler(user_text: str) -> str:
        req = AnswerRequest(answer_text=user_text)
        result = await interview_coach_service._submit_answer(user_id, session_id, req)
        return result.next_question or "That wraps up this interview — great work today."

    return LiveCallSetup(instructions=instructions, opening_line=opening_line, turn_handler=turn_handler)


async def _build_scenario_setup(session_id: str, user_id: str) -> LiveCallSetup:
    row = await db.scenariosession.find_unique(where={"id": session_id})
    if not row or row.userId != user_id:
        raise SessionNotFoundError(f"Scenario session {session_id} not found")

    # CM-US-04: meta frozen at start_session (matches send_turn's own rule — an admin
    # edit mid-conversation must not change this session's persona/prompt/rules).
    meta = row.scenarioMeta or await scenario_service.scenario_meta(row.scenarioKey)
    instructions = prompts.build_scenario_roleplay_prompt(meta)
    # turns always ends on an assistant line (start_session seeds turns[0] with the
    # opening; send_turn only ever returns after appending its own reply) — that's
    # exactly what should be spoken first on connect, same reasoning as Interview Coach.
    opening_line = row.turns[-1]["content"] if row.turns else meta.get("opening_fallback", "Let's begin.")

    async def turn_handler(user_text: str) -> str:
        result = await scenario_service.send_turn(session_id, ScenarioTurnSchema(message=user_text), user_id)
        if isinstance(result, JSONResponse):
            return "Sorry, something went wrong there — let's try again."
        return result["reply"]

    return LiveCallSetup(instructions=instructions, opening_line=opening_line, turn_handler=turn_handler)


async def _build_coaching_setup(session_id: str, user_id: str) -> LiveCallSetup:
    row = await db.coachingsession.find_unique(where={"id": session_id})
    if not row or row.userId != user_id:
        raise SessionNotFoundError(f"Coaching session {session_id} not found")

    # Only client_communication/meeting_communication are roleplay=True (interactive,
    # multi-turn) — the other scenarios (email_writing, presentation_prep,
    # general_workplace) are single-submission draft-and-grade, no turns to call into.
    scenario_key = coaching_service.SCENARIO_ENUM_TO_KEY[row.scenario]
    meta = coaching_service.scenario_meta(scenario_key)
    if not meta or not meta["roleplay"]:
        raise SessionNotFoundError(f"Coaching session {session_id} is not an interactive roleplay")

    instructions = prompts.build_workplace_roleplay_prompt(scenario_key, row.promptText)
    # start_session doesn't persist its opening_message into turns (only returns it),
    # so a fresh join regenerates one the same way; a mid-conversation join speaks the
    # last thing the AI said, same reasoning as Scenario/Interview Coach above.
    turns = list(row.turns)
    opening_line = (
        turns[-1]["content"] if turns
        else await coaching_service._roleplay_opening(scenario_key, row.promptText)
    )

    async def turn_handler(user_text: str) -> str:
        result = await coaching_service.roleplay_turn(session_id, RoleplayTurnSchema(message=user_text), user_id)
        if isinstance(result, JSONResponse):
            return "Sorry, something went wrong there — let's try again."
        return result["reply"]

    return LiveCallSetup(instructions=instructions, opening_line=opening_line, turn_handler=turn_handler)
