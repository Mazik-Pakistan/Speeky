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

try:
    from .vad import VoiceActivityDetector
    from .asr import AutomaticSpeechRecognition
    from .alignment import WordAligner
    from .pronunciation import PronunciationScorer
    from .grammar import GrammarCorrector
    from .fluency import FluencyAnalyzer
    from .response import ConversationEngine
    from .tts import TextToSpeech
    from .confidence import ConfidenceScoreEngine, SessionScore
except ImportError:
    # For standalone testing
    try:
        from vad import VoiceActivityDetector
        from asr import AutomaticSpeechRecognition
        from alignment import WordAligner
        from pronunciation import PronunciationScorer
        from grammar import GrammarCorrector
        from fluency import FluencyAnalyzer
        from response import ConversationEngine
        from tts import TextToSpeech
        from confidence import ConfidenceScoreEngine, SessionScore
    except ImportError:
        # If dependencies not available, create dummy classes for testing
        VoiceActivityDetector = None
        AutomaticSpeechRecognition = None
        WordAligner = None
        PronunciationScorer = None
        GrammarCorrector = None
        FluencyAnalyzer = None
        ConversationEngine = None
        TextToSpeech = None
        try:
            from .confidence import ConfidenceScoreEngine, SessionScore
        except ImportError:
            from confidence import ConfidenceScoreEngine, SessionScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        lazy_loading: bool = True,
        confidence_engine: Optional[ConfidenceScoreEngine] = None
    ):
        """
        Initialize the Speeky pipeline.
        
        Args:
            asr_model_size: Size of ASR model
            tts_voice: TTS voice to use
            use_llm: Whether to use LLM for enhancement
            ollama_url: URL for Ollama API
            lazy_loading: Whether to load models lazily
            confidence_engine: Optional confidence score engine
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
        
        # Confidence score engine
        self.confidence_engine = confidence_engine or ConfidenceScoreEngine()
        
        # Load components if not lazy loading
        if not lazy_loading:
            self._load_all_components()
    
    def _load_all_components(self):
        """Load all pipeline components."""
        logger.info("Loading all pipeline components...")
        
        if VoiceActivityDetector:
            try:
                self.vad = VoiceActivityDetector()
                logger.info("VAD loaded")
            except Exception as e:
                logger.error(f"Failed to load VAD: {e}")
        
        if AutomaticSpeechRecognition:
            try:
                self.asr = AutomaticSpeechRecognition(model_size=self.asr_model_size)
                logger.info("ASR loaded")
            except Exception as e:
                logger.error(f"Failed to load ASR: {e}")
        
        if WordAligner:
            try:
                self.aligner = WordAligner()
                logger.info("Word aligner loaded")
            except Exception as e:
                logger.error(f"Failed to load aligner: {e}")
        
        if PronunciationScorer:
            try:
                self.pronunciation_scorer = PronunciationScorer()
                logger.info("Pronunciation scorer loaded")
            except Exception as e:
                logger.error(f"Failed to load pronunciation scorer: {e}")
        
        if GrammarCorrector:
            try:
                self.grammar_corrector = GrammarCorrector(use_llm=self.use_llm, ollama_url=self.ollama_url)
                logger.info("Grammar corrector loaded")
            except Exception as e:
                logger.error(f"Failed to load grammar corrector: {e}")
        
        if FluencyAnalyzer:
            try:
                self.fluency_analyzer = FluencyAnalyzer()
                logger.info("Fluency analyzer loaded")
            except Exception as e:
                logger.error(f"Failed to load fluency analyzer: {e}")
        
        if ConversationEngine:
            try:
                self.conversation_engine = ConversationEngine(ollama_url=self.ollama_url)
                logger.info("Conversation engine loaded")
            except Exception as e:
                logger.error(f"Failed to load conversation engine: {e}")
        
        if TextToSpeech:
            try:
                self.tts = TextToSpeech(voice=self.tts_voice)
                logger.info("TTS loaded")
            except Exception as e:
                logger.error(f"Failed to load TTS: {e}")
        
        logger.info("All components loaded")
    
    def _ensure_component(self, component_name: str):
        """Ensure a component is loaded (for lazy loading)."""
        if self.lazy_loading:
            if component_name == "vad" and self.vad is None and VoiceActivityDetector:
                self.vad = VoiceActivityDetector()
            elif component_name == "asr" and self.asr is None and AutomaticSpeechRecognition:
                self.asr = AutomaticSpeechRecognition(model_size=self.asr_model_size)
            elif component_name == "aligner" and self.aligner is None and WordAligner:
                self.aligner = WordAligner()
            elif component_name == "pronunciation" and self.pronunciation_scorer is None and PronunciationScorer:
                self.pronunciation_scorer = PronunciationScorer()
            elif component_name == "grammar" and self.grammar_corrector is None and GrammarCorrector:
                self.grammar_corrector = GrammarCorrector(use_llm=self.use_llm, ollama_url=self.ollama_url)
            elif component_name == "fluency" and self.fluency_analyzer is None and FluencyAnalyzer:
                self.fluency_analyzer = FluencyAnalyzer()
            elif component_name == "conversation" and self.conversation_engine is None and ConversationEngine:
                self.conversation_engine = ConversationEngine(ollama_url=self.ollama_url)
            elif component_name == "tts" and self.tts is None and TextToSpeech:
                self.tts = TextToSpeech(voice=self.tts_voice)
    
    def process(
        self,
        audio_input: np.ndarray,
        sample_rate: int,
        context_type: str = "general",
        skip_vad: bool = False,
        output_dir: str = "output"
    ) -> Dict:
        """
        Process audio input through the complete pipeline.
        
        Args:
            audio_input: Audio data as numpy array
            sample_rate: Sample rate of the audio
            context_type: Context type for conversation (hr, technical, functional, general)
            skip_vad: Whether to skip VAD (useful for pre-segmented audio)
            output_dir: Directory to save output files
            
        Returns:
            Dictionary with complete analysis results
        """
        try:
            logger.info("Starting pipeline processing...")
            
            # Create output directory if needed
            os.makedirs(output_dir, exist_ok=True)
            
            # Initialize result dictionary
            result = {
                'timestamp': datetime.now().isoformat(),
                'context_type': context_type,
                'original_text': '',
                'corrected_text': '',
                'pronunciation_score': None,
                'fluency_score': 0.0,
                'grammar_errors': {},
                'explanation': '',
                'response_text': '',
                'audio_filename': '',
                'errors': []
            }
            
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
                result['fluency_score'] = 0.0
            
            # Step 5.5: Vocabulary score estimation
            vocabulary_score = self._estimate_vocabulary_score(result['original_text'])
            result['vocabulary_score'] = vocabulary_score
            
            # Step 5.6: Confidence score calculation
            try:
                # Create session score for confidence calculation
                session_score = SessionScore(
                    timestamp=datetime.now(),
                    fluency_score=result.get('fluency_score', 0.0),
                    vocabulary_score=vocabulary_score,
                    pronunciation_score=result.get('pronunciation_score'),
                    is_text_only=False,
                    is_complete=True
                )
                
                # Add to confidence engine
                self.confidence_engine.add_session_score(session_score)
                
                # Get current confidence score
                result['confidence_score'] = self.confidence_engine.get_confidence_score()
                result['confidence_breakdown'] = self.confidence_engine.get_confidence_breakdown()
                
            except Exception as e:
                logger.error(f"Error calculating confidence score: {e}")
                result['confidence_score'] = 0.0
                result['errors'].append(f"Confidence score calculation failed: {str(e)}")
            
            # Use default values if components not available
            if 'fluency_score' not in result:
                result['fluency_score'] = 0.0
            if 'vocabulary_score' not in result:
                result['vocabulary_score'] = 0.0
            if 'confidence_score' not in result:
                result['confidence_score'] = 0.0
            
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
            return {
                'timestamp': datetime.now().isoformat(),
                'context_type': context_type,
                'original_text': '',
                'corrected_text': '',
                'pronunciation_score': None,
                'fluency_score': 0.0,
                'grammar_errors': {},
                'explanation': '',
                'response_text': '',
                'audio_filename': '',
                'errors': [f"Pipeline error: {str(e)}"]
            }
    
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
    
    def _estimate_vocabulary_score(self, text: str) -> float:
        """
        Estimate vocabulary score from transcription.
        
        Args:
            text: Transcribed text
            
        Returns:
            Vocabulary score (0-100)
        """
        if not text:
            return 0.0
        
        words = text.split()
        if not words:
            return 0.0
        
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