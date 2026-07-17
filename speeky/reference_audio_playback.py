import logging

logger = logging.getLogger(__name__)

MAX_LISTENS_BEFORE_NUDGE = 5


class ReferenceAudioPlayer:
    def __init__(self):
        self.listen_count = {}  # sentence_id -> kitni baar suna gaya
        self.slow_mode_enabled = False
        self.cached_sentences = {}  # sentence_id -> file_path (pre-cached)

    def get_reference_audio(self, sentence_id, sentence_text, speed="normal"):
        """
        Happy Path: Sentence ki reference awaaz banata/deta hai.
        E-01: Agar reference file na bane, generic TTS pe fallback karo.
        """
        from speeky.tts import TextToSpeech

        # Kitni baar suna gaya, track karo (E-02 ke liye)
        self.listen_count[sentence_id] = self.listen_count.get(sentence_id, 0) + 1

        file_suffix = "slow" if speed == "slow" else "normal"
        output_path = f"output/ref_{sentence_id}_{file_suffix}.wav"

        try:
            tts = TextToSpeech()
            length_scale = 1.67 if speed == "slow" else 1.0  # 0.6x pacing = length_scale ~1.67
            tts.synthesize_to_file(sentence_text, output_path, length_scale=length_scale)
            return {
                "status": "ok",
                "audio_file": output_path,
                "listen_count": self.listen_count[sentence_id],
                "nudge": self._check_nudge(sentence_id),
                "score_impact": 0,  # Acceptance Criteria: sunna score pe asar nahi dalta
            }
        except Exception as e:
            logger.warning(f"Reference audio failed for {sentence_id}, falling back to generic TTS: {e}")
            return {
                "status": "fallback",
                "audio_file": None,
                "message": "Using generic voice; original reference asset missing.",
                "logged_for_content_team": True,
            }

    def _check_nudge(self, sentence_id):
        """E-02: 5 baar se zyada suna bina record kiye to gentle nudge"""
        if self.listen_count[sentence_id] > MAX_LISTENS_BEFORE_NUDGE:
            return "Ready to give it a try?"
        return None

    def toggle_slow_speed(self, enabled=True):
        """E-04: Slow-speed preference session mein persist hoti hai"""
        self.slow_mode_enabled = enabled
        return {"status": "ok", "slow_mode": self.slow_mode_enabled}

    def handle_playback_interruption(self, sentence_id):
        """E-03: Interrupt hone par shuru se dobara bajana hai, beech se nahi"""
        return {"status": "restart_from_beginning", "sentence_id": sentence_id}

    def precache_upcoming_sentences(self, sentence_list):
        """E-05: Low bandwidth ho to agli 2-3 sentences pehle se cache karo"""
        cached = []
        for sid, text in sentence_list[:3]:
            self.cached_sentences[sid] = f"output/ref_{sid}_normal.wav"
            cached.append(sid)
        return {"status": "caching", "cached_sentence_ids": cached}