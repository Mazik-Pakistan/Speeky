"""
Voice Activity Detection module using SileroVAD.

This module provides speech detection and audio segmentation capabilities
using the Silero VAD model for accurate speech activity detection.
"""

import logging
import torch
import numpy as np
from typing import List, Dict, Optional
from silero_vad import get_speech_timestamps, load_silero_vad, read_audio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    """
    Voice Activity Detector using SileroVAD model.
    
    This class provides methods to detect speech segments in audio
    and segment audio into utterance chunks.
    """
    
    def __init__(self, sample_rate: int = 16000):
        """
        Initialize the VAD with Silero model.
        
        Args:
            sample_rate: Audio sample rate (default: 16000 for SileroVAD)
        """
        self.sample_rate = sample_rate
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the Silero VAD model."""
        try:
            logger.info("Loading Silero VAD model...")
            self.model = load_silero_vad()
            logger.info("Silero VAD model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise
    
    def get_speech_segments(
        self, 
        audio: np.ndarray, 
        sample_rate: int,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
        speech_pad_ms: int = 30
    ) -> List[Dict[str, float]]:
        """
        Detect speech segments in audio.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
            min_speech_duration_ms: Minimum speech duration in milliseconds
            min_silence_duration_ms: Minimum silence duration in milliseconds  
            speech_pad_ms: Speech padding in milliseconds
            
        Returns:
            List of speech segments with 'start' and 'end' times in seconds
        """
        if self.model is None:
            raise RuntimeError("VAD model not loaded")
        
        # Convert audio to float32 if needed
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Resample if necessary
        if sample_rate != self.sample_rate:
            logger.warning(f"Audio sample rate {sample_rate} differs from VAD rate {self.sample_rate}")
            # Note: In production, you'd want to resample here using librosa or similar
            # For now, we'll assume the audio is already at the correct rate
        
        try:
            # Get speech timestamps using Silero VAD
            speech_timestamps = get_speech_timestamps(
                audio,
                self.model,
                sampling_rate=self.sample_rate,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
                speech_pad_ms=speech_pad_ms,
                return_seconds=True
            )
            
            # Convert to standard format
            segments = [
                {'start': seg['start'], 'end': seg['end']}
                for seg in speech_timestamps
            ]
            
            logger.info(f"Detected {len(segments)} speech segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error detecting speech segments: {e}")
            raise
    
    def segment_audio(
        self, 
        audio: np.ndarray, 
        sample_rate: int, 
        segments: List[Dict[str, float]]
    ) -> List[np.ndarray]:
        """
        Split audio into utterance chunks based on speech segments.
        
        Args:
            audio: Full audio data as numpy array
            sample_rate: Sample rate of the audio
            segments: List of speech segments with 'start' and 'end' times
            
        Returns:
            List of audio chunks (numpy arrays)
        """
        audio_chunks = []
        
        for seg in segments:
            start_sample = int(seg['start'] * sample_rate)
            end_sample = int(seg['end'] * sample_rate)
            
            # Ensure bounds are valid
            start_sample = max(0, start_sample)
            end_sample = min(len(audio), end_sample)
            
            if end_sample > start_sample:
                chunk = audio[start_sample:end_sample]
                audio_chunks.append(chunk)
                logger.debug(f"Segment {len(audio_chunks)}: {seg['start']:.2f}s - {seg['end']:.2f}s")
            else:
                logger.warning(f"Invalid segment bounds: {seg}")
        
        logger.info(f"Created {len(audio_chunks)} audio segments")
        return audio_chunks
    
    def is_speech(self, audio_chunk: np.ndarray, threshold: float = 0.5) -> bool:
        """
        Determine if a short audio chunk contains speech.
        
        Args:
            audio_chunk: Short audio segment
            threshold: Probability threshold for speech detection
            
        Returns:
            True if speech is detected, False otherwise
        """
        if self.model is None:
            raise RuntimeError("VAD model not loaded")
        
        try:
            # This is a simplified check - for more accurate results,
            # use get_speech_segments on the full audio
            audio_tensor = torch.from_numpy(audio_chunk).float()
            if len(audio_tensor.shape) == 1:
                audio_tensor = audio_tensor.unsqueeze(0)
            
            with torch.no_grad():
                speech_prob = self.model(audio_tensor, self.sample_rate).item()
            
            return speech_prob > threshold
            
        except Exception as e:
            logger.error(f"Error checking for speech: {e}")
            return False