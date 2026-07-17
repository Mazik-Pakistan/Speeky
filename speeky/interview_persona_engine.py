import logging
import time
import os
from speeky.tts import TextToSpeech

logger = logging.getLogger(__name__)

# US-46: 3 fixed personas — har ek ki apni awaaz (voice) aur apna tone
PERSONAS = {
    "strict_corporate_hr": {
        "name": "Strict Corporate HR",
        "voice": "en_GB-alan-medium",
        "tone_label": "Strict",
        "tone_prompt": "You are a strict, formal corporate HR interviewer. Ask rigorous follow-up questions and maintain a serious tone.",
        "strictness": "high",
        "active": True,
    },
    "friendly_startup_founder": {
        "name": "Friendly Startup Founder",
        "voice": "en_US-amy-medium",
        "tone_label": "Conversational",
        "tone_prompt": "You are a friendly, casual startup founder. Be warm, encouraging, and conversational.",
        "strictness": "low",
        "active": True,
    },
    "formal_panel": {
        "name": "Formal Panel",
        "voice": "en_US-lessac-medium",
        "tone_label": "Formal",
        "tone_prompt": "You are a formal interview panel representative. Maintain a neutral, structured tone.",
        "strictness": "medium",
        "active": True,
    },
}

DEFAULT_PERSONA_ID = "formal_panel"
PREVIEW_SAMPLE_TEXT = "Welcome to the interview. Let's begin."

CRISIS_KEYWORDS = ["i can't do this", "i'm too stressed", "i want to give up", "i'm panicking"]


class PersonaEngine:
    def __init__(self):
        self.active_persona_id = None
        self.favorite_persona_id = None
        self._last_preview_time = 0
        self._current_preview_file = None
        self.session_started = False  # TC-004: interview shuru hone ke baad persona lock karne ke liye

    def select_persona(self, persona_id, voice_pack_download_success=True):
        # TC-004 (US-46): Interview shuru hone ke baad persona change nahi honi chahiye
        if self.session_started:
            return {
                "status": "blocked",
                "message": "Cannot change persona after the interview has started.",
                "persona": self.get_active_persona()["name"],
            }

        if not voice_pack_download_success:
            logger.warning(f"Voice pack failed for {persona_id}, using default.")
            self.active_persona_id = DEFAULT_PERSONA_ID
            return {
                "status": "fallback",
                "persona": PERSONAS[DEFAULT_PERSONA_ID]["name"],
                "message": "Selected voice pack unavailable. Using standard interviewer voice.",
            }

        if persona_id not in PERSONAS or not PERSONAS[persona_id]["active"]:
            persona_id = DEFAULT_PERSONA_ID

        self.active_persona_id = persona_id
        return {
            "status": "ok",
            "persona": PERSONAS[persona_id]["name"],
            "voice": PERSONAS[persona_id]["voice"],
            "tone_label": PERSONAS[persona_id]["tone_label"],
        }

    def start_session(self):
        """Interview session ko 'locked' state mein daal do - ab persona change nahi hogi"""
        self.session_started = True

    def end_session(self):
        """Session khatam - ab persona dobara select ho sakti hai"""
        self.session_started = False

    def get_active_persona(self):
        pid = self.active_persona_id or DEFAULT_PERSONA_ID
        return PERSONAS[pid]

    def check_crisis_override(self, user_text):
        text_lower = user_text.lower()
        return any(kw in text_lower for kw in CRISIS_KEYWORDS)

    def get_effective_prompt(self, user_text):
        if self.check_crisis_override(user_text):
            return "You are a supportive, calm assistant. The user seems distressed; respond gently, dropping any strict persona."
        return self.get_active_persona()["tone_prompt"]

    def simulate_tts_latency_fallback(self, tts_service_responded_in_time=True):
        if not tts_service_responded_in_time:
            return {
                "status": "fallback",
                "voice": "en_GB-alan-medium",
                "message": "Using standard voice due to slow connection.",
            }
        return {"status": "ok", "voice": self.get_active_persona()["voice"]}

    def preview_persona_voice(self, persona_id, current_time=None):
        """US-47: 5-second sample sunwao persona select karne se pehle"""
        if current_time is None:
            current_time = time.time()

        time_since_last = current_time - self._last_preview_time
        halted_previous = time_since_last < 2.0
        self._last_preview_time = current_time

        if persona_id not in PERSONAS or not PERSONAS[persona_id]["active"]:
            if self.favorite_persona_id == persona_id:
                self.favorite_persona_id = None
            persona_id = DEFAULT_PERSONA_ID
            fallback_note = "Your saved persona is no longer available. Please select a new one."
        else:
            fallback_note = None

        persona = PERSONAS[persona_id]

        try:
            output_file = f"output/preview_{persona_id}.wav"
            if not os.path.exists(output_file):
                tts = TextToSpeech()
                tts.synthesize_to_file(PREVIEW_SAMPLE_TEXT, output_file, voice=persona["voice"])

            self._current_preview_file = output_file
            result = {
                "status": "ok",
                "persona": persona["name"],
                "tone_label": persona["tone_label"],
                "preview_file": output_file,
                "halted_previous_audio": halted_previous,
            }
            if fallback_note:
                result["message"] = fallback_note
            return result
        except Exception as e:
            logger.error(f"Preview generation failed for {persona_id}: {e}")
            return {
                "status": "failed",
                "message": "Could not generate voice preview. Please try again.",
            }

    def deprecate_persona(self, persona_id):
        if persona_id in PERSONAS:
            PERSONAS[persona_id]["active"] = False
            logger.info(f"Persona {persona_id} deprecated by admin.")

    def set_favorite(self, persona_id):
        self.favorite_persona_id = persona_id