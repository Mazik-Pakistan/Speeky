import asyncio
import queue

import sounddevice as sd
from livekit import rtc


LIVEKIT_URL = "wss://mazik2026-heeytr6k.livekit.cloud"

# Paste a FRESH token returned by:
# POST /api/conversation/sessions/{session_id}/voice-token
LIVEKIT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ2aWRlbyI6eyJyb29tSm9pbiI6dHJ1ZSwicm9vbSI6ImNvbnZfYWQyZTE5YjI3MTFhIiwiY2FuUHVibGlzaCI6dHJ1ZSwiY2FuU3Vic2NyaWJlIjp0cnVlLCJjYW5QdWJsaXNoRGF0YSI6dHJ1ZX0sInN1YiI6ImNtcnQwZmFnejAwMWQ1eWgzNm5pZ2l2eHoiLCJpc3MiOiJBUElmRWlHeXhNaDViOE0iLCJuYmYiOjE3ODQ2NTU1NjYsImV4cCI6MTc4NDY3NzE2Nn0.ycL3pmd9z3yZkbJ3I9C-iIyKR_Xz98pimRMvaLjVQ_Q"

SAMPLE_RATE = 16000
NUM_CHANNELS = 1
BLOCK_SIZE = 800

audio_queue = queue.Queue()


def mic_callback(indata, frames, time, status):
    if status:
        print(status)

    audio_queue.put(bytes(indata))


async def main():
    room = rtc.Room()

    await room.connect(LIVEKIT_URL, LIVEKIT_TOKEN)

    print(f"Connected to real conversation room: {room.name}")

    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)

    track = rtc.LocalAudioTrack.create_audio_track(
        "mic",
        source,
    )

    options = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_MICROPHONE
    )

    await room.local_participant.publish_track(track, options)

    mic_stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        channels=NUM_CHANNELS,
        callback=mic_callback,
    )

    mic_stream.start()

    print("Microphone published.")
    print("Speak normally.")
    print("Press Ctrl+C to stop.")

    loop = asyncio.get_event_loop()

    try:
        while True:
            data = await loop.run_in_executor(
                None,
                audio_queue.get,
            )

            frame = rtc.AudioFrame(
                data=data,
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=len(data) // 2,
            )

            await source.capture_frame(frame)

    except KeyboardInterrupt:
        pass

    finally:
        mic_stream.stop()
        mic_stream.close()

        await room.disconnect()

        print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())