"""Publish test mic audio into a room without a frontend.

    1. python agent.py dev            (own terminal)
    2. python join_test_room.py       (own terminal, speak into your mic)

Uses ROOM_NAME="test-room" — not a real session_id, so agent.py's POST back to
the backend will 404 (no such session). That's expected here: this script only
exercises the LiveKit connect + VAD + Whisper pipeline, watch agent.py's log.
"""

import asyncio
import os
import queue

import sounddevice as sd
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv()

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
API_KEY = os.environ["LIVEKIT_API_KEY"]
API_SECRET = os.environ["LIVEKIT_API_SECRET"]

ROOM_NAME = "test-room"
SAMPLE_RATE = 16000
NUM_CHANNELS = 1
BLOCK_SIZE = 800  # 50ms of audio per chunk at 16kHz

audio_queue = queue.Queue()


def mic_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(bytes(indata))


async def main():
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("test-user")
        .with_name("Test User")
        .with_grants(api.VideoGrants(room_join=True, room=ROOM_NAME))
        .to_jwt()
    )

    room = rtc.Room()
    await room.connect(LIVEKIT_URL, token)
    print(f"Connected to room: {room.name} as 'test-user'")

    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(track, options)

    mic_stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        channels=NUM_CHANNELS,
        callback=mic_callback,
    )
    mic_stream.start()

    print("Publishing microphone audio to the room. Speak now! Ctrl+C to stop.")

    loop = asyncio.get_event_loop()
    try:
        while True:
            data = await loop.run_in_executor(None, audio_queue.get)
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
