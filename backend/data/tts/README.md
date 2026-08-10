# TTS voice model

`en_US-lessac-medium.onnx` + `.onnx.json` — a [Piper](https://github.com/OHF-Voice/piper1-gpl)
neural voice, used by `lib/tts_client.py` for AIC-US-16 (TTS playback).

Not committed to git (63MB binary, `.gitignore`d) — copy it here manually, or download it:

```
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

Override the filename via `TTS_VOICE_MODEL` env var if you use a different voice. Without
this file, `lib.tts_client.is_configured()` returns `False` and `/api/conversation/tts`
returns 503 — the client is expected to fall back to its own native TTS in that case.
