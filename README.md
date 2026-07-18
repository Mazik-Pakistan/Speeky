# Speeky - AI-Assisted English Language Practice Pipeline

A self-hosted, offline-capable AI-assisted English language practice system focused on British English standards. Speeky provides comprehensive speech analysis including pronunciation scoring, fluency assessment, grammar correction, and conversational practice.

## Features

- **Speech Recognition**: FasterWhisper-based ASR with word-level timestamps
- **Voice Activity Detection**: SileroVAD for accurate speech segmentation
- **Pronunciation Analysis**: Phone-level alignment and scoring (with MFA support)
- **Fluency Assessment**: Speech rate, pause analysis, filled pause detection, lexical diversity
- **Grammar Correction**: Gramformer + spaCy + LLM enhancement for British English
- **Conversational AI**: Role-play scenarios (HR, Technical, Functional) using Ollama
- **Text-to-Speech**: Piper TTS with British English voices
- **Offline Capable**: All models run locally (except optional Ollama)

## System Requirements

- Python 3.8 or higher
- Standard laptop with CPU (GPU optional but not required)
- 8GB+ RAM recommended
- ~10GB disk space for models

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download spaCy Model

```bash
python -m spacy download en_core_web_sm
```

### 3. Install Ollama (for LLM features)

Ollama is required for the conversation engine and enhanced grammar correction.

**Windows:**
```bash
# Download from https://ollama.ai/download
# Or use winget:
winget install Ollama.Ollama
```

**Linux/Mac:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 4. Pull Llama 3.1 Model

```bash
ollama pull llama3.1:8b
```

### 5. Start Ollama Server

```bash
ollama serve
```

The server will run on `http://localhost:11434` by default.

### Optional: Montreal Forced Aligner (for British English phonemes)

For accurate British English phoneme alignment, install Montreal Forced Aligner:

```bash
# Follow instructions at: https://montreal-forced-aligner.readthedocs.io/
# Download British English acoustic model:
mfa model download acoustic english_uk_mfa
```

Note: If MFA is not installed, the system will use g2p_en (US English dictionary) as a fallback.

## Usage

### Basic Usage

Process a pre-recorded audio file:

```bash
python main.py --file input.wav
```

Record from microphone for 5 seconds:

```bash
python main.py --record --duration 5
```

Record until silence is detected:

```bash
python main.py --live
```

### Context-Specific Practice

Practice for different scenarios:

```bash
# HR Interview practice
python main.py --live --context hr

# Technical meeting practice
python main.py --live --context technical

# Functional conversation practice
python main.py --live --context functional
```

### Advanced Options

```bash
# Use specific ASR model
python main.py --file input.wav --asr-model large-v3

# Use different TTS voice
python main.py --file input.wav --tts-voice en_GB-cori-medium

# Disable LLM (use only Gramformer)
python main.py --file input.wav --no-llm

# Save detailed JSON output
python main.py --file input.wav --output results.json

# Play TTS audio after processing
python main.py --file input.wav --play-audio

# Skip VAD (for pre-segmented audio)
python main.py --file input.wav --skip-vad

# Custom Ollama URL
python main.py --file input.wav --ollama-url http://localhost:11434
```

### Check Component Status

Verify all components are available:

```bash
python main.py --check-status
```

## Project Structure

```
speeky/
├── __init__.py           # Package initialization
├── vad.py                # Voice Activity Detection (SileroVAD)
├── asr.py                # Speech Recognition (FasterWhisper)
├── alignment.py          # Word/Phoneme Alignment
├── pronunciation.py      # Pronunciation Scoring
├── grammar.py            # Grammar Correction
├── fluency.py            # Fluency Analysis
├── response.py           # Conversation Engine
├── tts.py                # Text-to-Speech (Piper)
└── pipeline.py           # Main Pipeline Orchestrator
main.py                   # Entry Point
requirements.txt          # Dependencies
README.md                 # This file
```

## Pipeline Flow

1. **Input**: Microphone recording or audio file
2. **VAD**: Speech detection and segmentation
3. **ASR**: Speech-to-text with word timestamps
4. **Alignment**: Word-level alignment refinement
5. **Pronunciation**: Phone-level scoring and analysis
6. **Fluency**: Speech rate, pauses, lexical diversity
7. **Grammar**: British English correction and explanation
8. **Conversation**: Contextual response generation
9. **TTS**: Convert corrected text to speech
10. **Output**: JSON results + audio file

## Output Format

