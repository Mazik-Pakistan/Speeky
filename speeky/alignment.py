"""
Word and phoneme alignment module.

This module provides word-level alignment capabilities for pronunciation analysis.
Currently uses FasterWhisper's built-in word timestamps, with optional WhisperX support.
"""

import logging
import numpy as np
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WordAligner:
    """
    Word-level alignment for pronunciation analysis.
    
    This class provides word alignment using FasterWhisper's word timestamps.
    For more advanced alignment, WhisperX can be integrated (optional).
    """
    
    def __init__(self, use_whisperx: bool = False):
        """
        Initialize the word aligner.
        
        Args:
            use_whisperx: Whether to use WhisperX for advanced alignment
                         (requires whisperx installation, defaults to False)
        """
        self.use_whisperx = use_whisperx
        self.whisperx_model = None
        
        if use_whisperx:
            self._load_whisperx()
    
    def _load_whisperx(self):
        """Load WhisperX model for advanced alignment."""
        try:
            import whisperx
            logger.info("Loading WhisperX model for advanced alignment...")
            # WhisperX model loading would go here
            # self.whisperx_model = whisperx.load_model("large-v3", device="cpu")
            logger.warning("WhisperX integration not fully implemented - using FasterWhisper timestamps")
            self.use_whisperx = False
        except ImportError:
            logger.warning("WhisperX not installed, falling back to FasterWhisper timestamps")
            self.use_whisperx = False
        except Exception as e:
            logger.error(f"Failed to load WhisperX: {e}")
            self.use_whisperx = False
    
    def align_words(
        self,
        audio: np.ndarray,
        sample_rate: int,
        transcript: str,
        asr_word_timings: Optional[List[Dict]] = None
    ) -> List[Dict[str, any]]:
        """
        Align words to audio with refined timestamps.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
            transcript: Transcript text
            asr_word_timings: Optional word timings from ASR (if provided, will be refined)
            
        Returns:
            List of aligned word dictionaries with 'word', 'start', 'end', 'confidence'
        """
        if self.use_whisperx and self.whisperx_model is not None:
            return self._align_with_whisperx(audio, sample_rate, transcript)
        elif asr_word_timings is not None:
            # Use and refine ASR word timings
            return self._refine_asr_timings(asr_word_timings, transcript)
        else:
            # Fallback: create simple alignment based on word count
            return self._create_simple_alignment(audio, sample_rate, transcript)
    
    def _align_with_whisperx(
        self,
        audio: np.ndarray,
        sample_rate: int,
        transcript: str
    ) -> List[Dict[str, any]]:
        """
        Perform alignment using WhisperX (if available).
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            transcript: Transcript text
            
        Returns:
            List of aligned words
        """
        # Placeholder for WhisperX implementation
        # This would use whisperx.align for more accurate alignment
        logger.info("Using WhisperX for alignment")
        
        # For now, fall back to simple alignment
        return self._create_simple_alignment(audio, sample_rate, transcript)
    
    def _refine_asr_timings(
        self,
        asr_word_timings: List[Dict],
        transcript: str
    ) -> List[Dict[str, any]]:
        """
        Refine ASR word timings by matching with transcript.
        
        Args:
            asr_word_timings: Word timings from ASR
            transcript: Reference transcript
            
        Returns:
            Refined word alignments
        """
        logger.info("Refining ASR word timings")
        
        # Clean transcript words
        transcript_words = transcript.lower().split()
        
        # Match ASR words with transcript words
        aligned_words = []
        asr_words = [w['word'].lower().strip() for w in asr_word_timings]
        
        # Simple alignment - in production, use more sophisticated matching
        for i, timing in enumerate(asr_word_timings):
            if i < len(transcript_words):
                aligned_words.append({
                    'word': transcript_words[i],
                    'start': timing['start'],
                    'end': timing['end'],
                    'confidence': timing.get('probability', 1.0)
                })
        
        logger.info(f"Refined {len(aligned_words)} word alignments")
        return aligned_words
    
    def _create_simple_alignment(
        self,
        audio: np.ndarray,
        sample_rate: int,
        transcript: str
    ) -> List[Dict[str, any]]:
        """
        Create simple word alignment based on word count and audio duration.
        
        This is a fallback method when no ASR timings are available.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            transcript: Transcript text
            
        Returns:
            List of word alignments with evenly distributed timestamps
        """
        logger.warning("Using simple alignment (evenly distributed word timings)")
        
        words = transcript.split()
        audio_duration = len(audio) / sample_rate
        
        if len(words) == 0:
            return []
        
        # Distribute words evenly across audio duration
        word_duration = audio_duration / len(words)
        aligned_words = []
        
        for i, word in enumerate(words):
            start_time = i * word_duration
            end_time = (i + 1) * word_duration
            
            aligned_words.append({
                'word': word,
                'start': start_time,
                'end': end_time,
                'confidence': 0.5  # Low confidence for simple alignment
            })
        
        logger.info(f"Created simple alignment for {len(aligned_words)} words")
        return aligned_words
    
    def align_phonemes(
        self,
        audio: np.ndarray,
        sample_rate: int,
        word_alignments: List[Dict[str, any]],
        phoneme_dictionary: Optional[Dict] = None
    ) -> List[Dict[str, any]]:
        """
        Align phonemes within words (placeholder for MFA integration).
        
        This is a stub for phoneme-level alignment. For full phoneme alignment,
        Montreal Forced Aligner (MFA) should be used.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            word_alignments: Word-level alignments
            phoneme_dictionary: Optional phoneme dictionary
            
        Returns:
            List of phoneme alignments (currently placeholder)
        """
        logger.info("Phoneme alignment requires MFA - returning placeholder")
        
        # Placeholder structure
        phoneme_alignments = []
        
        for word_align in word_alignments:
            word = word_align['word']
            start = word_align['start']
            end = word_align['end']
            
            # This would be replaced with actual MFA phoneme alignment
            # For now, create placeholder phoneme entries
            phoneme_alignments.append({
                'word': word,
                'phonemes': [],  # Would contain phoneme details
                'start': start,
                'end': end
            })
        
        return phoneme_alignments