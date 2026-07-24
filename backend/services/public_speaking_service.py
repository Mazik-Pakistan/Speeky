"""
Public Speaking Coach Service — PSC-US-01, PSC-US-03, PSC-US-04, PSC-US-05, PSC-US-06, PSC-US-07, PSC-US-11, PSC-US-12, PSC-US-14

Audio/text-based public speaking analysis. Ignores video-specific requirements (eye contact, physical presence).
Focuses on:
- Speech structure analysis (business pitch, classroom, TED-style)
- Speaking pace analytics (WPM calculation)
- Voice clarity and projection analysis
- Filler word tracking and visualization
- Tone variation and energy assessment
- Audience Q&A simulation
- Motivational speech evaluation
- Casual event speech feedback
"""

import base64
import binascii
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import Depends
from lib import llm_client, prompts, prosody_engine, recording_engine, session_scorer
from lib.audio_io import AudioDecodeError
from lib.prisma_client import db
from lib.session_scorer import AudioFeatures, ScoredSession
from lib.speech_config import load_speech_config
from middlewares.auth_middleware import require_auth
from schemas.public_speaking_schemas import (
    PublicSpeakingScorecard,
    PublicSpeakingSession,
    StartPublicSpeakingSchema,
    PublicSpeakingTurnSchema,
    QAResponseSchema,
)

logger = logging.getLogger(__name__)

# Speech type configurations
SPEECH_TYPES = {
    "business_pitch": {
        "label": "Business Pitch",
        "structure_elements": ["hook", "problem", "solution", "ask"],
        "ideal_wpm_range": (130, 160),
        "prioritize_structure": True,
        "prioritize_persuasiveness": True,
    },
    "casual_event": {
        "label": "Casual Event Speech (Wedding/Toast)",
        "structure_elements": ["opening", "story", "emotional_peak", "closing"],
        "ideal_wpm_range": (120, 150),
        "disable_corporate_tone": True,
        "prioritize_warmth": True,
    },
    "motivational": {
        "label": "Motivational Speech",
        "structure_elements": ["hook", "struggle", "triumph", "call_to_action"],
        "ideal_wpm_range": (130, 160),
        "prioritize_energy": True,
        "prioritize_tone_variation": True,
    },
    "classroom": {
        "label": "Classroom Presentation",
        "structure_elements": ["introduction", "body", "conclusion"],
        "ideal_wpm_range": (130, 150),
        "check_transitions": True,
        "track_filler_words": True,
    },
    "ted_talk": {
        "label": "TED-Style Talk",
        "structure_elements": ["hook", "story", "core_idea", "conclusion"],
        "ideal_wpm_range": (130, 150),
        "prioritize_storytelling": True,
        "prioritize_engagement": True,
    },
}

# Filler word patterns
FILLER_PATTERNS = [
    r"\bum\b", r"\bah\b", r"\buh\b", r"\blike\b", r"\byou know\b", 
    r"\bso\b", r"\bactually\b", r"\bbasically\b", r"\bkind of\b", r"\bsort of\b"
]

# Speaking pace thresholds
IDEAL_WPM_MIN = 130
IDEAL_WPM_MAX = 160
RUSHED_WPM_THRESHOLD = 170
SLOW_WPM_THRESHOLD = 110

# Audio quality thresholds
MIC_QUIET_DB = -45.0
CLIPPING_DB = -3.0


async def start_session(
    user_id: str,
    request: StartPublicSpeakingSchema,
) -> Dict:
    """Start a new public speaking session"""
    session_id = str(uuid.uuid4())
    
    speech_config = SPEECH_TYPES.get(request.speech_type, SPEECH_TYPES["business_pitch"])
    
    # Create session record
    session = await db.publicspeakingsession.create(
        data={
            "id": session_id,
            "userId": user_id,
            "speechType": request.speech_type,
            "inputMode": request.input_mode,
            "status": "in_progress",
            "createdAt": datetime.now(timezone.utc),
            "topic": request.topic,
        }
    )
    
    return {
        "session_id": session_id,
        "speech_type": request.speech_type,
        "label": speech_config["label"],
        "input_mode": request.input_mode,
        "structure_elements": speech_config["structure_elements"],
        "ideal_wpm_range": speech_config["ideal_wpm_range"],
        "topic": request.topic,
        "status": "in_progress",
    }


