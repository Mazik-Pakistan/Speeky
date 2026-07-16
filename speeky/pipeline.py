"""
Pipeline orchestrator for the Speeky language practice system.

This module provides the main pipeline that orchestrates all components
to process speech input and provide comprehensive feedback.
"""

import logging
import numpy as np
import json
from typing import Dict, Optional, List
import os
from datetime import datetime
from .formality import FormalityTier
from .vad import VoiceActivityDetector
from .asr import AutomaticSpeechRecognition
from .alignment import WordAligner
from .pronunciation import PronunciationScorer
from .grammar import GrammarCorrector
from .fluency import FluencyAnalyzer
from .response import ConversationEngine
from .tts import TextToSpeech
from .confidence import ConfidenceGrammarAnalyzer
from .code_switch_text import TextCodeSwitchDetector
from .code_switch_tolerance import CodeSwitchToleranceWrapper
from .cultural_terms import CulturalTermClassifier
from .retry_drill import RetryDrillService
from .word_mastery import WordMasteryTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Context types treated as high-stakes/professional for US-21's E-02
# (Professional Context Violation). ASSUMPTION: pipeline.py's docstring
# only documents context_type values as (hr, technical, functional,
# general) with no further definition of what each represents. This set
# is a best-effort mapping and should be confirmed with whoever owns the
# context_type semantics.
HIGH_STAKES_CONTEXT_TYPES = {"hr", "technical", "functional"}


