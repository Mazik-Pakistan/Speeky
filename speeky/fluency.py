"""
Fluency analysis module for speech assessment.

This module provides fluency metrics including speech rate, pause analysis,
filled pauses, and lexical diversity assessment.
"""

import logging
import numpy as np
import librosa
from typing import List, Dict, Optional
from lexicalrichness import LexicalRichness

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FluencyAnalyzer:
    """
    Fluency analysis for speech assessment.
    
    This class provides comprehensive fluency metrics including speech rate,
    pause analysis, filled pause detection, and lexical diversity.
    """
    
    def __init__(self):
        """Initialize the fluency analyzer."""
        self.pause_threshold = 0.2  # 200ms pause threshold
        self.filled_pauses = ['um', 'uh', 'er', 'erm', 'ah', 'like', 'you know']
    
    def analyze_fluency(
        self,
        audio: np.ndarray,
        sample_rate: int,
        word_timings: List[Dict[str, any]],
        transcript: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Analyze fluency metrics from audio and word timings.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
            word_timings: List of word timing dictionaries
            transcript: Optional transcript for lexical analysis
            
        Returns:
            Dictionary containing fluency metrics:
                - 'speech_rate': Words per second (overall)
                - 'articulation_rate': Words per second (excluding pauses)
                - 'pause_count': Number of pauses
                - 'mean_pause_duration': Average pause duration
                - 'filled_pauses': Count of filled pauses
                - 'lexical_diversity': Lexical diversity metrics
                - 'overall_score': Weighted fluency score
        """
        logger.info("Analyzing fluency...")
        
        if not word_timings:
            logger.warning("No word timings provided for fluency analysis")
            return self._empty_result()
        
        # Calculate basic timing metrics
        timing_metrics = self._calculate_timing_metrics(word_timings)
        
        # Analyze pauses
        pause_metrics = self._analyze_pauses(word_timings)
        
        # Detect filled pauses
        filled_pause_count = self._detect_filled_pauses(transcript) if transcript else 0
        
        # Calculate lexical diversity
        lexical_metrics = self._calculate_lexical_diversity(transcript) if transcript else {}
        
        # Calculate overall fluency score
        overall_score = self._calculate_overall_score(
            timing_metrics, pause_metrics, filled_pause_count, lexical_metrics
        )
        
        result = {
            'speech_rate': timing_metrics['speech_rate'],
            'articulation_rate': timing_metrics['articulation_rate'],
            'pause_count': pause_metrics['pause_count'],
            'mean_pause_duration': pause_metrics['mean_pause_duration'],
            'total_pause_duration': pause_metrics['total_pause_duration'],
            'filled_pauses': filled_pause_count,
            'lexical_diversity': lexical_metrics,
            'overall_score': overall_score
        }
        
        logger.info(f"Fluency analysis complete: overall score {overall_score:.1f}/100")
        return result
    
    def _empty_result(self) -> Dict[str, any]:
        """Return empty result when no data available."""
        return {
            'speech_rate': 0.0,
            'articulation_rate': 0.0,
            'pause_count': 0,
            'mean_pause_duration': 0.0,
            'total_pause_duration': 0.0,
            'filled_pauses': 0,
            'lexical_diversity': {},
            'overall_score': 0.0
        }
    
    def _calculate_timing_metrics(self, word_timings: List[Dict]) -> Dict[str, float]:
        """
        Calculate basic timing metrics.
        
        Args:
            word_timings: List of word timing dictionaries
            
        Returns:
            Dictionary with speech_rate and articulation_rate
        """
        if not word_timings:
            return {'speech_rate': 0.0, 'articulation_rate': 0.0}
        
        # Calculate total duration
        first_word = word_timings[0]
        last_word = word_timings[-1]
        total_duration = last_word['end'] - first_word['start']
        
        # Count words
        word_count = len(word_timings)
        
        # Calculate speech rate (words per second)
        speech_rate = word_count / total_duration if total_duration > 0 else 0.0
        
        # Calculate articulation rate (excluding pauses)
        speech_duration = sum(w['end'] - w['start'] for w in word_timings)
        articulation_rate = word_count / speech_duration if speech_duration > 0 else 0.0
        
        return {
            'speech_rate': speech_rate,
            'articulation_rate': articulation_rate
        }
    
    def _analyze_pauses(self, word_timings: List[Dict]) -> Dict[str, float]:
        """
        Analyze pauses between words.
        
        Args:
            word_timings: List of word timing dictionaries
            
        Returns:
            Dictionary with pause metrics
        """
        pauses = []
        
        for i in range(len(word_timings) - 1):
            current_word = word_timings[i]
            next_word = word_timings[i + 1]
            
            # Calculate gap between words
            gap = next_word['start'] - current_word['end']
            
            # Only count as pause if above threshold
            if gap > self.pause_threshold:
                pauses.append(gap)
        
        pause_count = len(pauses)
        mean_pause_duration = np.mean(pauses) if pauses else 0.0
        total_pause_duration = sum(pauses)
        
        return {
            'pause_count': pause_count,
            'mean_pause_duration': mean_pause_duration,
            'total_pause_duration': total_pause_duration
        }
    
    def _detect_filled_pauses(self, transcript: str) -> int:
        """
        Detect filled pauses in transcript.
        
        Args:
            transcript: Text transcript
            
        Returns:
            Count of filled pauses
        """
        if not transcript:
            return 0
        
        words = transcript.lower().split()
        filled_pause_count = sum(1 for word in words if word in self.filled_pauses)
        
        return filled_pause_count
    
    def _calculate_lexical_diversity(self, transcript: str) -> Dict[str, float]:
        """
        Calculate lexical diversity metrics.
        
        Args:
            transcript: Text transcript
            
        Returns:
            Dictionary with lexical diversity metrics
        """
        if not transcript:
            return {}
        
        try:
            lex = LexicalRichness(transcript)
            
            metrics = {
                'ttr': lex.ttr,  # Type-Token Ratio
                'mtld': lex.mtld(threshold=0.72),  # Measure of Textual Lexical Diversity
                'hdd': lex.hdd(draws=42),  # Hypergeometric Distribution D
                'word_count': len(transcript.split())
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating lexical diversity: {e}")
            return {}
    
    def _calculate_overall_score(
        self,
        timing_metrics: Dict[str, float],
        pause_metrics: Dict[str, float],
        filled_pause_count: int,
        lexical_metrics: Dict[str, float]
    ) -> float:
        """
        Calculate overall fluency score (0-100).
        
        Scoring criteria:
        - Speech rate: 2-4 words/sec is ideal (40 points)
        - Pause frequency: Fewer pauses is better (20 points)
        - Filled pauses: Fewer is better (20 points)
        - Lexical diversity: Higher is better (20 points)
        
        Args:
            timing_metrics: Timing metrics
            pause_metrics: Pause metrics
            filled_pause_count: Count of filled pauses
            lexical_metrics: Lexical diversity metrics
            
        Returns:
            Overall fluency score (0-100)
        """
        score = 0.0
        
        # Speech rate scoring (40 points)
        speech_rate = timing_metrics['speech_rate']
        if 2.0 <= speech_rate <= 4.0:
            score += 40.0
        elif 1.5 <= speech_rate <= 5.0:
            score += 30.0
        elif speech_rate > 0:
            score += 20.0
        
        # Pause frequency scoring (20 points)
        pause_count = pause_metrics['pause_count']
        if pause_count == 0:
            score += 20.0
        elif pause_count <= 2:
            score += 15.0
        elif pause_count <= 5:
            score += 10.0
        else:
            score += 5.0
        
        # Filled pauses scoring (20 points)
        if filled_pause_count == 0:
            score += 20.0
        elif filled_pause_count <= 1:
            score += 15.0
        elif filled_pause_count <= 3:
            score += 10.0
        else:
            score += 5.0
        
        # Lexical diversity scoring (20 points)
        if lexical_metrics:
            ttr = lexical_metrics.get('ttr', 0)
            if ttr >= 0.5:
                score += 20.0
            elif ttr >= 0.4:
                score += 15.0
            elif ttr >= 0.3:
                score += 10.0
            else:
                score += 5.0
        else:
            score += 10.0  # Neutral score if unavailable
        
        return min(100.0, max(0.0, score))
    
    def analyze_audio_features(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> Dict[str, any]:
        """
        Analyze basic audio features using librosa.
        
        Args:
            audio: Audio data
            sample_rate: Sample rate
            
        Returns:
            Dictionary with audio features
        """
        try:
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13)
            
            # Extract zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(audio)
            
            # Extract spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)
            
            return {
                'mfcc_mean': np.mean(mfccs, axis=1).tolist(),
                'mfcc_std': np.std(mfccs, axis=1).tolist(),
                'zcr_mean': float(np.mean(zcr)),
                'zcr_std': float(np.std(zcr)),
                'spectral_centroid_mean': float(np.mean(spectral_centroids)),
                'spectral_centroid_std': float(np.std(spectral_centroids))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing audio features: {e}")
            return {}