async def submit_turn(
    session_id: str,
    user_id: str,
    turn: PublicSpeakingTurnSchema,
) -> Dict:
    """Process a speech turn (audio or text) and return analysis"""
    session = await db.publicspeakingsession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        raise ValueError("Session not found")
    
    speech_config = SPEECH_TYPES.get(session.speechType, SPEECH_TYPES[PublicSpeakingType.BUSINESS_PITCH])
    
    # Process audio or text input
    if turn.audio_data:
        # Audio processing pipeline
        transcript, audio_features = await _process_audio(turn.audio_data)
        text_content = transcript
    else:
        # Text processing
        text_content = turn.text_content or ""
        audio_features = None
    
    # Generate comprehensive scorecard
    scorecard = await _generate_scorecard(
        speech_type=str(session.speechType),
        text_content=text_content,
        audio_features=audio_features,
        speech_config=speech_config,
    )
    
    # Update session
    await db.publicspeakingsession.update(
        where={"id": session_id},
        data={
            "transcript": text_content,
            "status": "completed" if turn.is_final else "in_progress",
            "completedAt": datetime.now(timezone.utc) if turn.is_final else None,
            "scorecard": scorecard,
        }
    )
    
    # Check if Q&A should be triggered (PSC-US-12)
    should_trigger_qa = (
        turn.is_final and 
        len(text_content) > 100 and  # Minimum content for meaningful Q&A
        not _is_nonsense_content(text_content)
    )
    
    if should_trigger_qa:
        # Generate AI question based on speech content
        ai_question = await _generate_qa_question(session.speechType, text_content)
        await db.publicspeakingsession.update(
            where={"id": session_id},
            data={
                "status": "qa_phase",
                "aiQuestion": ai_question,
            }
        )
        return {
            "scorecard": scorecard,
            "qa_triggered": True,
            "ai_question": ai_question,
            "session_id": session_id,
        }
    
    return {
        "scorecard": scorecard,
        "qa_triggered": False,
        "session_id": session_id,
    }


async def submit_qa_response(
    session_id: str,
    user_id: str,
    response: QAResponseSchema,
) -> Dict:
    """Process Q&A response and evaluate performance"""
    session = await db.publicspeakingsession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        raise ValueError("Session not found")
    
    if session.status != "qa_phase":
        raise ValueError("Session not in Q&A phase")
    
    # Process response
    if response.audio_data:
        transcript, audio_features = await _process_audio(response.audio_data)
        text_content = transcript
    else:
        text_content = response.text_content or ""
        audio_features = None
    
    # Evaluate Q&A performance
    qa_score = await _evaluate_qa_response(
        original_speech=session.transcript or "",
        ai_question=session.aiQuestion or "",
        user_response=text_content,
        audio_features=audio_features,
    )
    
    # Update session with Q&A results
    await db.publicspeakingsession.update(
        where={"id": session_id},
        data={
            "userQaResponse": text_content,
            "status": "completed",
            "completedAt": datetime.now(timezone.utc),
            "qaScore": qa_score,
        }
    )
    
    # Merge Q&A score into existing scorecard
    updated_scorecard = session.scorecard or {}
    updated_scorecard["qa_handling"] = qa_score
    
    return {
        "qa_score": qa_score,
        "updated_scorecard": updated_scorecard,
        "session_id": session_id,
    }


async def get_session(session_id: str, user_id: str) -> Dict:
    """Get session details"""
    session = await db.publicspeakingsession.find_unique(where={"id": session_id})
    if not session or session.userId != user_id:
        raise ValueError("Session not found")
    
    return {
        "session_id": session.id,
        "speech_type": session.speechType,
        "input_mode": session.inputMode,
        "status": session.status,
        "created_at": session.createdAt.isoformat(),
        "completed_at": session.completedAt.isoformat() if session.completedAt else None,
        "topic": session.topic,
        "transcript": session.transcript,
        "scorecard": session.scorecard,
        "ai_question": session.aiQuestion,
        "user_qa_response": session.userQaResponse,
        "qa_score": session.qaScore,
    }


