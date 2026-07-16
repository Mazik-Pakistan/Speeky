"""
Initial Communication Assessment implementation.

This module implements the 5-minute AI-led baseline assessment (BAS-US-09)
to establish initial confidence and learning level for new users.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field
import random

try:
    from .pipeline import SpeekyPipeline
    from .storage import InMemoryStorage, LearningLevel, AssessmentStatus
    from .confidence import ConfidenceScoreEngine, SessionScore
except ImportError:
    from pipeline import SpeekyPipeline
    from storage import InMemoryStorage, LearningLevel, AssessmentStatus
    from confidence import ConfidenceScoreEngine, SessionScore

logger = logging.getLogger(__name__)


@dataclass
class AssessmentQuestion:
    """Single assessment question."""
    question_id: str
    text: str
    category: str  # introduction, fluency, vocabulary, pronunciation
    expected_response_length: str  # short, medium, long
    audio_prompt: Optional[str] = None  # TTS audio file if pre-generated


@dataclass
class AssessmentResponse:
    """User response to assessment question."""
    question_id: str
    response_type: str  # audio, text
    audio_data: Optional[np.ndarray] = None
    text_data: Optional[str] = None
    sample_rate: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    is_flagged: bool = False
    flag_reason: Optional[str] = None
    processing_result: Optional[Dict] = None


@dataclass
class AssessmentResult:
    """Complete assessment result."""
    user_id: str
    assessment_id: str
    responses: List[AssessmentResponse]
    fluency_score: float
    vocabulary_score: float
    pronunciation_score: Optional[float]
    confidence_score: float
    learning_level: LearningLevel
    completed_at: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    is_flagged: bool = False
    flag_reason: Optional[str] = None


class AssessmentQuestionBank:
    """Bank of assessment questions for baseline evaluation."""
    
    def __init__(self):
        """Initialize question bank with varied questions."""
        self.questions = {
            'introduction': [
                AssessmentQuestion(
                    question_id="intro_1",
                    text="Hello! Could you please introduce yourself and tell me what brings you here today?",
                    category="introduction",
                    expected_response_length="medium"
                ),
                AssessmentQuestion(
                    question_id="intro_2",
                    text="What are your main goals for improving your English communication skills?",
                    category="introduction",
                    expected_response_length="medium"
                ),
            ],
            'fluency': [
                AssessmentQuestion(
                    question_id="fluency_1",
                    text="Tell me about a typical day in your life, from morning to evening.",
                    category="fluency",
                    expected_response_length="long"
                ),
                AssessmentQuestion(
                    question_id="fluency_2",
                    text="Describe your favorite hobby or activity and why you enjoy it.",
                    category="fluency",
                    expected_response_length="long"
                ),
            ],
            'vocabulary': [
                AssessmentQuestion(
                    question_id="vocab_1",
                    text="What do you think are the most important qualities for success in your field?",
                    category="vocabulary",
                    expected_response_length="medium"
                ),
                AssessmentQuestion(
                    question_id="vocab_2",
                    text="Describe a challenging situation you faced and how you handled it.",
                    category="vocabulary",
                    expected_response_length="long"
                ),
            ],
            'pronunciation': [
                AssessmentQuestion(
                    question_id="pron_1",
                    text="Please read this sentence carefully: 'The quick brown fox jumps over the lazy dog.'",
                    category="pronunciation",
                    expected_response_length="short"
                ),
                AssessmentQuestion(
                    question_id="pron_2",
                    text="Say these words: 'beautiful', 'comfortable', 'extraordinary', 'unfortunately'.",
                    category="pronunciation",
                    expected_response_length="short"
                ),
            ]
        }
    
    def get_assessment_questions(self, count: int = 5) -> List[AssessmentQuestion]:
        """
        Get a random set of assessment questions.
        
        Args:
            count: Number of questions to return
            
        Returns:
            List of assessment questions
        """
        selected = []
        
        # Always include at least one from each category
        for category, questions in self.questions.items():
            selected.append(random.choice(questions))
        
        # Fill remaining slots with random questions
        all_questions = [q for cat_questions in self.questions.values() for q in cat_questions]
        remaining = [q for q in all_questions if q not in selected]
        
        while len(selected) < count and remaining:
            question = random.choice(remaining)
            selected.append(question)
            remaining.remove(question)
        
        random.shuffle(selected)
        return selected[:count]


class AssessmentIntegrityChecker:
    """
    Assessment integrity and anti-gaming safeguards (BAS-US-03).
    
    Detects attempts to artificially inflate scores through:
    - Pre-recorded audio
    - Text-to-speech playback
    - Copy-pasted text answers
    """
    
    def __init__(self):
        """Initialize integrity checker."""
        self.flagged_sessions = {}
    
    def check_audio_integrity(self, audio_data: np.ndarray, sample_rate: int) -> Tuple[bool, Optional[str]]:
        """
        Check audio for synthetic/TTS signatures.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate
            
        Returns:
            Tuple of (is_flagged, reason)
        """
        # Basic signal analysis
        if len(audio_data) == 0:
            return True, "Empty audio signal"
        
        # Check for flatlining (silence)
        amplitude = np.max(np.abs(audio_data))
        if amplitude < 0.01:
            return True, "Audio amplitude too low (silent)"
        
        # Check for clipping
        if amplitude > 0.99:
            return True, "Audio clipping detected (possible synthetic source)"
        
        # Check for repetitive patterns (possible loop)
        if len(audio_data) > sample_rate:  # At least 1 second
            # Simple repetition check
            chunk_size = sample_rate // 10  # 100ms chunks
            chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data)-chunk_size, chunk_size)]
            if len(chunks) > 10:
                # Check if many chunks are similar
                similarities = []
                for i in range(len(chunks)-1):
                    correlation = np.corrcoef(chunks[i], chunks[i+1])[0,1]
                    similarities.append(correlation)
                
                avg_similarity = np.mean(similarities)
                if avg_similarity > 0.95:
                    return True, "Highly repetitive audio pattern detected"
        
        return False, None
    
    def check_text_integrity(self, text: str, clipboard_detected: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Check text for paste or irregular input patterns.
        
        Args:
            text: Input text
            clipboard_detected: Whether clipboard paste was detected
            
        Returns:
            Tuple of (is_flagged, reason)
        """
        if not text or not text.strip():
            return True, "Empty text response"
        
        # Check for clipboard paste
        if clipboard_detected:
            return True, "Clipboard paste detected"
        
        # Check for gibberish
        words = text.split()
        if len(words) > 0:
            # Check average word length
            avg_length = sum(len(word) for word in words) / len(words)
            if avg_length < 2:
                return True, "Suspiciously short words (possible gibberish)"
        
        # Check for repetitive characters
        if any(char * 5 in text for char in text):
            return True, "Repetitive character pattern detected"
        
        return False, None
    
    def check_response_consistency(self, responses: List[AssessmentResponse]) -> Tuple[bool, Optional[str]]:
        """
        Check for consistency across multiple responses.
        
        Args:
            responses: List of assessment responses
            
        Returns:
            Tuple of (is_flagged, reason)
        """
        if len(responses) < 2:
            return False, None
        
        # Check if all responses are identical or very similar
        text_responses = [r.text_data for r in responses if r.text_data]
        
        if len(text_responses) > 1:
            # Check for identical responses
            if len(set(text_responses)) == 1:
                return True, "Identical responses across multiple questions"
        
        return False, None


