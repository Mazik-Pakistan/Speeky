"""
faster-whisper wrapper — same STT engine already used in backend/voice_agent/agent.py
for live conversation practice; here it runs in-process against a one-shot upload
instead of a streamed LiveKit utterance.

Gives word-level timestamps *and* per-word confidence (`probability`), which
lib/text_alignment.py and services/pronunciation_coach_service.py use to tell a
mispronounced word apart from a skipped one.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from faster_whisper import WhisperModel

from lib.speech_config import SpeechConfig

_model: Optional[WhisperModel] = None
_model_key: Optional[tuple] = None


def _get_model(config: SpeechConfig) -> WhisperModel:
    global _model, _model_key
    key = (config.stt_model_size, config.stt_device, config.stt_compute_type)
    if _model is None or _model_key != key:
        _model = WhisperModel(config.stt_model_size, device=config.stt_device, compute_type=config.stt_compute_type)
        _model_key = key
    return _model


@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptionResult:
    text: str
    words: List[WordTiming]


def transcribe(waveform: np.ndarray, sample_rate: int, config: SpeechConfig) -> TranscriptionResult:
    """Transcribe a mono float32 waveform. faster-whisper's numpy-array input path
    expects 16kHz PCM — the recording engine always decodes at config.audio_sample_rate,
    so this is a guard against a misconfigured .env, not a normal runtime path."""
    if sample_rate != 16000:
        raise ValueError(f"faster-whisper expects 16000 Hz audio for array input, got {sample_rate}")

    model = _get_model(config)
    segments, _info = model.transcribe(
        waveform.astype(np.float32), beam_size=5, word_timestamps=True, language="en"
    )

    words: List[WordTiming] = []
    text_parts: List[str] = []
    for segment in segments:
        text_parts.append(segment.text)
        for w in segment.words or []:
            words.append(
                WordTiming(word=w.word.strip(), start=w.start, end=w.end, probability=w.probability)
            )

    return TranscriptionResult(text=" ".join(p.strip() for p in text_parts).strip(), words=words)