async def _process_audio(audio_data: str) -> Tuple[str, Optional[AudioFeatures]]:
    """Process audio input: decode base64, then run it through the same shared
    decode+VAD+STT+prosody pipeline Pronunciation Coach / Accent Assessment use
    (lib/recording_engine.py) instead of duplicating that logic here."""
    try:
        # Frontend sends either a raw base64 string or a data: URI — strip the prefix if present.
        raw = audio_data.split(",", 1)[1] if audio_data.startswith("data:") else audio_data
        audio_bytes = base64.b64decode(raw)
        config = load_speech_config()
        analysis = recording_engine.analyze_recording(audio_bytes, config)
        audio_features = AudioFeatures(
            transcript=analysis.transcript,
            duration_seconds=analysis.duration_seconds,
            avg_db=analysis.avg_dbfs,
        )
        return analysis.transcript, audio_features
    except (AudioDecodeError, binascii.Error) as e:
        logger.error(f"Audio processing failed: {e}")
        return "", None


async def _generate_scorecard(
    speech_type: str,
    text_content: str,
    audio_features: Optional[AudioFeatures],
    speech_config: Dict,
) -> Dict:
    """Generate comprehensive scorecard based on speech analysis"""
    
    # Calculate speaking pace (PSC-US-11)
    wpm_metrics = _calculate_wpm(text_content, audio_features)
    
    # Analyze filler words (PSC-US-08)
    filler_analysis = _analyze_filler_words(text_content)
    
    # Assess tone variation and energy (PSC-US-05, PSC-US-07)
    tone_analysis = _analyze_tone_variation(text_content, audio_features)
    
    # Evaluate structure based on speech type
    structure_analysis = _evaluate_structure(speech_type, text_content, speech_config)
    
    # Voice clarity analysis (PSC-US-14)
    clarity_analysis = _analyze_voice_clarity(audio_features)
    
    # Calculate overall scores
    scores = _calculate_overall_scores(
        speech_type=speech_type,
        wpm_metrics=wpm_metrics,
        filler_analysis=filler_analysis,
        tone_analysis=tone_analysis,
        structure_analysis=structure_analysis,
        clarity_analysis=clarity_analysis,
        speech_config=speech_config,
    )
    
    # Generate feedback and flags
    flags = _generate_flags(
        speech_type=speech_type,
        wpm_metrics=wpm_metrics,
        filler_analysis=filler_analysis,
        tone_analysis=tone_analysis,
        structure_analysis=structure_analysis,
        clarity_analysis=clarity_analysis,
    )
    
    highlights = _generate_highlights(
        speech_type=speech_type,
        structure_analysis=structure_analysis,
        tone_analysis=tone_analysis,
    )
    
    # Generate summary and actionable tips
    summary, actionable_tips = _generate_feedback_summary(
        speech_type=speech_type,
        scores=scores,
        flags=flags,
        speech_config=speech_config,
    )
    
    return {
        "speech_type": str(speech_type),
        "input_mode": "audio" if audio_features else "text",
        "overall_score": scores["overall"],
        "confidence": scores["confidence"],
        "pacing": scores["pacing"],
        "tone_variation": scores["tone_variation"],
        "voice_clarity": scores["voice_clarity"],
        "structure": scores["structure"],
        "audience_engagement": scores["audience_engagement"],
        "words_per_minute": wpm_metrics["wpm"],
        "filler_word_count": filler_analysis["count"],
        "filler_words": filler_analysis["words"],
        "flags": flags,
        "highlights": highlights,
        "summary": summary,
        "actionable_tips": actionable_tips,
        "delivery": {
            "duration_seconds": audio_features.duration_seconds if audio_features else 0,
            "avg_db": audio_features.avg_db if audio_features else None,
        } if audio_features else None,
    }


