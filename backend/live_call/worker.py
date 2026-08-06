"""Live Call agent worker entrypoint.

Run locally while iterating (auto-reconnects, verbose):
    uv run python -m live_call.worker dev
Run as the long-running deployed worker:
    uv run python -m live_call.worker start

Deliberately NOT part of the FastAPI process (backend/main.py) — LiveKit Cloud
dispatches one job per room to this worker. It talks to Postgres directly
(lib.prisma_client.db) and imports services/* directly, so a Live Call session's data
is identical in shape to a typed/push-to-talk one — no HTTP relay back to the API.
"""

import asyncio
import contextlib
import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, stt
from livekit.agents.voice.turn import TurnHandlingOptions
from livekit.plugins import silero
from prisma.engine.errors import EngineError

from lib.prisma_client import db
from live_call import dispatch
from live_call.llm_plugin import ServiceLLM
from live_call.stt_plugin import WhisperSTT
from live_call.tts_plugin import PiperTTS

load_dotenv(override=True)
logger = logging.getLogger("live-call-agent")

# `dev` mode's CLI defaults the root logger to DEBUG, which makes every prisma query,
# every piper phoneme breakdown, and asyncio's own internals print on every turn. None
# of that is actionable here — keep our own + livekit.agents' lifecycle/warning logs,
# drop the rest.
for _noisy in ("prisma", "asyncio", "piper"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logging.getLogger("livekit").setLevel(logging.INFO)

_db_connected = False
_db_lock = asyncio.Lock()


async def _ensure_db_connected() -> None:
    global _db_connected
    if _db_connected:
        return
    async with _db_lock:
        if not _db_connected:
            await db.connect()
            _db_connected = True


async def _reset_db_connection() -> None:
    """`_db_connected` was a connect-once-ever flag — once True it stayed True even
    if the query engine process died underneath it (DB restart, OOM, network drop),
    so every job after that failed forever until someone restarted the whole worker.
    Drop the stale engine handle and clear the flag so the next job's
    `_ensure_db_connected()` spins up a fresh one instead of reusing a dead one."""
    global _db_connected
    async with _db_lock:
        _db_connected = False
        with contextlib.suppress(Exception):
            await db.disconnect()


_SETUP_TIMEOUT_S = 15


async def _speak_and_disconnect(ctx: agents.JobContext, message: str) -> None:
    """DB/session lookup failed — leaving the caller in silence staring at "Connecting…"
    forever is worse than a short spoken apology. TTS-only session, no STT/LLM needed."""
    session = AgentSession(tts=PiperTTS())
    await session.start(room=ctx.room, agent=Agent(instructions=message))
    handle = session.say(message)
    await handle.wait_for_playout()
    await ctx.shutdown(reason="live call setup failed")


async def entrypoint(ctx: agents.JobContext) -> None:
    # Join the room FIRST, before anything DB-dependent — a slow/unreachable database
    # must never block the room join itself, or the caller sees an agent that never
    # even connects (indistinguishable from a crash) instead of a spoken error.
    await ctx.connect()

    feature, session_id = dispatch.parse_room_name(ctx.room.name)
    participant = await ctx.wait_for_participant()
    user_id = participant.identity  # set via .with_identity(user_id) at token mint time
    logger.info(
        "Live Call job: feature=%s session_id=%s participant_identity=%s", feature, session_id, user_id
    )

    try:
        await asyncio.wait_for(_ensure_db_connected(), timeout=_SETUP_TIMEOUT_S)
        setup = await asyncio.wait_for(
            dispatch.build_setup(feature, session_id, user_id), timeout=_SETUP_TIMEOUT_S
        )
    except (EngineError, asyncio.TimeoutError):
        # Engine-level failure or a hang long enough to time out — force a reconnect.
        logger.exception("Live Call DB engine unhealthy; forcing reconnect: feature=%s session_id=%s", feature, session_id)
        await _reset_db_connection()
        await _speak_and_disconnect(
            ctx, "Sorry, I'm having trouble connecting right now. Please try again in a moment."
        )
        return
    except Exception:
        logger.exception("Live Call setup failed: feature=%s session_id=%s", feature, session_id)
        await _speak_and_disconnect(
            ctx, "Sorry, I'm having trouble connecting right now. Please try again in a moment."
        )
        return

    # One VAD instance shared by the STT segmentation adapter and the session's own
    # turn-taking/interruption detection — two distinct concerns, no reason to load the
    # Silero model twice in the same process.
    #
    # min_silence_duration is longer than push-to-talk's 0.55s (lib/voice_ws.py):
    # push-to-talk is "read one sentence", Live Call is free conversation where an ESL
    # learner routinely pauses mid-sentence to find a word. At 0.55s that pause reads as
    # "done talking" — the fragment gets sent as its own turn, generates an off-topic
    # reply, and the rest of what they were saying becomes a second, disconnected turn
    # (this is what looked like "no answer, then a doubled message").
    vad = silero.VAD.load(min_silence_duration=1.1)
    session = AgentSession(
        stt=stt.StreamAdapter(stt=WhisperSTT(), vad=vad),
        llm=ServiceLLM(setup.turn_handler),
        tts=PiperTTS(),
        vad=vad,
        # Our STT is a single batch transcription per utterance, not a real streaming
        # STT with interim results — LiveKit's default smart turn-detector expects the
        # latter (it makes a semantic "is this sentence actually finished" call over
        # interim text, which timed out and mis-fired here, cutting users off mid-
        # sentence). Plain VAD silence-based endpointing, on both turn-taking and
        # interruption detection, matches what we can actually signal from a batch STT.
        turn_handling=TurnHandlingOptions(
            turn_detection="vad",
            endpointing={"min_delay": 1.1, "max_delay": 5.0},
            interruption={"mode": "vad"},
        ),
    )
    await session.start(room=ctx.room, agent=Agent(instructions=setup.instructions))

    # The caller's mic is live the instant start() returns, and our STT is a single
    # batch transcription per VAD segment, not a real streaming one — if the canned
    # opener starts playing on top of speech that's already in progress, the framework
    # commits whatever's buffered as its own turn the moment agent speech begins, which
    # is what split a caller's opening sentence into two disconnected turns. Skip the
    # greeting if they've already started talking (their utterance becomes the natural
    # first turn instead), and bail out of it early if they start mid-line too.
    if session.user_state == "speaking":
        return

    greeting = session.say(setup.opening_line)

    def _yield_floor_if_user_speaks(ev) -> None:
        if ev.new_state == "speaking":
            greeting.interrupt()

    session.on("user_state_changed", _yield_floor_if_user_speaks)
    try:
        await greeting
    finally:
        session.off("user_state_changed", _yield_floor_if_user_speaks)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
