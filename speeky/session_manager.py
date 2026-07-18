"""
Session Manager for Speeky - handles US-37 and US-38.

US-37: Seamless Voice-to-Text Mode Switching
    - Lets a learner switch between voice and text input mid-conversation
      without losing conversation history/context.
    - Caches typed text if the network drops (E-01).
    - Locks text input while the mic is actively recording (E-02).
    - Drops the pronunciation score if the voice sample is too short (E-03).

US-38: Text-to-Speech (TTS) Playback for AI Text Chat
    - Lets the learner press a "play" button to hear the AI's text
      reply out loud, using the existing TTS component.
    - Falls back gracefully if TTS fails.

This module wraps the EXISTING pipeline pieces (ConversationEngine, TTS,
ASR, PronunciationScorer) - it does not replace or duplicate them.
"""

import logging
from enum import Enum
from typing import Optional, Dict, List
from datetime import datetime

from .response import ConversationEngine
from .tts import TextToSpeech
from .asr import AutomaticSpeechRecognition
from .pronunciation import PronunciationScorer
from .interview_scenarios import UniversityAdmissionSession

logger = logging.getLogger(__name__)

# US-37, E-03: minimum audio length (seconds) required to score pronunciation
MIN_AUDIO_SECONDS_FOR_PRONUNCIATION = 5.0


class InputMode(str, Enum):
    VOICE = "voice"
    TEXT = "text"