def _calculate_wpm(text: str, audio_features: Optional[AudioFeatures]) -> Dict:
    """Calculate words per minute and pacing metrics"""
    words = text.split()
    word_count = len(words)
    
    if audio_features and audio_features.duration_seconds > 0:
        wpm = (word_count / audio_features.duration_seconds) * 60
    else:
        # Estimate based on average reading speed for text-only
        wpm = 150  # Default assumption
    
    # Determine pacing quality
    if IDEAL_WPM_MIN <= wpm <= IDEAL_WPM_MAX:
        pacing_quality = "optimal"
    elif wpm > RUSHED_WPM_THRESHOLD:
        pacing_quality = "rushed"
    elif wpm < SLOW_WPM_THRESHOLD:
        pacing_quality = "slow"
    else:
        pacing_quality = "acceptable"
    
    return {
        "wpm": round(wpm, 1),
        "word_count": word_count,
        "pacing_quality": pacing_quality,
    }


def _analyze_filler_words(text: str) -> Dict:
    """Analyze filler word usage"""
    filler_words = []
    text_lower = text.lower()
    
    for pattern in FILLER_PATTERNS:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            filler_words.append({
                "word": match.group(),
                "position": match.start(),
            })
    
    # Distinguish "like" as filler vs. valid usage (PSC-US-08 E-01)
    valid_like_contexts = ["i like", "would like", "you like", "they like"]
    filler_words = [
        fw for fw in filler_words 
        if not (fw["word"] == "like" and 
                any(ctx in text_lower[max(0, fw["position"]-10):fw["position"]+10] 
                    for ctx in valid_like_contexts))
    ]
    
    return {
        "count": len(filler_words),
        "words": filler_words,
    }


def _analyze_tone_variation(text: str, audio_features: Optional[AudioFeatures]) -> Dict:
    """Analyze tone variation and vocal energy"""
    # Text-based analysis
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    sentence_lengths = [len(s.split()) for s in sentences]
    
    # Check for monotone indication (similar sentence lengths)
    if len(sentence_lengths) > 1:
        length_variance = max(sentence_lengths) - min(sentence_lengths)
        monotone_risk = length_variance < 5  # Low variance suggests monotone
    else:
        monotone_risk = False
    
    # Audio-based analysis if available
    energy_score = 75.0  # Default
    if audio_features:
        # Use prosody engine for detailed analysis
        try:
            prosody_result = prosody_engine.analyze(audio_features)
            energy_score = prosody_result.get("energy", 75.0)
        except Exception:
            energy_score = 75.0
    
    return {
        "energy_score": energy_score,
        "monotone_risk": monotone_risk,
        "sentence_count": len(sentences),
    }


def _evaluate_structure(speech_type: str, text: str, speech_config: Dict) -> Dict:
    """Evaluate speech structure based on type"""
    structure_elements = speech_config["structure_elements"]
    found_elements = []
    
    text_lower = text.lower()
    
    # Define keyword patterns for each structure element
    element_patterns = {
        "hook": [r"imagine", r"picture this", r"let me tell you", r"have you ever"],
        "problem": [r"problem", r"challenge", r"issue", r"struggle", r"pain point"],
        "solution": [r"solution", r"answer", r"approach", r"we propose", r"our product"],
        "ask": [r"ask", r"investment", r"funding", r"partnership", r"next steps", r"call to action"],
        "introduction": [r"introduction", r"today i", r"i will", r"let's start", r"agenda"],
        "body": [r"first", r"second", r"third", r"next", r"moving on", r"furthermore"],
        "conclusion": [r"in conclusion", r"to summarize", r"finally", r"wrap up", r"in summary"],
        "story": [r"story", r"experience", r"remember when", r"back when", r"personal"],
        "emotional_peak": [r"inspire", r"believe", r"passion", r"love", r"dream"],
        "closing": [r"thank you", r"appreciate", r"grateful", r"conclude"],
        "struggle": [r"struggle", r"difficult", r"hard", r"challenge", r"overcome"],
        "triumph": [r"success", r"achieve", r"accomplish", r"breakthrough", r"victory"],
        "call_to_action": [r"act now", r"join me", r"let's", r"together", r"start"],
        "opening": [r"hello", r"welcome", r"good morning", r"good afternoon", r"thank you for being here"],
    }
    
    for element in structure_elements:
        patterns = element_patterns.get(element, [])
        if any(re.search(pattern, text_lower) for pattern in patterns):
            found_elements.append(element)
    
    structure_score = (len(found_elements) / len(structure_elements)) * 100 if structure_elements else 75.0
    
    return {
        "found_elements": found_elements,
        "missing_elements": [e for e in structure_elements if e not in found_elements],
        "structure_score": round(structure_score, 1),
    }


