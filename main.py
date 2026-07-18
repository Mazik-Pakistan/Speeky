#!/usr/bin/env python3
"""
Speeky - Main entry point for the AI-assisted English language practice pipeline.

This script provides a command-line interface for recording speech from microphone
or processing audio files, then running the complete analysis pipeline.
"""

import argparse
import logging
import sys
import numpy as np
import sounddevice as sd
from scipy.io import wavfile
import json
import os
from pathlib import Path

# Import Speeky components
from speeky import SpeekyPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def record_audio(duration: int = 5, sample_rate: int = 16000) -> tuple:
    """
    Record audio from microphone.
    
    Args:
        duration: Recording duration in seconds
        sample_rate: Sample rate for recording
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    logger.info(f"Recording for {duration} seconds...")
    
    try:
        # Record audio
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()  # Wait until recording is finished
        
        # Flatten to 1D array
        audio = audio.flatten()
        
        logger.info(f"Recording complete: {len(audio)} samples")
        return audio, sample_rate
        
    except Exception as e:
        logger.error(f"Error recording audio: {e}")
        raise


def record_until_silence(
    max_duration: int = 30,
    sample_rate: int = 16000,
    silence_threshold: float = 0.01,
    silence_duration: float = 1.0
) -> tuple:
    """
    Record audio until silence is detected.
    
    Args:
        max_duration: Maximum recording duration in seconds
        sample_rate: Sample rate for recording
        silence_threshold: Amplitude threshold for silence detection
        silence_duration: Duration of silence to stop recording
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    logger.info("Recording until silence (press Ctrl+C to stop)...")
    
    try:
        audio_chunks = []
        chunk_size = int(sample_rate * 0.1)  # 100ms chunks
        silence_counter = 0
        max_silence_chunks = int(silence_duration * sample_rate / chunk_size)
        total_chunks = int(max_duration * sample_rate / chunk_size)
        
        def callback(indata, frames, time, status):
            if status:
                logger.warning(f"Recording status: {status}")
            
            audio_chunks.append(indata.copy())
            
            # Check for silence
            if len(indata) > 0:
                amplitude = np.max(np.abs(indata))
                if amplitude < silence_threshold:
                    nonlocal silence_counter
                    silence_counter += 1
                    if silence_counter >= max_silence_chunks:
                        raise sd.CallbackStop
                else:
                    silence_counter = 0
        
        # Start recording
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            callback=callback,
            blocksize=chunk_size
        ):
            while len(audio_chunks) < total_chunks:
                sd.sleep(100)
        
        # Combine chunks
        audio = np.concatenate(audio_chunks).flatten()
        
        logger.info(f"Recording complete: {len(audio)} samples")
        return audio, sample_rate
        
    except sd.CallbackStop:
        # Normal stop due to silence
        audio = np.concatenate(audio_chunks).flatten()
        logger.info(f"Silence detected, recording stopped: {len(audio)} samples")
        return audio, sample_rate
    except KeyboardInterrupt:
        # User interrupted
        if audio_chunks:
            audio = np.concatenate(audio_chunks).flatten()
            logger.info(f"Recording stopped by user: {len(audio)} samples")
            return audio, sample_rate
        else:
            logger.warning("No audio recorded")
            return np.array([]), sample_rate
    except Exception as e:
        logger.error(f"Error recording audio: {e}")
        raise


