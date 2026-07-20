"""LiveKit room-token minting for AI Conversation Practice's voice mode.

The backend still never touches raw audio (see conversation_service.py) — this
module only signs a short-lived join token so the client can publish its mic into
a LiveKit room, and the voice_agent/ worker can subscribe and transcribe it.
"""

import os

from livekit import api


def is_configured() -> bool:
    return bool(
        os.environ.get("LIVEKIT_URL")
        and os.environ.get("LIVEKIT_API_KEY")
        and os.environ.get("LIVEKIT_API_SECRET")
    )


def mint_room_token(room: str, identity: str) -> dict:
    token = (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return {"url": os.environ["LIVEKIT_URL"], "token": token, "room": room}
