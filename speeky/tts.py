"""
Text-to-Speech module using Piper TTS.

This module provides text-to-speech conversion using Piper TTS
with British English voice models.
"""

import logging
import numpy as np
import subprocess
import os
from typing import Optional
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Text-to-Speech using Piper TTS with British English voices.
    
    This class provides TTS capabilities using Piper TTS, which supports
    high-quality neural TTS with British English voices.
    """
    
    def __init__(
        self,
        voice: str = "en_GB-alan-medium",
        sample_rate: int = 22050,
        use_python_bindings: bool = True
    ):
        """
        Initialize the TTS engine.
        
        Args:
            voice: Voice model to use (e.g., 'en_GB-alan-medium')
            sample_rate: Output sample rate (Piper typically uses 22050)
            use_python_bindings: Whether to use Python bindings or subprocess
        """
        self.voice = voice
        self.sample_rate = sample_rate
        self.use_python_bindings = use_python_bindings
        self.piper_available = False
        self.voice_path = None
        
        self._check_piper()
    
    def _check_piper(self):
        """Check if Piper TTS is available."""
        if self.use_python_bindings:
            try:
                import piper_tts
                self.piper_available = True
                logger.info("Piper TTS Python bindings available")
            except ImportError:
                logger.warning("Piper TTS Python bindings not found, trying subprocess")
                self.use_python_bindings = False
        
        if not self.use_python_bindings:
            # Check for piper executable
            try:
                result = subprocess.run(['piper', '--help'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    self.piper_available = True
                    logger.info("Piper TTS executable available")
                else:
                    logger.warning("Piper TTS executable not found")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("Piper TTS not available")
    
    def synthesize(self, text: str, voice: Optional[str] = None) -> np.ndarray:
        """
        Synthesize speech from text.
        
        Args:
            text: Input text to synthesize
            voice: Optional voice override
            
        Returns:
            Audio waveform as numpy array at self.sample_rate
        """
        if not self.piper_available:
            raise RuntimeError("Piper TTS is not available")
        
        voice_to_use = voice or self.voice
        
        if self.use_python_bindings:
            return self._synthesize_with_bindings(text, voice_to_use)
        else:
            return self._synthesize_with_subprocess(text, voice_to_use)
    
    def _synthesize_with_bindings(self, text: str, voice: str) -> np.ndarray:
        """
        Synthesize using Piper Python bindings.
        
        Args:
            text: Input text
            voice: Voice model
            
        Returns:
            Audio waveform
        """
        try:
            from piper_tts import Piper
            
            # Download voice model if not present
            model_path = self._get_voice_model_path(voice)
            
            # Initialize Piper
            piper = Piper(model_path)
            
            # Synthesize
            audio = piper.synthesize(text)
            
            logger.info(f"Synthesized {len(text)} characters using {voice}")
            return audio
            
        except Exception as e:
            logger.error(f"Error synthesizing with Python bindings: {e}")
            raise
    
    def _synthesize_with_subprocess(self, text: str, voice: str) -> np.ndarray:
        """
        Synthesize using Piper subprocess.
        
        Args:
            text: Input text
            voice: Voice model
            
        Returns:
            Audio waveform
        """
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as text_file:
                text_file.write(text)
                text_path = text_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as audio_file:
                audio_path = audio_file.name
            
            try:
                # Run piper command
                cmd = [
                    'piper',
                    '--model', voice,
                    '--output_file', audio_path,
                    text_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                
                if result.returncode != 0:
                    logger.error(f"Piper error: {result.stderr.decode()}")
                    raise RuntimeError("Piper synthesis failed")
                
                # Load the generated audio
                from scipy.io import wavfile
                sample_rate, audio = wavfile.read(audio_path)
                
                # Convert to float32 if needed
                if audio.dtype == np.int16:
                    audio = audio.astype(np.float32) / 32768.0
                elif audio.dtype == np.int32:
                    audio = audio.astype(np.float32) / 2147483648.0
                
                # Resample if necessary
                if sample_rate != self.sample_rate:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=self.sample_rate)
                
                logger.info(f"Synthesized {len(text)} characters using {voice}")
                return audio
                
            finally:
                # Clean up temporary files
                os.unlink(text_path)
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
                    
        except Exception as e:
            logger.error(f"Error synthesizing with subprocess: {e}")
            raise
    
    def _get_voice_model_path(self, voice: str) -> str:
        """
        Get the path to a voice model, downloading if necessary.
        
        Args:
            voice: Voice model name
            
        Returns:
            Path to voice model
        """
        # Piper typically downloads models automatically
        # This is a placeholder for model management
        # In production, you'd want to cache models properly
        
        # Common British English voices in Piper:
        # - en_GB-alan-medium
        # - en_GB-alan-low
        # - en_GB-cori-medium
        # - en_GB-cori-low
        
        return voice
    
    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None
    ) -> str:
        """
        Synthesize speech and save to file.
        
        Args:
            text: Input text
            output_path: Path to save audio file
            voice: Optional voice override
            
        Returns:
            Path to saved file
        """
        audio = self.synthesize(text, voice)
        
        # Save as WAV
        from scipy.io import wavfile
        wavfile.write(output_path, self.sample_rate, (audio * 32767).astype(np.int16))
        
        logger.info(f"Saved audio to {output_path}")
        return output_path
    
    def get_available_voices(self) -> list:
        """
        Get list of available British English voices.
        
        Returns:
            List of voice names
        """
        # Common British English voices in Piper
        voices = [
            "en_GB-alan-medium",
            "en_GB-alan-low",
            "en_GB-cori-medium",
            "en_GB-cori-low"
        ]
        
        return voices
    
    def set_voice(self, voice: str):
        """
        Set the voice to use.
        
        Args:
            voice: Voice model name
        """
        if voice in self.get_available_voices():
            self.voice = voice
            logger.info(f"Voice set to: {voice}")
        else:
            logger.warning(f"Unknown voice: {voice}. Using default.")
    
    def is_available(self) -> bool:
        """
        Check if TTS is available.
        
        Returns:
            True if available, False otherwise
        """
        return self.piper_available