class SessionManager:
    """
    Manages a single AI Conversation practice session that can switch
    between voice and text input mid-session (US-37), and can play back
    the AI's text replies as audio on demand (US-38).
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        asr_model_size: str = "base",
        tts_voice: str = "en_GB-alan-medium",
    ):
        # Reuse the SAME conversation engine used elsewhere in the app.
        # Its internal conversation_history is what keeps context alive
        # across a voice<->text switch (US-37 acceptance criteria #1).
        self.conversation_engine = ConversationEngine(ollama_url=ollama_url)

        # Loaded lazily - only created the first time they're actually needed,
        # so the session starts up fast.
        self._asr: Optional[AutomaticSpeechRecognition] = None
        self._tts: Optional[TextToSpeech] = None
        self._pronunciation_scorer: Optional[PronunciationScorer] = None
        self._asr_model_size = asr_model_size
        self._tts_voice = tts_voice

        # --- Session state ---
        self.current_mode: InputMode = InputMode.VOICE
        self.mic_active: bool = False          # US-37, E-02
        self.text_input_locked: bool = False   # US-37, E-02
        self.cached_text: Optional[str] = None # US-37, E-01
        self.connection_status: str = "online" # "online" | "waiting"

        # Every turn (voice or text) gets logged here for the final scorecard
        self.turns: List[Dict] = []

        # US-50: University Admission scenario (None until explicitly started)
        self.university_session: Optional[UniversityAdmissionSession] = None

    # ------------------------------------------------------------------
    # Lazy-loaded components
    # ------------------------------------------------------------------
    def _get_asr(self) -> AutomaticSpeechRecognition:
        if self._asr is None:
            self._asr = AutomaticSpeechRecognition(model_size=self._asr_model_size)
        return self._asr

    def _get_tts(self) -> TextToSpeech:
        if self._tts is None:
            self._tts = TextToSpeech(voice=self._tts_voice)
        return self._tts

    def _get_pronunciation_scorer(self) -> PronunciationScorer:
        if self._pronunciation_scorer is None:
            self._pronunciation_scorer = PronunciationScorer()
        return self._pronunciation_scorer

    # ------------------------------------------------------------------
    # US-50: University Admission scenario setup
    # ------------------------------------------------------------------
    def start_university_admission(self, degree_text: str) -> Dict:
        """Start (or restart) a University Admission Interview scenario."""
        self.university_session = UniversityAdmissionSession(self.conversation_engine)
        result = self.university_session.set_degree(degree_text)
        return result

    def get_university_question(self) -> Dict:
        """Get the next admission interview question (US-50)."""
        if self.university_session is None:
            return {"status": "error", "ai_message": "Start a university admission session first."}
        return self.university_session.get_question()

    # ------------------------------------------------------------------
    # US-37: Mode switching
    # ------------------------------------------------------------------
    def toggle_mode(self, new_mode: str) -> Dict:
        """Switch between 'voice' and 'text' mode mid-session."""
        new_mode_enum = InputMode(new_mode)

        # E-02 guard: can't switch to text while the mic is recording
        if new_mode_enum == InputMode.TEXT and self.mic_active:
            return {
                "status": "blocked",
                "reason": "Mic is active - release the mic before switching to text.",
            }

        self.current_mode = new_mode_enum
        logger.info(f"Session mode switched to: {self.current_mode}")
        return {"status": "ok", "current_mode": self.current_mode.value}

    # ------------------------------------------------------------------
    # US-37: Mic hold / release (E-02 simultaneous input handling)
    # ------------------------------------------------------------------
    def mic_hold(self):
        """Call this the moment the user presses/holds the mic button."""
        self.mic_active = True
        self.text_input_locked = True

    def mic_release(self, voice_note_sent: bool = True) -> Dict:
        """Call this when the user releases the mic button."""
        self.mic_active = False
        self.text_input_locked = False
        return {"clear_text_field": voice_note_sent}

    # ------------------------------------------------------------------
    # US-37: Sending a VOICE turn
    # ------------------------------------------------------------------
    def send_voice_turn(
        self,
        audio_input,
        sample_rate: int,
        context_type: str = "general",
    ) -> Dict:
        """
        Process one voice turn: transcribe audio, get the AI's reply,
        and score pronunciation ONLY if there was enough audio (E-03).
        """
        audio_duration_sec = len(audio_input) / float(sample_rate)

        # Transcribe using the existing ASR component
        asr = self._get_asr()
        transcription = asr.transcribe(audio_input, sample_rate)
        user_text = transcription["text"]

        # E-03: drop pronunciation metric if the sample is too short
        pronunciation_score = None
        if audio_duration_sec >= MIN_AUDIO_SECONDS_FOR_PRONUNCIATION:
            try:
                scorer = self._get_pronunciation_scorer()
                word_timings = asr.get_word_timings(transcription)
                pron_result = scorer.score_pronunciation(
                    audio_input, sample_rate, word_timings, user_text
                )
                pronunciation_score = pron_result["overall_score"]
            except Exception as e:
                logger.warning(f"Pronunciation scoring skipped: {e}")

        # US-50: route to University Admission scenario if active
        if context_type == "university_admission" and self.university_session is not None:
            scenario_result = self.university_session.submit_answer(user_text)
            ai_response = scenario_result["ai_message"]
        else:
            # Get the AI's reply - conversation_history inside conversation_engine
            # is what preserves context across the voice<->text switch.
            ai_response = self.conversation_engine.generate_response(user_text, context_type)

        turn = {
            "mode": InputMode.VOICE.value,
            "user_content": user_text,
            "ai_response": ai_response,
            "audio_duration_sec": audio_duration_sec,
            "pronunciation_score": pronunciation_score,
            "timestamp": datetime.now().isoformat(),
        }
        self.turns.append(turn)
        self.current_mode = InputMode.VOICE
        return turn

    # ------------------------------------------------------------------
    # US-37: Sending a TEXT turn (with E-01 network-drop handling)
    # ------------------------------------------------------------------
    def send_text_turn(
        self,
        text: str,
        context_type: str = "general",
        network_online: bool = True,
    ) -> Dict:
        """Process one text turn. Caches text locally if offline (E-01)."""
        if self.text_input_locked:
            return {"status": "blocked", "reason": "Text input is locked (mic active)."}

        # E-01: network dropped mid-send -> cache locally, don't lose the message
        if not network_online:
            self.cached_text = text
            self.connection_status = "waiting"
            return {
                "status": "cached",
                "banner": "Waiting for connection...",
                "cached_text": self.cached_text,
            }

        # Flush any cached text first (from a previous drop), then send
        final_text = self.cached_text or text
        self.cached_text = None
        self.connection_status = "online"

        # US-50: route to University Admission scenario if active
        if context_type == "university_admission" and self.university_session is not None:
            scenario_result = self.university_session.submit_answer(final_text)
            ai_response = scenario_result["ai_message"]
        else:
            ai_response = self.conversation_engine.generate_response(final_text, context_type)

        turn = {
            "mode": InputMode.TEXT.value,
            "user_content": final_text,
            "ai_response": ai_response,
            "audio_duration_sec": 0.0,
            "pronunciation_score": None,
            "timestamp": datetime.now().isoformat(),
        }
        self.turns.append(turn)
        self.current_mode = InputMode.TEXT
        return {"status": "sent", "turn": turn}

    def retry_connection(self, context_type: str = "general") -> Dict:
        """Call this once the connection is back, to flush cached text (E-01)."""
        if not self.cached_text:
            return {"status": "nothing_to_send"}
        return self.send_text_turn(self.cached_text, context_type, network_online=True)

    # ------------------------------------------------------------------
    # US-38: Play the AI's text reply out loud
    # ------------------------------------------------------------------
    def play_ai_response(self, text: str, output_path: str = "output/ai_reply.wav") -> Dict:
        """
        Synthesize the AI's reply as speech (the "speaker" button in US-38).
        Falls back to a clear error message if TTS is unavailable, instead
        of crashing the session.
        """
        try:
            tts = self._get_tts()
            tts.synthesize_to_file(text, output_path)
            return {"status": "playing", "audio_file": output_path}
        except Exception as e:
            logger.error(f"TTS playback failed: {e}")
            return {
                "status": "failed",
                "reason": "Could not generate audio for this reply. Please check your device volume/TTS service.",
            }

    # ------------------------------------------------------------------
    # Final hybrid scorecard (Acceptance Criteria for US-37)
    # ------------------------------------------------------------------
    def get_scorecard(self) -> Dict:
        voice_turns = [t for t in self.turns if t["mode"] == InputMode.VOICE.value]
        text_turns = [t for t in self.turns if t["mode"] == InputMode.TEXT.value]

        scored = [t for t in voice_turns if t["pronunciation_score"] is not None]
        pronunciation_avg = (
            round(sum(t["pronunciation_score"] for t in scored) / len(scored), 1)
            if scored
            else None
        )

        return {
            "total_turns": len(self.turns),
            "voice_turns": len(voice_turns),
            "text_turns": len(text_turns),
            "pronunciation_score": pronunciation_avg,
            "hybrid_session": bool(voice_turns) and bool(text_turns),
        }