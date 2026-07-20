"""
LiveKit worker: subscribes to a conversation room's mic track, runs Silero VAD to find
speech boundaries, transcribes each utterance with faster-whisper (word-level timing),
and posts the result to the backend's AIC-US-16 voice intake endpoint as an
AudioFeaturesSchema turn — the contract conversation_service.py / session_scorer.py
already expect.

Room naming convention: conversation_service._start_session sets room_name = session_id
(session ids are already generated as "conv_<hex>" — see
Speeky/backend/services/conversation_service.py). ctx.room.name IS the session_id, no
transform needed on either side.

Run: python agent.py dev   (needs its own venv — see requirements.txt; kept separate
from the API server's deps since faster-whisper/silero pull in torch/ctranslate2).
"""

import asyncio
import logging
import os
import wave

import httpx
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents import vad as agents_vad
from livekit.plugins import silero

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
INTERNAL_AGENT_SECRET = os.environ["INTERNAL_AGENT_SECRET"]

model = WhisperModel("base", device="cpu", compute_type="int8")


def save_wav(frames, filename="speech.wav"):
    """Write every frame of the utterance, not just the first — a single VAD segment
    spans many audio frames, and truncating to frames[0] means Whisper only ever sees
    the first ~10-50ms of speech."""
    first = frames[0]
    with wave.open(filename, "wb") as wav:
        wav.setnchannels(first.num_channels)
        wav.setsampwidth(2)  # int16 = 2 bytes
        wav.setframerate(first.sample_rate)
        for frame in frames:
            wav.writeframes(frame.data)


def transcribe_audio(filename="speech.wav"):
    """Returns (transcript, word_timings) where word_timings matches
    AudioFeaturesSchema.word_timings: [{"word", "start", "end"}, ...]."""
    segments, _info = model.transcribe(filename, beam_size=5, word_timestamps=True)
    text_parts = []
    word_timings = []
    for segment in segments:
        text_parts.append(segment.text)
        for w in segment.words or []:
            word_timings.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return " ".join(p.strip() for p in text_parts).strip(), word_timings


async def send_transcript_to_backend(session_id: str, transcript: str, word_timings: list, duration_seconds: float):
    payload = {
        "input_mode": "audio",
        "audio_features": {
            "transcript": transcript,
            "duration_seconds": duration_seconds,
            "word_timings": word_timings,
        },
    }
    url = f"{BACKEND_URL}/api/conversation/internal/sessions/{session_id}/agent-message"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers={"X-Internal-Secret": INTERNAL_AGENT_SECRET})
            resp.raise_for_status()
            logger.info("Backend reply: %s", resp.json().get("reply"))
    except httpx.HTTPError as e:
        # Fire-and-forget per utterance — no retry loop; the next thing the user says
        # is a fresh attempt, same as a dropped word in a live conversation.
        logger.error("Failed to post transcript for session %s: %s", session_id, e)


async def process_audio(track: rtc.Track, identity: str, vad: silero.VAD, session_id: str):
    """Feed incoming audio frames into Silero VAD, transcribe each utterance, forward it."""
    audio_stream = rtc.AudioStream(track)
    vad_stream = vad.stream()

    async def forward_frames():
        async for event in audio_stream:
            vad_stream.push_frame(event.frame)
        vad_stream.end_input()

    async def read_vad_events():
        async for event in vad_stream:
            if event.type == agents_vad.VADEventType.START_OF_SPEECH:
                logger.info("Speech STARTED (%s)", identity)
            elif event.type == agents_vad.VADEventType.END_OF_SPEECH:
                logger.info("Speech ENDED (%s) — %d frames", identity, len(event.frames))
                save_wav(event.frames)

                first, sample_rate = event.frames[0], event.frames[0].sample_rate
                duration_seconds = sum(f.samples_per_channel for f in event.frames) / sample_rate

                transcript, word_timings = transcribe_audio()
                if not transcript.strip():
                    logger.info("Empty transcript (likely noise) — skipping")
                    continue

                logger.info("Transcript: %s", transcript)
                await send_transcript_to_backend(session_id, transcript, word_timings, duration_seconds)

    await asyncio.gather(forward_frames(), read_vad_events())


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    session_id = ctx.room.name
    logger.info("Agent connected to room: %s (session_id=%s)", ctx.room.name, session_id)

    logger.info("Loading Silero VAD model...")
    vad = silero.VAD.load()
    logger.info("VAD model loaded.")

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant):
        logger.info("Track subscribed: kind=%s from participant=%s", track.kind, participant.identity)
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(process_audio(track, participant.identity, vad, session_id))

    await asyncio.Event().wait()  # keep the agent alive to keep listening


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
