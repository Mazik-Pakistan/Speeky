# TTS voice model

A [Piper](https://github.com/OHF-Voice/piper1-gpl) neural voice (`.onnx` + `.onnx.json`), used by
`lib/tts_client.py` for AIC-US-16 (TTS playback) and by `live_call/` for the avatar's speech.

**The filename here must match whatever `TTS_VOICE_MODEL` is set to in `.env`** — `tts_client.py`
looks for exactly that name and nothing else. It defaults to `en_US-lessac-medium.onnx` only when
the var is unset. Download both files for your configured voice from
`https://huggingface.co/rhasspy/piper-voices/resolve/main/en/{lang}/{voice}/{quality}/`, e.g.:

```
# en_GB-alba-medium (TTS_VOICE_MODEL=en_GB-alba-medium.onnx)
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alba/medium/en_GB-alba-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alba/medium/en_GB-alba-medium.onnx.json

# en_US-lessac-medium (the default when TTS_VOICE_MODEL is unset)
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

Not committed to git (63MB binary, `.gitignore`d), so this has to be redone per machine. Without a
matching file, `lib.tts_client.is_configured()` returns `False`: `/api/conversation/tts` returns
503 (the client falls back to its own native TTS), and a Live Call agent has no voice — it joins
the room but cannot speak.