The pipeline returns a JSON object with:

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "context_type": "general",
  "original_text": "Your original speech",
  "corrected_text": "Corrected British English version",
  "pronunciation_score": 85.5,
  "fluency_score": 78.2,
  "grammar_errors": {
    "error_density": 0.1,
    "spacy_analysis": {...}
  },
  "explanation": "Brief explanation of corrections",
  "response_text": "Conversational response",
  "audio_filename": "output/speeky_output_20240101_120000.wav",
  "errors": []
}
```

## Module Details

### VAD (vad.py)
- Uses SileroVAD ONNX model
- Provides speech segment detection
- Splits audio into utterance chunks

### ASR (asr.py)
- FasterWhisper with configurable model sizes
- Word-level timestamps for alignment
- Supports long audio chunking

### Alignment (alignment.py)
- Currently uses FasterWhisper word timestamps
- Optional WhisperX integration
- Placeholder for MFA phoneme alignment

### Pronunciation (pronunciation.py)
- GOP (Goodness of Pronunciation) scoring
- Uses g2p_en for phoneme conversion (US English)
- MFA support for British English phonemes
- Problematic word identification

### Grammar (grammar.py)
- Gramformer for basic corrections
- spaCy for linguistic analysis
- Ollama LLM for British English refinement
- Error density calculation

### Fluency (fluency.py)
- Speech rate and articulation rate
- Pause analysis (count, duration)
- Filled pause detection
- Lexical diversity (TTR, MTLD)
- Overall fluency scoring

### Response (response.py)
- Ollama with Llama 3.1 8B
- Context-aware role-play
- Conversation history management
- British English enforcement

### TTS (tts.py)
- Piper TTS with British voices
- Voices: en_GB-alan-medium, en_GB-cori-medium
- Automatic model downloading
- WAV file output

## Troubleshooting

### Ollama Connection Issues

If Ollama is not reachable:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama server
ollama serve
```

### Model Download Issues

Models are downloaded automatically on first use. If downloads fail:

- Check internet connection
- Verify sufficient disk space
- Try running with `--verbose` flag for details

### Audio Input Issues

If microphone recording fails:

- Check microphone permissions
- Verify sounddevice installation: `pip install sounddevice`
- Try pre-recorded file instead: `--file input.wav`

### Memory Issues

If you encounter memory errors:

- Use smaller ASR model: `--asr-model base`
- Close other applications
- Process shorter audio segments

### TTS Issues

If TTS fails:

- Check Piper installation: `pip install piper-tts`
- Verify voice model name: `--tts-voice en_GB-alan-medium`
- Use `--no-audio` to skip TTS

## Development

### Running Tests

```bash
# Test individual components
python -c "from speeky import VoiceActivityDetector; vad = VoiceActivityDetector()"

# Test pipeline status
python main.py --check-status
```

### Adding New Voices

Piper supports various British English voices:

```bash
# Available voices:
# - en_GB-alan-medium (default)
# - en_GB-alan-low
# - en_GB-cori-medium
# - en_GB-cori-low

python main.py --file input.wav --tts-voice en_GB-cori-medium
```

### Custom Contexts

To add custom conversation contexts, modify the `_get_context_system_prompt` method in `response.py`.

## Limitations

- **Phoneme Alignment**: Currently uses US English dictionary (g2p_en). For British English phonemes, install MFA.
- **GPU Support**: Optimized for CPU but can use GPU if available (configure in respective modules).
- **Real-time Processing**: Not real-time; processing time depends on audio length and model size.
- **Language Support**: Currently focused on English (British) only.

## License

This project uses various open-source components. Please refer to individual component licenses:

- FasterWhisper: MIT License
- SileroVAD: MIT License
- Piper TTS: MIT License
- Gramformer: Apache 2.0 License
- spaCy: MIT License
- Ollama: MIT License

## Contributing

Contributions are welcome! Areas for improvement:

- Full MFA integration with British English models
- WhisperX integration for advanced alignment
- Additional language support
- Real-time processing capabilities
- Web interface

## Acknowledgments

- [FasterWhisper](https://github.com/guillaumekln/faster-whisper) - Efficient ASR
- [SileroVAD](https://github.com/snakers4/silero-vad) - Voice Activity Detection
- [Piper TTS](https://github.com/rhasspy/piper) - Neural TTS
- [Gramformer](https://github.com/PrithivirajDamodaran/Gramformer) - Grammar Correction
- [Ollama](https://ollama.ai/) - Local LLM inference
- [Montreal Forced Aligner](https://montreal-forced-aligner.readthedocs.io/) - Phoneme Alignment

## Support

For issues or questions:

1. Check the troubleshooting section
2. Run with `--verbose` flag for detailed logs
3. Verify component status with `--check-status`
4. Check individual component documentation

## Roadmap

- [ ] Full MFA integration with British English acoustic models
- [ ] WhisperX integration for advanced word alignment
- [ ] Web interface for easier access
- [ ] Additional language support
- [ ] Real-time feedback mode
- [ ] Progress tracking and analytics
- [ ] Custom vocabulary and scenario support