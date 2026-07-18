"""
Automatic Speech Recognition module using FasterWhisper.

This module provides speech-to-text transcription with word-level timestamps
using the FasterWhisper library for efficient ASR.
"""

import logging
import numpy as np
from typing import Dict, List, Optional
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutomaticSpeechRecognition:
    """
    Speech-to-Text using FasterWhisper model.
    
    This class provides transcription capabilities with word-level timestamps
    for downstream alignment and analysis tasks.
    """
    
    def __init__(
        self, 
        model_size: str = "distil-large-v3",
        device: str = "cpu",
        compute_type: str = "int8"
    ):
        """
        Initialize the ASR with FasterWhisper model.
        
        Args:
            model_size: Model size ('tiny', 'base', 'small', 'medium', 'large-v3', 'distil-large-v3')
            device: Device to run model on ('cpu' or 'cuda')
            compute_type: Computation type ('float16', 'float32', 'int8', 'int8_float16')
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the FasterWhisper model."""
        try:
            logger.info(f"Loading FasterWhisper model: {self.model_size}")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("FasterWhisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load FasterWhisper model: {e}")
            raise
    
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str = "en",
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = True
    ) -> Dict[str, any]:
        """
        Transcribe audio to text with word timestamps.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio (default: 16000)
            language: Language code (default: 'en' for English)
            beam_size: Beam size for decoding
            vad_filter: Whether to use VAD filtering
            word_timestamps: Whether to return word-level timestamps
            
        Returns:
            Dictionary containing:
                - 'text': Full transcription text
                - 'segments': List of segment dictionaries with word details
                - 'language': Detected language
        """
        if self.model is None:
            raise RuntimeError("ASR model not loaded")
        
        # Convert audio to float32 if needed
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        try:
            logger.info("Starting transcription...")
            
            # Run transcription
            segments, info = self.model.transcribe(
                audio,
                language=language,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps,
                sample_rate=sample_rate
            )
            
            # Collect segments and words
            all_segments = []
            full_text = ""
            
            for segment in segments:
                segment_data = {
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text,
                    'words': []
                }
                
                # Extract word-level information
                if word_timestamps and segment.words:
                    for word in segment.words:
                        word_data = {
                            'word': word.word.strip(),
                            'start': word.start,
                            'end': word.end,
                            'probability': word.probability
                        }
                        segment_data['words'].append(word_data)
                
                all_segments.append(segment_data)
                full_text += segment.text + " "
            
            # Clean up full text
            full_text = full_text.strip()
            
            result = {
                'text': full_text,
                'segments': all_segments,
                'language': info.language,
                'language_probability': info.language_probability
            }
            
            logger.info(f"Transcription complete: {len(full_text)} characters, {len(all_segments)} segments")
            return result
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            raise
    
    def transcribe_long_audio(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        chunk_length_s: int = 30,
        **kwargs
    ) -> Dict[str, any]:
        """
        Transcribe long audio by chunking it.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
            chunk_length_s: Length of each chunk in seconds
            **kwargs: Additional arguments for transcribe()
            
        Returns:
            Dictionary with same structure as transcribe()
        """
        chunk_samples = chunk_length_s * sample_rate
        total_samples = len(audio)
        num_chunks = (total_samples + chunk_samples - 1) // chunk_samples
        
        logger.info(f"Transcribing long audio ({num_chunks} chunks)")
        
        all_segments = []
        full_text = ""
        time_offset = 0.0
        
        for i in range(num_chunks):
            start = i * chunk_samples
            end = min((i + 1) * chunk_samples, total_samples)
            chunk = audio[start:end]
            
            # Transcribe chunk
            result = self.transcribe(chunk, sample_rate, **kwargs)
            
            # Adjust timestamps
            for segment in result['segments']:
                segment['start'] += time_offset
                segment['end'] += time_offset
                for word in segment['words']:
                    word['start'] += time_offset
                    word['end'] += time_offset
            
            all_segments.extend(result['segments'])
            full_text += result['text'] + " "
            time_offset += len(chunk) / sample_rate
        
        return {
            'text': full_text.strip(),
            'segments': all_segments,
            'language': result.get('language', 'en'),
            'language_probability': result.get('language_probability', 1.0)
        }
    
    def get_word_timings(self, transcription_result: Dict) -> List[Dict[str, any]]:
        """
        Extract word-level timings from transcription result.
        
        Args:
            transcription_result: Result from transcribe() method
            
        Returns:
            List of word dictionaries with timing information
        """
        word_timings = []
        
        for segment in transcription_result['segments']:
            if 'words' in segment:
                word_timings.extend(segment['words'])
        
        return word_timings