def _analyze_voice_clarity(audio_features: Optional[AudioFeatures]) -> Dict:
    """Analyze voice clarity and projection (PSC-US-14)"""
    if not audio_features:
        return {
            "clarity_score": 75.0,
            "projection_score": 75.0,
            "issues": [],
        }
    
    issues = []
    clarity_score = 75.0
    projection_score = 75.0
    
    # Check for quiet microphone (hardware issue)
    if audio_features.avg_db and audio_features.avg_db <= MIC_QUIET_DB:
        issues.append({
            "type": "microphone_quiet",
            "message": "Microphone volume is very low. Please check device settings.",
        })
        projection_score = 50.0  # Don't penalize user for hardware
    
    # Check for clipping
    if audio_features.avg_db and audio_features.avg_db >= CLIPPING_DB:
        issues.append({
            "type": "audio_clipping",
            "message": "Audio distortion detected. Please move farther from microphone.",
        })
        clarity_score = 50.0
    
    # Check for volume consistency (not currently produced by the recording pipeline —
    # guarded rather than assumed present since AudioFeatures doesn't declare this field).
    db_variance = getattr(audio_features, "db_variance", None)
    if db_variance and db_variance > 15:
        issues.append({
            "type": "volume_inconsistent",
            "message": "Voice volume varies significantly. Try to maintain consistent projection.",
        })
        clarity_score -= 10
    
    return {
        "clarity_score": max(0.0, min(100.0, clarity_score)),
        "projection_score": max(0.0, min(100.0, projection_score)),
        "issues": issues,
    }


def _calculate_overall_scores(
    speech_type: str,
    wpm_metrics: Dict,
    filler_analysis: Dict,
    tone_analysis: Dict,
    structure_analysis: Dict,
    clarity_analysis: Dict,
    speech_config: Dict,
) -> Dict:
    """Calculate overall scores based on all analyses"""
    
    # Base scores
    pacing_score = 100.0
    if wpm_metrics["pacing_quality"] == "rushed":
        pacing_score = 60.0
    elif wpm_metrics["pacing_quality"] == "slow":
        pacing_score = 70.0
    
    # Penalize excessive filler words
    filler_penalty = min(filler_analysis["count"] * 2, 30)  # Max 30 point penalty
    
    # Tone variation score
    tone_score = tone_analysis["energy_score"]
    if tone_analysis["monotone_risk"]:
        tone_score -= 20
    
    # Structure score
    structure_score = structure_analysis["structure_score"]
    
    # Clarity score
    clarity_score = clarity_analysis["clarity_score"]
    
    # Calculate overall based on speech type priorities
    if speech_config.get("prioritize_energy"):
        # Motivational: prioritize tone and energy
        overall = (0.35 * tone_score + 0.25 * structure_score + 
                   0.2 * pacing_score + 0.1 * clarity_score + 
                   0.1 * (100 - filler_penalty))
    elif speech_config.get("prioritize_storytelling"):
        # TED-style: prioritize structure and engagement
        overall = (0.3 * structure_score + 0.25 * tone_score + 
                   0.2 * pacing_score + 0.15 * clarity_score + 
                   0.1 * (100 - filler_penalty))
    elif speech_config.get("prioritize_structure"):
        # Business pitch: prioritize structure and persuasiveness
        overall = (0.35 * structure_score + 0.2 * pacing_score + 
                   0.2 * tone_score + 0.15 * clarity_score + 
                   0.1 * (100 - filler_penalty))
    elif speech_config.get("disable_corporate_tone"):
        # Casual event: prioritize warmth, lower structure weight
        overall = (0.3 * tone_score + 0.2 * structure_score + 
                   0.2 * pacing_score + 0.2 * clarity_score + 
                   0.1 * (100 - filler_penalty))
    else:
        # Default balanced scoring
        overall = (0.25 * structure_score + 0.25 * pacing_score + 
                   0.2 * tone_score + 0.15 * clarity_score + 
                   0.15 * (100 - filler_penalty))
    
    # Audience engagement derived from tone and structure
    audience_engagement = (tone_score + structure_score) / 2
    
    # Confidence score (overall adjusted for major issues)
    confidence = overall
    if clarity_analysis["issues"]:
        confidence -= 10
    
    return {
        "overall": round(max(0.0, min(100.0, overall)), 1),
        "confidence": round(max(0.0, min(100.0, confidence)), 1),
        "pacing": round(pacing_score, 1),
        "tone_variation": round(max(0.0, min(100.0, tone_score)), 1),
        "voice_clarity": round(clarity_score, 1),
        "structure": round(structure_score, 1),
        "audience_engagement": round(audience_engagement, 1),
    }


