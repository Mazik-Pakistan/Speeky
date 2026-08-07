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
import os

from dotenv import load_dotenv

load_dotenv(override=True)  # must run before any project-lib import for proper envs.

import numpy as np
from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, stt
from livekit.agents.voice.turn import TurnHandlingOptions
from livekit.plugins import bey, silero
from prisma.engine.errors import EngineError

from lib import stt_engine, tts_client
from lib.prisma_client import db
from lib.speech_config import load_speech_config
from live_call import dispatch
from live_call.llm_plugin import ServiceLLM
from live_call.stt_plugin import WhisperSTT
from live_call.tts_plugin import PiperTTS

logger = logging.getLogger("live-call-agent")

# `dev` mode's CLI defaults the root logger to DEBUG, which makes every query call breakdown so reduce that to warning level.
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
    """ _ensure_db_connected() spins up a fresh one instead of reusing a dead one."""
    global _db_connected
    async with _db_lock:
        _db_connected = False
        with contextlib.suppress(Exception):
            await db.disconnect()


_SETUP_TIMEOUT_S = 15


def _prewarm(proc: agents.JobProcess) -> None:
    """Runs once per worker subprocess, before it accepts any job — loads Silero
    once instead of on every entrypoint() call (official LiveKit prewarm pattern)."""
    proc.userdata["vad"] = silero.VAD.load(min_silence_duration=1.1)


def _warm_stt_tts() -> None:
    """faster-whisper (thread-local) and Piper (process-global) both lazy-load their
    model on first real call — several seconds of load time on top of actual inference.
    That cost lands on whichever turn happens first in a call (the
    canned opener's TTS, or worse, the caller's own STT if they talk over it), reading as the agent going silent. Fired fire-and-forget right after room connect so it overlaps the existing DB/setup awaits instead of adding wall-clock time. Piper's
    warm-up is a permanent win (global singleton); whisper's is best-effort only since
    a later call can still land on a different, cold executor thread."""
    with contextlib.suppress(Exception):
        stt_engine.transcribe(np.zeros(8000, dtype=np.float32), 16000, load_speech_config())
    with contextlib.suppress(Exception):
        tts_client.synthesize(" ")


async def _start_avatar_or_skip(session: AgentSession, room: rtc.Room) -> bool:
    """Optional Beyond Presence lip-synced avatar. Env-gated (unset key or blocked/dropped = audio-call only)."""
    if not os.getenv("BEY_API_KEY"):
        return False
    try:
        avatar = bey.AvatarSession(avatar_id=os.getenv("BEY_AVATAR_ID","694c83e2-8895-4a98-bd16-56332ca3f449"))
        await asyncio.wait_for(avatar.start(session, room=room), timeout=_SETUP_TIMEOUT_S)
        return True
    except Exception:
        logger.exception("Beyond Presence avatar failed to start; continuing audio-only")
        return False


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
    asyncio.create_task(asyncio.to_thread(_warm_stt_tts))

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
    # "done talking"
    vad = ctx.proc.userdata["vad"]
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
        #
        # "dynamic" mode starts at min_delay (snappier than the old fixed 1.1s) and
        # learns this caller's actual pause length from their own speech, floating the
        # wait up toward max_delay when they hesitate mid-sentence — fast by default,
        # still forgiving of a real pause, instead of every user paying a flat tax.
        turn_handling=TurnHandlingOptions(
            turn_detection="vad",
            endpointing={"mode": "dynamic", "min_delay": 0.7, "max_delay": 5.0},
            interruption={"mode": "vad"},
        ),
    )
    await _start_avatar_or_skip(session, ctx.room)
    await session.start(room=ctx.room, agent=Agent(instructions=setup.instructions))

    # Voice barge-in (talking over the agent) is already handled by
    # TurnHandlingOptions(interruption={"mode": "vad"}) above — the framework cuts off
    # whatever's currently playing the instant VAD detects the user speaking. This adds
    # the other trigger the frontend wants: a manual "interrupt" button for when the
    # user wants to jump in without out-talking the agent. 
    def _on_interrupt_rpc(_data: rtc.RpcInvocationData) -> str:
        session.interrupt()
        return "ok"

    ctx.room.local_participant.register_rpc_method("interrupt_agent", _on_interrupt_rpc)

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
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=_prewarm))