class InitialCommunicationAssessment:
    """
    Initial Communication Assessment implementation (BAS-US-09).
    
    5-minute AI-led evaluation to establish baseline confidence and learning level.
    """
    
    def __init__(self, pipeline: SpeekyPipeline, storage: InMemoryStorage, 
                 confidence_engine: ConfidenceScoreEngine):
        """
        Initialize the assessment system.
        
        Args:
            pipeline: Speeky pipeline for audio processing
            storage: In-memory storage for results
            confidence_engine: Confidence score calculation engine
        """
        self.pipeline = pipeline
        self.storage = storage
        self.confidence_engine = confidence_engine
        self.question_bank = AssessmentQuestionBank()
        self.integrity_checker = AssessmentIntegrityChecker()
        
        # Current assessment state (stored in storage for persistence)
        self.current_assessment = None
        self.storage = storage  # Reference to storage for persistence
        
        logger.info("Initial Communication Assessment initialized")
    
    def start_assessment(self, user_id: str) -> Dict:
        """
        Start a new baseline assessment for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Assessment session data
        """
        # Create assessment in storage
        assessment = self.storage.create_baseline_assessment(user_id)
        
        # Get assessment questions
        questions = self.question_bank.get_assessment_questions(count=5)
        
        # Initialize current assessment state
        self.current_assessment = {
            'assessment_id': assessment.assessment_id,
            'user_id': user_id,
            'questions': questions,
            'responses': [],
            'start_time': datetime.now(),
            'current_question_index': 0
        }
        
        # Store in storage for persistence
        self.storage.set_current_assessment(user_id, self.current_assessment)
        
        logger.info(f"Assessment started: {assessment.assessment_id} for user {user_id}")
        
        return {
            'assessment_id': assessment.assessment_id,
            'total_questions': len(questions),
            'current_question': questions[0].text,
            'question_index': 0,
            'estimated_duration_minutes': 5
        }
    
    def _load_current_assessment(self, user_id: str, assessment_id: str):
        """Load current assessment from storage."""
        assessment_data = self.storage.get_current_assessment(user_id)
        if assessment_data and assessment_data.get('assessment_id') == assessment_id:
            self.current_assessment = assessment_data
            return True
        return False
    
    def submit_response(self, assessment_id: str, response_type: str,
                       audio_data: Optional[np.ndarray] = None,
                       text_data: Optional[str] = None,
                       sample_rate: Optional[int] = None,
                       clipboard_detected: bool = False) -> Dict:
        """
        Submit a response to the current assessment question.
        
        Args:
            assessment_id: Assessment ID
            response_type: Type of response ('audio' or 'text')
            audio_data: Audio data (for voice responses)
            text_data: Text data (for text responses)
            sample_rate: Sample rate (for audio)
            clipboard_detected: Whether clipboard paste was detected
            
        Returns:
            Response processing result
        """
        if not self.current_assessment or self.current_assessment['assessment_id'] != assessment_id:
            # Try to load from storage
            found = False
            for user_id, data in self.storage.current_assessments.items():
                if data.get('assessment_id') == assessment_id:
                    self.current_assessment = data
                    found = True
                    break
            if not found:
                raise ValueError("No active assessment found")
        
        current_index = self.current_assessment['current_question_index']
        questions = self.current_assessment['questions']
        
        if current_index >= len(questions):
            raise ValueError("All questions already answered")
        
        current_question = questions[current_index]
        
        # Create response object
        response = AssessmentResponse(
            question_id=current_question.question_id,
            response_type=response_type,
            audio_data=audio_data,
            text_data=text_data,
            sample_rate=sample_rate
        )
        
        # Integrity checks
        is_flagged = False
        flag_reason = None
        
        if response_type == 'audio' and audio_data is not None:
            is_flagged, flag_reason = self.integrity_checker.check_audio_integrity(audio_data, sample_rate or 16000)
        elif response_type == 'text' and text_data is not None:
            is_flagged, flag_reason = self.integrity_checker.check_text_integrity(text_data, clipboard_detected)
        
        if is_flagged:
            response.is_flagged = True
            response.flag_reason = flag_reason
            logger.warning(f"Response flagged: {flag_reason}")
        
        # Process response through pipeline
        processing_result = self._process_response(response, current_question)
        
        # Store response
        response.processing_result = processing_result
        self.current_assessment['responses'].append(response)
        
        # Move to next question or complete assessment
        self.current_assessment['current_question_index'] += 1
        
        # Save updated state to storage
        self.storage.set_current_assessment(self.current_assessment['user_id'], self.current_assessment)
        
        if self.current_assessment['current_question_index'] >= len(questions):
            # Assessment complete
            return self._complete_assessment()
        else:
            # Return next question
            next_question = questions[self.current_assessment['current_question_index']]
            return {
                'status': 'in_progress',
                'next_question': next_question.text,
                'question_index': self.current_assessment['current_question_index'],
                'previous_result': processing_result
            }
    
    def _process_response(self, response: AssessmentResponse, question: AssessmentQuestion) -> Dict:
        """
        Process a response through the Speeky pipeline.
        
        Args:
            response: Assessment response
            question: Question being answered
            
        Returns:
            Processing result with scores
        """
        result = {
            'question_id': question.question_id,
            'category': question.category,
            'is_flagged': response.is_flagged,
            'flag_reason': response.flag_reason
        }
        
        if response.is_flagged:
            return result
        
        try:
            if response.response_type == 'audio' and response.audio_data is not None:
                # Process audio through pipeline
                pipeline_result = self.pipeline.process(
                    audio_input=response.audio_data,
                    sample_rate=response.sample_rate or 16000,
                    context_type='general',
                    skip_vad=False
                )
                
                result.update({
                    'transcription': pipeline_result.get('original_text', ''),
                    'fluency_score': pipeline_result.get('fluency_score', 0),
                    'pronunciation_score': pipeline_result.get('pronunciation_score', 0),
                    'grammar_errors': pipeline_result.get('grammar_errors', {}),
                    'processing_success': True
                })
                
            elif response.response_type == 'text' and response.text_data is not None:
                # Process text (limited analysis)
                result.update({
                    'transcription': response.text_data,
                    'fluency_score': 0,  # Cannot assess fluency from text alone
                    'pronunciation_score': None,
                    'grammar_errors': {},
                    'processing_success': True
                })
            
        except Exception as e:
            logger.error(f"Error processing response: {e}")
            result.update({
                'processing_success': False,
                'error': str(e)
            })
        
        return result
    
    def _complete_assessment(self) -> Dict:
        """
        Complete the assessment and calculate final scores.
        
        Returns:
            Final assessment results
        """
        if not self.current_assessment:
            raise ValueError("No active assessment to complete")
        
        responses = self.current_assessment['responses']
        assessment_id = self.current_assessment['assessment_id']
        user_id = self.current_assessment['user_id']
        
        # Calculate aggregate scores
        fluency_scores = []
        vocabulary_scores = []
        pronunciation_scores = []
        
        for response in responses:
            if hasattr(response, 'processing_result') and response.processing_result.get('processing_success'):
                fluency_scores.append(response.processing_result.get('fluency_score', 0))
                # Vocabulary score estimation from transcription quality
                vocab_score = self._estimate_vocabulary_score(response.processing_result.get('transcription', ''))
                vocabulary_scores.append(vocab_score)
                
                pron_score = response.processing_result.get('pronunciation_score')
                if pron_score is not None:
                    pronunciation_scores.append(pron_score)
        
        # Calculate averages
        avg_fluency = sum(fluency_scores) / len(fluency_scores) if fluency_scores else 0
        avg_vocabulary = sum(vocabulary_scores) / len(vocabulary_scores) if vocabulary_scores else 0
        avg_pronunciation = sum(pronunciation_scores) / len(pronunciation_scores) if pronunciation_scores else None
        
        # Calculate confidence score using the engine
        session_score = SessionScore(
            timestamp=datetime.now(),
            fluency_score=avg_fluency,
            vocabulary_score=avg_vocabulary,
            pronunciation_score=avg_pronunciation,
            is_text_only=avg_pronunciation is None,
            is_complete=True
        )
        
        confidence_score = self.confidence_engine.calculate_session_confidence(session_score)

        # Feed baseline result into the engine's history so score-breakdown (BAS-US-06)
        # and trend detection have data immediately after the baseline completes.
        self.confidence_engine.add_session_score(session_score)
        
        # Determine learning level
        learning_level = self._determine_learning_level(confidence_score)
        
        # Check for integrity flags
        flagged_responses = [r for r in responses if r.is_flagged]
        is_flagged = len(flagged_responses) > len(responses) / 2  # Flagged if >50% responses
        flag_reason = flagged_responses[0].flag_reason if flagged_responses else None
        
        # Complete assessment in storage
        try:
            self.storage.complete_baseline_assessment(
                assessment_id=assessment_id,
                fluency_score=avg_fluency,
                vocabulary_score=avg_vocabulary,
                pronunciation_score=avg_pronunciation if avg_pronunciation else 0,
                confidence_score=confidence_score,
                learning_level=learning_level
            )
            
            # Clear current assessment state from storage
            self.storage.clear_current_assessment(user_id)
            
            if is_flagged:
                self.storage.flag_assessment(assessment_id, flag_reason or "Multiple integrity flags")
        
        except Exception as e:
            logger.error(f"Error completing assessment in storage: {e}")
        
        # Calculate duration
        duration = (datetime.now() - self.current_assessment['start_time']).total_seconds()
        
        # Create result object
        result = AssessmentResult(
            user_id=user_id,
            assessment_id=assessment_id,
            responses=responses,
            fluency_score=avg_fluency,
            vocabulary_score=avg_vocabulary,
            pronunciation_score=avg_pronunciation,
            confidence_score=confidence_score,
            learning_level=learning_level,
            duration_seconds=duration,
            is_flagged=is_flagged,
            flag_reason=flag_reason
        )
        
        # Clear current assessment
        self.current_assessment = None
        
        logger.info(f"Assessment completed: {assessment_id} - Confidence: {confidence_score:.1f}")
        
        return {
            'status': 'completed',
            'assessment_id': assessment_id,
            'confidence_score': confidence_score,
            'fluency_score': avg_fluency,
            'vocabulary_score': avg_vocabulary,
            'pronunciation_score': avg_pronunciation,
            'learning_level': learning_level.value,
            'duration_seconds': duration,
            'is_flagged': is_flagged,
            'flag_reason': flag_reason
        }
    
    def _estimate_vocabulary_score(self, text: str) -> float:
        """
        Estimate vocabulary score from transcription.
        
        Args:
            text: Transcribed text
            
        Returns:
            Vocabulary score (0-100)
        """
        if not text:
            return 0
        
        words = text.split()
        if not words:
            return 0
        
        # Simple heuristics
        unique_words = len(set(word.lower() for word in words))
        total_words = len(words)
        
        # Lexical diversity
        lexical_diversity = unique_words / total_words if total_words > 0 else 0
        
        # Word length complexity
        avg_word_length = sum(len(word) for word in words) / total_words if total_words > 0 else 0
        
        # Combine metrics
        vocabulary_score = (lexical_diversity * 50) + (min(avg_word_length / 8, 1) * 50)
        
        return round(vocabulary_score, 2)
    
    def _determine_learning_level(self, confidence_score: float) -> LearningLevel:
        """
        Determine learning level from confidence score.
        
        Args:
            confidence_score: Overall confidence score
            
        Returns:
            Learning level
        """
        if confidence_score >= 90:
            return LearningLevel.PROFICIENT
        elif confidence_score >= 80:
            return LearningLevel.ADVANCED
        elif confidence_score >= 70:
            return LearningLevel.UPPER_INTERMEDIATE
        elif confidence_score >= 60:
            return LearningLevel.INTERMEDIATE
        elif confidence_score >= 40:
            return LearningLevel.ELEMENTARY
        else:
            return LearningLevel.BEGINNER
    
    def get_assessment_status(self, assessment_id: str) -> Dict:
        """
        Get status of an assessment.
        
        Args:
            assessment_id: Assessment ID
            
        Returns:
            Assessment status
        """
        if self.current_assessment and self.current_assessment['assessment_id'] == assessment_id:
            return {
                'status': 'in_progress',
                'current_question_index': self.current_assessment['current_question_index'],
                'total_questions': len(self.current_assessment['questions']),
                'elapsed_seconds': (datetime.now() - self.current_assessment['start_time']).total_seconds()
            }
        
        # Check in storage
        # This would require adding assessment status tracking to storage
        return {'status': 'unknown'}