def _generate_flags(
    speech_type: str,
    wpm_metrics: Dict,
    filler_analysis: Dict,
    tone_analysis: Dict,
    structure_analysis: Dict,
    clarity_analysis: Dict,
) -> List[Dict]:
    """Generate flags for issues and suggestions"""
    flags = []
    
    # Pacing flags
    if wpm_metrics["pacing_quality"] == "rushed":
        flags.append({
            "type": "rushed_pacing",
            "message": f"Speaking at {wpm_metrics['wpm']} WPM - too fast for audience comprehension.",
            "suggestion": "Slow down and add strategic pauses after key points.",
        })
    elif wpm_metrics["pacing_quality"] == "slow":
        flags.append({
            "type": "slow_pacing",
            "message": f"Speaking at {wpm_metrics['wpm']} WPM - may lose audience engagement.",
            "suggestion": "Increase energy and pace slightly to maintain attention.",
        })
    
    # Filler word flags
    if filler_analysis["count"] > 10:
        flags.append({
            "type": "excessive_filler_words",
            "message": f"Used {filler_analysis['count']} filler words - breaks fluency.",
            "suggestion": "Practice pausing silently instead of using 'um' or 'ah'.",
        })
    
    # Tone flags
    if tone_analysis["monotone_risk"]:
        flags.append({
            "type": "monotone_delivery",
            "message": "Speech lacks vocal variety - may sound flat to audience.",
            "suggestion": "Vary your pitch and volume, especially on emotional words.",
        })
    
    # Structure flags
    for missing in structure_analysis["missing_elements"]:
        flags.append({
            "type": "missing_structure_element",
            "message": f"Speech missing key element: {missing}",
            "suggestion": f"Add a clear {missing} section to improve structure.",
        })
    
    # Clarity flags
    for issue in clarity_analysis["issues"]:
        flags.append(issue)
    
    return flags


def _generate_highlights(
    speech_type: str,
    structure_analysis: Dict,
    tone_analysis: Dict,
) -> List[Dict]:
    """Generate positive highlights"""
    highlights = []
    
    for element in structure_analysis["found_elements"]:
        highlights.append({
            "kind": "structure",
            "phrase": f"Strong {element} section",
        })
    
    if not tone_analysis["monotone_risk"]:
        highlights.append({
            "kind": "tone",
            "phrase": "Good vocal variety and energy",
        })
    
    return highlights


def _generate_feedback_summary(
    speech_type: str,
    scores: Dict,
    flags: List[Dict],
    speech_config: Dict,
) -> Tuple[str, List[str]]:
    """Generate overall summary and actionable tips"""
    
    # Generate summary based on overall score
    overall = scores["overall"]
    if overall >= 85:
        summary = "Excellent delivery! Your speech demonstrates strong structure and engaging delivery."
    elif overall >= 70:
        summary = "Good speech with room for improvement. Focus on the flagged areas to elevate your delivery."
    elif overall >= 50:
        summary = "Your speech shows potential. Work on structure and pacing to strengthen audience engagement."
    else:
        summary = "This speech needs significant revision. Focus on fundamentals: clear structure, appropriate pacing, and vocal variety."
    
    # Generate actionable tips from flags
    tips = []
    for flag in flags:
        if flag.get("suggestion"):
            tips.append(flag["suggestion"])
    
    # Add speech-type specific tips
    if speech_config.get("prioritize_energy"):
        tips.append("For motivational speeches: practice varying your volume and pause for dramatic effect.")
    elif speech_config.get("prioritize_storytelling"):
        tips.append("For TED-style talks: start with a personal story to hook your audience.")
    elif speech_config.get("disable_corporate_tone"):
        tips.append("For casual events: prioritize warmth and authenticity over formal structure.")
    
    return summary, tips[:5]  # Limit to top 5 tips


