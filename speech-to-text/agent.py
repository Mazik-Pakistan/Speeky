import asyncio
import logging
import wave
from faster_whisper import WhisperModel
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents import vad as agents_vad
from livekit.plugins import silero

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stt-test-agent")


async def process_audio(track: rtc.Track, identity: str, vad: silero.VAD):
    """Feed incoming audio frames into Silero VAD and log speech boundaries."""
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
                logger.info("Speech ENDED (%s)", identity)
                logger.info("Frames: %d", len(event.frames))
                frame = event.frames[0]
                logger.info(
                    "sample_rate=%d channels=%d samples=%d",
                    frame.sample_rate,
                    frame.num_channels,
                    frame.samples_per_channel,
                )
                save_wav(frame)
                logger.info("Saved speech.wav")
                logger.info("Starting Whisper transcription...")
                transcribe_audio()
                logger.info("Whisper transcription finished.")
    await asyncio.gather(forward_frames(), read_vad_events())


def save_wav(frame, filename="speech.wav"):
    with wave.open(filename, "wb") as wav:
        wav.setnchannels(frame.num_channels)
        wav.setsampwidth(2)  # int16 = 2 bytes
        wav.setframerate(frame.sample_rate)
        wav.writeframes(frame.data)

model = WhisperModel("base",device="cpu",compute_type="int8",)

def transcribe_audio(filename="speech.wav"):
    segments, info = model.transcribe(filename,beam_size=5,)
    logger.info("\n========== TRANSCRIPT ==========")
    for segment in segments:
        logger.info(segment.text)
    logger.info("================================\n")
async def entrypoint(ctx: JobContext):
    await ctx.connect()
    logger.info("SUCCESS: Agent connected to room: %s", ctx.room.name)

    logger.info("Loading Silero VAD model...")
    vad = silero.VAD.load()
    logger.info("VAD model loaded.")

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant):
        logger.info(
            "Track subscribed: kind=%s from participant=%s",
            track.kind,
            participant.identity,
        )
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(process_audio(track, participant.identity, vad))

    # Keep the agent alive to keep listening
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))