class SpeekyPipeline:
    """
    Main pipeline orchestrator for Speeky language practice system.

    This class coordinates all modules to provide comprehensive
    speech analysis and feedback for English language practice.
    """

    def __init__(
        self,
        asr_model_size: str = "distil-large-v3",
        tts_voice: str = "en_GB-alan-medium",
        use_llm: bool = True,
        ollama_url: str = "http://localhost:11434",
        lazy_loading: bool = True
    ):
        """
        Initialize the Speeky pipeline.

        Args:
            asr_model_size: Size of ASR model
            tts_voice: TTS voice to use
            use_llm: Whether to use LLM for enhancement
            ollama_url: URL for Ollama API
            lazy_loading: Whether to load models lazily
        """
        self.asr_model_size = asr_model_size
        self.tts_voice = tts_voice
        self.use_llm = use_llm
        self.ollama_url = ollama_url
        self.lazy_loading = lazy_loading

        # Components (loaded lazily if enabled)
        self.vad = None
        self.asr = None
        self.aligner = None
        self.pronunciation_scorer = None
        self.grammar_corrector = None
        self.fluency_analyzer = None
        self.conversation_engine = None
        self.tts = None
        self.confidence_analyzer = None

        # Code-Switch Coaching components (US-56/57/58)
        self.code_switch_detector = None
        self.tolerance_wrapper = None
        self.cultural_classifier = None
        self.retry_drill = None
        self.mastery_tracker = None

        # Load components if not lazy loading
        if not lazy_loading:
            self._load_all_components()

    def _load_all_components(self):
        """Load all pipeline components."""
        logger.info("Loading all pipeline components...")

        try:
            self.vad = VoiceActivityDetector()
            logger.info("VAD loaded")
        except Exception as e:
            logger.error(f"Failed to load VAD: {e}")

        try:
            self.asr = AutomaticSpeechRecognition(model_size=self.asr_model_size)
            logger.info("ASR loaded")
        except Exception as e:
            logger.error(f"Failed to load ASR: {e}")

        try:
            self.aligner = WordAligner()
            logger.info("Word aligner loaded")
        except Exception as e:
            logger.error(f"Failed to load aligner: {e}")

        try:
            self.pronunciation_scorer = PronunciationScorer()
            logger.info("Pronunciation scorer loaded")
        except Exception as e:
            logger.error(f"Failed to load pronunciation scorer: {e}")

        try:
            self.grammar_corrector = GrammarCorrector(use_llm=self.use_llm, ollama_url=self.ollama_url)
            logger.info("Grammar corrector loaded")
        except Exception as e:
            logger.error(f"Failed to load grammar corrector: {e}")

        try:
            self.fluency_analyzer = FluencyAnalyzer()
            logger.info("Fluency analyzer loaded")
        except Exception as e:
            logger.error(f"Failed to load fluency analyzer: {e}")

        try:
            self.conversation_engine = ConversationEngine(ollama_url=self.ollama_url)
            logger.info("Conversation engine loaded")
        except Exception as e:
            logger.error(f"Failed to load conversation engine: {e}")

        try:
            self.tts = TextToSpeech(voice=self.tts_voice)
            logger.info("TTS loaded")
        except Exception as e:
            logger.error(f"Failed to load TTS: {e}")

        try:
            self.confidence_analyzer = ConfidenceGrammarAnalyzer()
            logger.info("Confidence/grammar analyzer loaded")
        except Exception as e:
            logger.error(f"Failed to load confidence/grammar analyzer: {e}")

        try:
            self.code_switch_detector = TextCodeSwitchDetector(
                nlp=self.grammar_corrector.nlp if self.grammar_corrector else None
            )
            self.tolerance_wrapper = CodeSwitchToleranceWrapper(detector=self.code_switch_detector)
            self.cultural_classifier = CulturalTermClassifier()
            self.retry_drill = RetryDrillService()
            self.mastery_tracker = WordMasteryTracker()
            logger.info("Code-switch coaching components loaded")
        except Exception as e:
            logger.error(f"Failed to load code-switch coaching components: {e}")

        logger.info("All components loaded")

    def _ensure_component(self, component_name: str):
        """Ensure a component is loaded (for lazy loading)."""
        if self.lazy_loading:
            if component_name == "vad" and self.vad is None:
                self.vad = VoiceActivityDetector()
            elif component_name == "asr" and self.asr is None:
                self.asr = AutomaticSpeechRecognition(model_size=self.asr_model_size)
            elif component_name == "aligner" and self.aligner is None:
                self.aligner = WordAligner()
            elif component_name == "pronunciation" and self.pronunciation_scorer is None:
                self.pronunciation_scorer = PronunciationScorer()
            elif component_name == "grammar" and self.grammar_corrector is None:
                self.grammar_corrector = GrammarCorrector(use_llm=self.use_llm, ollama_url=self.ollama_url)
            elif component_name == "fluency" and self.fluency_analyzer is None:
                self.fluency_analyzer = FluencyAnalyzer()
            elif component_name == "conversation" and self.conversation_engine is None:
                self.conversation_engine = ConversationEngine(ollama_url=self.ollama_url)
            elif component_name == "tts" and self.tts is None:
                self.tts = TextToSpeech(voice=self.tts_voice)
            elif component_name == "confidence" and self.confidence_analyzer is None:
                self.confidence_analyzer = ConfidenceGrammarAnalyzer()
            elif component_name == "code_switch" and self.tolerance_wrapper is None:
                self.code_switch_detector = TextCodeSwitchDetector(
                    nlp=self.grammar_corrector.nlp if self.grammar_corrector else None
                )
                self.tolerance_wrapper = CodeSwitchToleranceWrapper(detector=self.code_switch_detector)
                self.cultural_classifier = CulturalTermClassifier()
                self.retry_drill = RetryDrillService()
                self.mastery_tracker = WordMasteryTracker()

    def process(
        self,
        audio_input: np.ndarray,
        sample_rate: int,
        context_type: str = "general",
        skip_vad: bool = False,
        output_dir: str = "output",
        learner_id: str = "anonymous",
        is_timed_assessment: bool = False,
    ) -> Dict:
        """
        Process audio input through the complete pipeline.

        Args:
            audio_input: Audio data as numpy array
            sample_rate: Sample rate of the audio
            context_type: Context type for conversation (hr, technical, functional, general)
            skip_vad: Whether to skip VAD (useful for pre-segmented audio)
            output_dir: Directory to save output files
            learner_id: Learner identifier, used for code-switch coaching
                personalization (US-56/57/58). Defaults to "anonymous" for
                backward compatibility with existing callers.
            is_timed_assessment: True if this is a scored, time-boxed
                exercise (WEC-US-05 E-05) — suppresses the interactive
                retry prompt during timing-sensitive segments.

        Returns:
            Dictionary with complete analysis results
        """
        logger.info("Starting pipeline processing...")

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        # Initialize result dictionary
        result = {
            'timestamp': datetime.now().isoformat(),
            'context_type': context_type,
            'original_text': '',
            'corrected_text': '',
            'pronunciation_score': 0.0,
            'fluency_score': 0.0,
            'grammar_errors': {},
            'explanation': '',
            'response_text': '',
            'audio_filename': '',
            'confidence_analysis': {},
            'code_switch_flags': [],
            'retry_prompt': None,
            'mastery_newly_mastered': [],
            'errors': []
        }

        try:
            # Step 1: VAD and segmentation (if not skipped)
            if not skip_vad:
                self._ensure_component("vad")
                if self.vad:
                    segments = self.vad.get_speech_segments(audio_input, sample_rate)
                    if segments:
                        audio_chunks = self.vad.segment_audio(audio_input, sample_rate, segments)
                        # Use the first substantial segment
                        if audio_chunks:
                            audio_input = audio_chunks[0]
                            logger.info(f"Using first speech segment: {len(audio_input)} samples")
                        else:
                            logger.warning("No speech segments detected, using original audio")
                    else:
                        logger.warning("No speech detected, using original audio")

            # Step 2: ASR
            self._ensure_component("asr")
            if self.asr:
                transcription = self.asr.transcribe(audio_input, sample_rate)
                result['original_text'] = transcription['text']
                word_timings = self.asr.get_word_timings(transcription)
                logger.info(f"Transcription: {transcription['text']}")
            else:
                logger.error("ASR not available")
                result['errors'].append("ASR component not available")
                return result

            if not result['original_text']:
                logger.warning("Empty transcription, skipping further analysis")
                return result

            # Step 3: Word alignment
            self._ensure_component("aligner")
            if self.aligner:
                word_alignments = self.aligner.align_words(
                    audio_input, sample_rate, result['original_text'], word_timings
                )
            else:
                word_alignments = word_timings

            # Step 4: Pronunciation scoring
            self._ensure_component("pronunciation")
            if self.pronunciation_scorer:
                pronunciation_result = self.pronunciation_scorer.score_pronunciation(
                    audio_input, sample_rate, word_alignments, result['original_text']
                )
                result['pronunciation_score'] = pronunciation_result['overall_score']
                result['pronunciation_details'] = pronunciation_result
            else:
                result['errors'].append("Pronunciation scorer not available")

            # Step 5: Fluency analysis
            self._ensure_component("fluency")
            if self.fluency_analyzer:
                fluency_result = self.fluency_analyzer.analyze_fluency(
                    audio_input, sample_rate, word_alignments, result['original_text']
                )
                result['fluency_score'] = fluency_result['overall_score']
                result['fluency_details'] = fluency_result
            else:
                result['errors'].append("Fluency analyzer not available")
                fluency_result = {}

            # Step 6: Grammar correction
            self._ensure_component("grammar")
            if self.grammar_corrector:
                grammar_result = self.grammar_corrector.correct_text(
                    result['original_text'], use_llm=self.use_llm
                )
                result['corrected_text'] = grammar_result['corrected']
                result['explanation'] = grammar_result['explanation']
                result['grammar_errors'] = {
                    'error_density': grammar_result['error_density'],
                    'spacy_analysis': grammar_result.get('spacy_analysis', {})
                }
            else:
                result['errors'].append("Grammar corrector not available")
                result['corrected_text'] = result['original_text']
                grammar_result = {}

            # Step 6.5: Confidence vs. Grammar analysis (US-21)
            self._ensure_component("confidence")
            is_high_stakes = context_type in HIGH_STAKES_CONTEXT_TYPES
            formality_tier = (
                FormalityTier.FORMAL_HIGH_STAKES if is_high_stakes else FormalityTier.PROFESSIONAL
            )
            if self.confidence_analyzer:
                confidence_analysis = self.confidence_analyzer.analyze(
                    fluency_result, grammar_result, formality_tier=formality_tier
                )
                result['confidence_analysis'] = confidence_analysis
            else:
                result['errors'].append("Confidence/grammar analyzer not available")

            # Step 6.6: Code-Switch Coaching (US-56/57/58)
            self._ensure_component("code_switch")
            if self.tolerance_wrapper:
                tolerance_result = self.tolerance_wrapper.evaluate(
                    session_id=learner_id,
                    text=result['original_text'],
                    formality_tier=formality_tier,
                )
                flags = tolerance_result.get("flags", [])

                # US-56: classify each flag as target word / cultural term
                classified_flags = [
                    self.cultural_classifier.classify(f, learner_id) for f in flags
                ]
                result['code_switch_flags'] = classified_flags

                # US-57: consolidated retry prompt for TARGET_WORD flags only
                # (cultural terms aren't things to eliminate, so no retry
                # drill fires on them).
                target_flags = [
                    f for f in classified_flags if f["category"] == "target_word"
                ]
                retry_result = self.retry_drill.evaluate(
                    learner_id=learner_id,
                    flags=target_flags,
                    formality_tier=formality_tier,
                    is_timed_assessment=is_timed_assessment,
                )
                result['retry_prompt'] = retry_result

                # US-58: mastery tracking. GAP — this pipeline only sees
                # FLAGGED words (code-switch occurrences), never "clean
                # opportunities" (target vocabulary correctly used
                # instead of code-switched). That signal doesn't exist
                # anywhere in this codebase yet; without it, words can
                # never graduate to Mastered from here alone. Logging
                # flags only, for now — someone needs to define where
                # the "clean opportunity" signal comes from.
                for f in target_flags:
                    self.mastery_tracker.record_flag(learner_id, f["token"])
            else:
                result['errors'].append("Code-switch coaching components not available")

            # Step 7: Conversational response
            self._ensure_component("conversation")
            if self.conversation_engine:
                response = self.conversation_engine.generate_response(
                    result['original_text'], context_type
                )
                result['response_text'] = response
            else:
                result['errors'].append("Conversation engine not available")

            # Step 8: TTS for corrected text
            self._ensure_component("tts")
            if self.tts:
                try:
                    audio_filename = os.path.join(
                        output_dir,
                        f"speeky_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    )
                    self.tts.synthesize_to_file(result['corrected_text'], audio_filename)
                    result['audio_filename'] = audio_filename
                    logger.info(f"TTS audio saved to {audio_filename}")
                except Exception as e:
                    logger.error(f"TTS failed: {e}")
                    result['errors'].append(f"TTS failed: {str(e)}")
            else:
                result['errors'].append("TTS not available")

            logger.info("Pipeline processing complete")
            return result

        except Exception as e:
            logger.error(f"Pipeline processing error: {e}")
            result['errors'].append(f"Pipeline error: {str(e)}")
            return result

    def process_batch(
        self,
        audio_files: List[str],
        context_type: str = "general",
        output_dir: str = "output"
    ) -> List[Dict]:
        """
        Process multiple audio files in batch.

        Args:
            audio_files: List of audio file paths
            context_type: Context type for conversation
            output_dir: Directory to save output files

        Returns:
            List of result dictionaries
        """
        results = []

        for audio_file in audio_files:
            try:
                # Load audio file
                from scipy.io import wavfile
                sample_rate, audio = wavfile.read(audio_file)

                # Convert to float32 if needed
                if audio.dtype == np.int16:
                    audio = audio.astype(np.float32) / 32768.0
                elif audio.dtype == np.int32:
                    audio = audio.astype(np.float32) / 2147483648.0

                # Process
                result = self.process(audio, sample_rate, context_type, output_dir=output_dir)
                result['source_file'] = audio_file
                results.append(result)

            except Exception as e:
                logger.error(f"Error processing {audio_file}: {e}")
                results.append({
                    'source_file': audio_file,
                    'error': str(e)
                })

        return results

    def get_status(self) -> Dict[str, bool]:
        """
        Get the status of all pipeline components.

        Returns:
            Dictionary with component availability status
        """
        return {
            'vad': self.vad is not None,
            'asr': self.asr is not None,
            'aligner': self.aligner is not None,
            'pronunciation': self.pronunciation_scorer is not None,
            'grammar': self.grammar_corrector is not None,
            'fluency': self.fluency_analyzer is not None,
            'conversation': self.conversation_engine is not None,
            'tts': self.tts is not None,
            'confidence': self.confidence_analyzer is not None,
            'code_switch_coaching': self.tolerance_wrapper is not None,
            'ollama_available': self.conversation_engine.ollama_available if self.conversation_engine else False
        }

    def save_result(self, result: Dict, output_path: str):
        """
        Save result to JSON file.

        Args:
            result: Result dictionary
            output_path: Path to save JSON file
        """
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Result saved to {output_path}")