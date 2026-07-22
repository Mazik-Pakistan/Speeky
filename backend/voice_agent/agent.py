"""
Speeky AI - LiveKit Speech-to-Text Worker

Pipeline:
LiveKit audio
    -> Silero VAD
    -> Faster-Whisper
    -> FastAPI conversation backend

The LiveKit room name is the conversation session ID (conv_...).

The worker listens to microphone tracks, detects complete speech
utterances with Silero VAD, transcribes them using Faster-Whisper,
and sends valid transcripts to the backend.

Run:
    python agent.py dev
"""

import asyncio
import logging
import os
import tempfile
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


BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "http://localhost:8000",
)

INTERNAL_AGENT_SECRET = os.environ["INTERNAL_AGENT_SECRET"]


# Very short segments are commonly clicks, microphone noise,
# screen-reader leakage, or incomplete speech.
MIN_UTTERANCE_SECONDS = 0.5


logger.info("Loading Faster-Whisper model...")

model = WhisperModel(
    "small.en",
    device="cpu",
    compute_type="int8",
)

logger.info("Faster-Whisper model loaded.")


def save_temp_wav(frames):
    """
    Save one utterance to its own temporary WAV file.

    A unique temporary file prevents different users or overlapping
    utterances from overwriting the same speech.wav file.
    """

    first = frames[0]

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    )

    filename = temp_file.name
    temp_file.close()

    with wave.open(filename, "wb") as wav:
        wav.setnchannels(first.num_channels)
        wav.setsampwidth(2)
        wav.setframerate(first.sample_rate)

        for frame in frames:
            wav.writeframes(frame.data)

    return filename


def transcribe_audio(filename):
    """
    Transcribe one utterance.

    Returns:
        transcript
        word_timings
    """

    segments, _info = model.transcribe(
        filename,
        language="en",
        beam_size=5,
        word_timestamps=True,
        condition_on_previous_text=False,
        vad_filter=False,
    )

    text_parts = []
    word_timings = []

    for segment in segments:
        text = segment.text.strip()

        if text:
            text_parts.append(text)

        for word in segment.words or []:
            cleaned_word = word.word.strip()

            if cleaned_word:
                word_timings.append(
                    {
                        "word": cleaned_word,
                        "start": word.start,
                        "end": word.end,
                    }
                )

    transcript = " ".join(text_parts).strip()

    return transcript, word_timings


async def send_transcript_to_backend(
    session_id,
    transcript,
    word_timings,
    duration_seconds,
):
    """
    Send a successfully recognized utterance to the conversation backend.
    """

    payload = {
        "input_mode": "audio",
        "audio_features": {
            "transcript": transcript,
            "duration_seconds": duration_seconds,
            "word_timings": word_timings,
        },
    }

    url = (
        f"{BACKEND_URL}/api/conversation/internal/"
        f"sessions/{session_id}/agent-message"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "X-Internal-Secret": INTERNAL_AGENT_SECRET
                },
            )

            response.raise_for_status()

            data = response.json()

            logger.info(
                "Transcript delivered successfully for session %s",
                session_id,
            )

            logger.info(
                "Backend reply: %s",
                data.get("reply"),
            )

    except httpx.HTTPError:
        logger.exception(
            "Failed to deliver transcript for session %s",
            session_id,
        )


async def process_utterance(
    frames,
    identity,
    session_id,
):
    """
    Process one complete speech utterance independently.

    Whisper runs in a worker thread so CPU-heavy transcription does not
    block LiveKit's asyncio event loop.
    """

    if not frames:
        return

    sample_rate = frames[0].sample_rate
    logger.info(
        "Audio received (%s): sample_rate=%d channels=%d frames=%d",
        identity,
        sample_rate,
        frames[0].num_channels,
        len(frames),
    )

    total_samples = sum(
        frame.samples_per_channel
        for frame in frames
    )

    duration_seconds = total_samples / sample_rate

    logger.info(
        "Utterance duration (%s): %.2f seconds",
        identity,
        duration_seconds,
    )

    if duration_seconds < MIN_UTTERANCE_SECONDS:
        logger.info(
            "Utterance too short (%s) - not sent to Whisper",
            identity,
        )
        return

    filename = None

    try:
        filename = save_temp_wav(frames)

        logger.info(
            "Starting Whisper transcription (%s)",
            identity,
        )

        transcript, word_timings = await asyncio.to_thread(
            transcribe_audio,
            filename,
        )

        if not transcript:
            logger.info(
                "Whisper returned no usable speech (%s) - skipping",
                identity,
            )
            return

        logger.info(
            "TRANSCRIPT (%s): %s",
            identity,
            transcript,
        )

        logger.info(
            "Sending transcript to backend for session %s",
            session_id,
        )

        await send_transcript_to_backend(
            session_id,
            transcript,
            word_timings,
            duration_seconds,
        )

    except Exception:
        logger.exception(
            "Failed to process utterance for %s",
            identity,
        )

    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                logger.warning(
                    "Could not remove temporary audio file",
                )


async def process_audio(
    track,
    identity,
    vad,
    session_id,
):
    """
    Continuously feed one participant's LiveKit audio into Silero VAD.
    """

    audio_stream = rtc.AudioStream(track)
    vad_stream = vad.stream()

    utterance_tasks = set()

    async def forward_frames():
        try:
            async for event in audio_stream:
                vad_stream.push_frame(event.frame)

        finally:
            vad_stream.end_input()

    async def read_vad_events():
        async for event in vad_stream:

            if event.type == agents_vad.VADEventType.START_OF_SPEECH:

                logger.info(
                    "Speech STARTED (%s)",
                    identity,
                )

            elif event.type == agents_vad.VADEventType.END_OF_SPEECH:

                logger.info(
                    "Speech ENDED (%s)",
                    identity,
                )

                task = asyncio.create_task(
                    process_utterance(
                        event.frames,
                        identity,
                        session_id,
                    )
                )

                utterance_tasks.add(task)

                task.add_done_callback(
                    utterance_tasks.discard
                )

    try:
        await asyncio.gather(
            forward_frames(),
            read_vad_events(),
        )

    except asyncio.CancelledError:
        logger.info(
            "Audio processing stopped for %s",
            identity,
        )
        raise


async def entrypoint(ctx: JobContext):

    await ctx.connect()

    session_id = ctx.room.name

    logger.info(
        "Agent connected to room: %s",
        session_id,
    )

    logger.info(
        "Loading Silero VAD model..."
    )

    vad = silero.VAD.load()

    logger.info(
        "Silero VAD model loaded."
    )

    audio_tasks = set()

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track,
        publication,
        participant,
    ):

        logger.info(
            "Track subscribed: kind=%s participant=%s",
            track.kind,
            participant.identity,
        )

        if track.kind == rtc.TrackKind.KIND_AUDIO:

            task = asyncio.create_task(
                process_audio(
                    track,
                    participant.identity,
                    vad,
                    session_id,
                )
            )

            audio_tasks.add(task)

            task.add_done_callback(
                audio_tasks.discard
            )

    try:
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        logger.info(
            "LiveKit job ending for session %s",
            session_id,
        )

        for task in audio_tasks:
            task.cancel()

        if audio_tasks:
            await asyncio.gather(
                *audio_tasks,
                return_exceptions=True,
            )

        raise


if __name__ == "__main__":

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint
        )
    )