def _is_nonsense_content(text: str) -> bool:
    """Check if content is too minimal/nonsense for Q&A (PSC-US-12 E-01)"""
    words = text.split()
    if len(words) < 20:
        return True
    
    # Check for repetitive patterns
    unique_words = set(words.lower())
    if len(unique_words) < 5:
        return True
    
    return False


async def _generate_qa_question(speech_type: str, transcript: str) -> str:
    """Generate relevant Q&A question based on speech content (PSC-US-12)"""
    if not llm_client.is_configured():
        # Fallback questions
        fallback_questions = {
            "BUSINESS_PITCH": "What makes your solution unique compared to competitors?",
            "CLASSROOM": "Can you elaborate on your main supporting argument?",
            "MOTIVATIONAL": "How did you overcome the biggest challenge you mentioned?",
            "TED_TALK": "What's the one thing you hope the audience remembers?",
            "CASUAL_EVENT": "What inspired you to share this particular story?",
        }
        return fallback_questions.get(speech_type.upper(), "Can you tell us more about your main point?")
    
    prompt = f"""Based on this {str(speech_type)} transcript, generate one relevant follow-up question an audience member might ask:

Transcript: {transcript}

Generate a specific, thoughtful question related to the content. Return only the question, no explanation."""
    
    try:
        response = await llm_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100,
        )
        return response.strip()
    except Exception as e:
        logger.error(f"Q&A question generation failed: {e}")
        return "Can you elaborate on your main point?"


async def _evaluate_qa_response(
    original_speech: str,
    ai_question: str,
    user_response: str,
    audio_features: Optional[AudioFeatures],
) -> Dict:
    """Evaluate Q&A response performance (PSC-US-12)"""
    
    # Check for silence/freezing (PSC-US-12 E-02)
    if len(user_response.strip()) < 10:
        return {
            "composure": 30.0,
            "relevance": 20.0,
            "feedback": "You froze when asked the question. Practice buying time with phrases like 'That's a great question, let me think about that...'",
        }
    
    # Check for aggressive/defensive tone (PSC-US-12 E-03)
    aggressive_indicators = ["wrong", "stupid", "ridiculous", "don't agree", "incorrect"]
    if any(indicator in user_response.lower() for indicator in aggressive_indicators):
        return {
            "composure": 40.0,
            "relevance": 60.0,
            "feedback": "Your response sounded defensive. Accept audience questions gracefully, even if you disagree.",
        }
    
    # Use LLM for detailed evaluation if available
    if llm_client.is_configured():
        prompt = f"""Evaluate this Q&A response:

Original Speech Context: {original_speech[:500]}
Question: {ai_question}
Response: {user_response}

Rate the response on:
1. Composure (0-100): Did the speaker remain calm and professional?
2. Relevance (0-100): Did the response directly address the question?

Provide a brief, constructive feedback tip.

Return JSON with keys: composure, relevance, feedback"""
        
        try:
            result = await llm_client.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            return {
                "composure": result.get("composure", 70.0),
                "relevance": result.get("relevance", 70.0),
                "feedback": result.get("feedback", "Good response."),
            }
        except Exception as e:
            logger.error(f"Q&A evaluation failed: {e}")
    
    # Fallback heuristic evaluation
    words = user_response.split()
    composure = min(100.0, 50.0 + len(words) * 2)  # Longer responses suggest more composure
    relevance = 75.0  # Default assumption
    
    return {
        "composure": round(composure, 1),
        "relevance": round(relevance, 1),
        "feedback": "Good effort. Continue practicing impromptu responses to build confidence.",
    }