def load_audio(file_path: str) -> tuple:
    """
    Load audio from file.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    logger.info(f"Loading audio from {file_path}...")
    
    try:
        sample_rate, audio = wavfile.read(file_path)
        
        # Convert to float32 if needed
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        elif audio.dtype == np.float64:
            audio = audio.astype(np.float32)
        
        # Convert stereo to mono if needed
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        logger.info(f"Audio loaded: {len(audio)} samples at {sample_rate} Hz")
        return audio, sample_rate
        
    except Exception as e:
        logger.error(f"Error loading audio file: {e}")
        raise


def play_audio(file_path: str):
    """
    Play audio file using sounddevice.
    
    Args:
        file_path: Path to audio file
    """
    try:
        sample_rate, audio = wavfile.read(file_path)
        
        # Convert to float32 if needed
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        
        # Convert stereo to mono if needed
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        logger.info(f"Playing audio: {file_path}")
        sd.play(audio, sample_rate)
        sd.wait()
        
    except Exception as e:
        logger.error(f"Error playing audio: {e}")


def print_result(result: dict):
    """
    Print pipeline result in a formatted way.
    
    Args:
        result: Result dictionary from pipeline
    """
    print("\n" + "="*60)
    print("SPEEKY ANALYSIS RESULTS")
    print("="*60)
    
    print(f"\nOriginal Text:")
    print(f"  {result.get('original_text', 'N/A')}")
    
    print(f"\nCorrected Text:")
    print(f"  {result.get('corrected_text', 'N/A')}")
    
    print(f"\nExplanation:")
    print(f"  {result.get('explanation', 'N/A')}")
    
    print(f"\nScores:")
    print(f"  Pronunciation: {result.get('pronunciation_score', 0):.1f}/100")
    print(f"  Fluency: {result.get('fluency_score', 0):.1f}/100")
    
    if 'grammar_errors' in result:
        print(f"\nGrammar Analysis:")
        print(f"  Error Density: {result['grammar_errors'].get('error_density', 0):.3f}")
    
    print(f"\nConversational Response:")
    print(f"  {result.get('response_text', 'N/A')}")
    
    if result.get('audio_filename'):
        print(f"\nAudio Output:")
        print(f"  {result['audio_filename']}")
    
    if result.get('errors'):
        print(f"\nWarnings/Errors:")
        for error in result['errors']:
            print(f"  - {error}")
    
    print("\n" + "="*60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Speeky - AI-assisted English language practice pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a pre-recorded audio file
  python main.py --file input.wav --context hr
  
  # Record from microphone for 5 seconds
  python main.py --record --duration 5 --context technical
  
  # Record until silence is detected
  python main.py --live --context functional
  
  # Process file and save detailed JSON output
  python main.py --file input.wav --output results.json
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--file',
        type=str,
        help='Input audio file path (WAV format)'
    )
    input_group.add_argument(
        '--record',
        action='store_true',
        help='Record from microphone for fixed duration'
    )
    input_group.add_argument(
        '--live',
        action='store_true',
        help='Record from microphone until silence detected'
    )
    
    # Recording options
    parser.add_argument(
        '--duration',
        type=int,
        default=5,
        help='Recording duration in seconds (for --record mode, default: 5)'
    )
    parser.add_argument(
        '--sample-rate',
        type=int,
        default=16000,
        help='Audio sample rate (default: 16000)'
    )
    
    # Context options
    parser.add_argument(
        '--context',
        type=str,
        choices=['hr', 'technical', 'functional', 'general'],
        default='general',
        help='Conversation context type (default: general)'
    )
    
    # Pipeline options
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Disable LLM enhancement (use only Gramformer)'
    )
    parser.add_argument(
        '--ollama-url',
        type=str,
        default='http://localhost:11434',
        help='Ollama API URL (default: http://localhost:11434)'
    )
    parser.add_argument(
        '--skip-vad',
        action='store_true',
        help='Skip VAD (useful for pre-segmented audio)'
    )
    
    # Output options
    parser.add_argument(
        '--output',
        type=str,
        help='Save JSON result to file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Directory for audio output files (default: output)'
    )
    parser.add_argument(
        '--play-audio',
        action='store_true',
        help='Play TTS audio after processing'
    )
    parser.add_argument(
        '--no-audio',
        action='store_true',
        help='Skip TTS audio generation'
    )
    
    # Model options
    parser.add_argument(
        '--asr-model',
        type=str,
        default='distil-large-v3',
        choices=['tiny', 'base', 'small', 'medium', 'large-v3', 'distil-large-v3'],
        help='ASR model size (default: distil-large-v3)'
    )
    parser.add_argument(
        '--tts-voice',
        type=str,
        default='en_GB-alan-medium',
        help='TTS voice model (default: en_GB-alan-medium)'
    )
    
    # Other options
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--check-status',
        action='store_true',
        help='Check component status and exit'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize pipeline
    logger.info("Initializing Speeky pipeline...")
    
    try:
        pipeline = SpeekyPipeline(
            asr_model_size=args.asr_model,
            tts_voice=args.tts_voice,
            use_llm=not args.no_llm,
            ollama_url=args.ollama_url,
            lazy_loading=True
        )
        
        # Check status if requested
        if args.check_status:
            status = pipeline.get_status()
            print("\nComponent Status:")
            print("="*40)
            for component, available in status.items():
                status_str = "✓ Available" if available else "✗ Not available"
                print(f"  {component.ljust(20)}: {status_str}")
            print("="*40 + "\n")
            return
        
        # Get audio input
        if args.file:
            audio, sample_rate = load_audio(args.file)
        elif args.record:
            audio, sample_rate = record_audio(args.duration, args.sample_rate)
        elif args.live:
            audio, sample_rate = record_until_silence(
                max_duration=30,
                sample_rate=args.sample_rate
            )
        else:
            parser.error("No input method specified")
        
        # Check if audio was captured
        if len(audio) == 0:
            logger.error("No audio data captured")
            return
        
        # Process audio
        logger.info("Processing audio through pipeline...")
        result = pipeline.process(
            audio_input=audio,
            sample_rate=sample_rate,
            context_type=args.context,
            skip_vad=args.skip_vad,
            output_dir=args.output_dir
        )
        
        # Print results
        print_result(result)
        
        # Save JSON output if requested
        if args.output:
            pipeline.save_result(result, args.output)
            logger.info(f"JSON result saved to {args.output}")
        
        # Play audio if requested
        if args.play_audio and result.get('audio_filename'):
            try:
                play_audio(result['audio_filename'])
            except Exception as e:
                logger.error(f"Could not play audio: {e}")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()