"""
STEP 4b (updated): Join a LiveKit room AND publish your microphone audio.

Earlier version only joined the room without sending any audio - that's
why the agent's VAD never saw anything. This version captures your mic
(same way real_time_stt.py did) and publishes it into the room, so the
agent can actually detect your speech.

INSTALL (if not already):
   pip install livekit livekit-api sounddevice

HOW TO RUN:
1. Keep agent.py running in its own terminal (python agent.py dev).
2. In a second terminal, run: python join_test_room.py
3. It will say "Publishing microphone audio..." - speak normally.
4. Watch the agent.py terminal for "Track subscribed" and then
   "Speech STARTED" / "Speech ENDED" lines.
5. Press Ctrl+C here when done.
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

    print("Publishing microphone audio to the room. Speak now!")
    print("Press Ctrl+C to stop.")

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
