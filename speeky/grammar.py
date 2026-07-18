"""
Grammar correction module using Gramformer, spaCy, and Ollama.

This module provides grammar correction with British English standards
using a combination of Gramformer, spaCy, and optional LLM enhancement via Ollama.
"""

import logging
import requests
import spacy
from typing import Dict, Optional, List
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GrammarCorrector:
    """
    Grammar correction using Gramformer, spaCy, and optional LLM enhancement.
    
    This class provides grammar correction with focus on British English
    using Gramformer for basic corrections and Ollama for advanced refinement.
    """
    
    def __init__(self, use_llm: bool = True, ollama_url: str = "http://localhost:11434"):
        """
        Initialize the grammar corrector.
        
        Args:
            use_llm: Whether to use Ollama LLM for enhanced correction
            ollama_url: URL for Ollama API
        """
        self.use_llm = use_llm
        self.ollama_url = ollama_url
        self.gramformer = None
        self.nlp = None
        self.ollama_available = False
        
        self._load_models()
        self._check_ollama()
    
    def _load_models(self):
        """Load Gramformer and spaCy models."""
        try:
            logger.info("Loading Gramformer...")
            from gramformer import Gramformer
            self.gramformer = Gramformer(models=1, use_gpu=False)  # models=1 for corrector
            logger.info("Gramformer loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Gramformer: {e}")
            logger.warning("Will use spaCy and LLM only for grammar correction")
        
        try:
            logger.info("Loading spaCy model (en_core_web_sm)...")
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {e}")
            logger.warning("spaCy features will be limited")
    
    def _check_ollama(self):
        """Check if Ollama is available."""
        if not self.use_llm:
            return
        
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                self.ollama_available = True
                logger.info("Ollama is available")
            else:
                logger.warning("Ollama responded but may not be ready")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self.ollama_available = False
    
    def correct_text(self, text: str, use_llm: bool = True) -> Dict[str, any]:
        """
        Correct text grammar and style to British English.
        
        Args:
            text: Input text to correct
            use_llm: Whether to use LLM for enhanced correction
            
        Returns:
            Dictionary containing:
                - 'corrected': Corrected text
                - 'explanation': Explanation of changes
                - 'error_density': Error density score
                - 'grammer_only': Gramformer-only correction (if available)
        """
        logger.info(f"Correcting text: '{text}'")
        
        # Step 1: Basic correction with Gramformer
        gramformer_result = self._correct_with_gramformer(text)
        
        # Step 2: LLM enhancement (if available and requested)
        if use_llm and self.ollama_available:
            llm_result = self._correct_with_llm(gramformer_result or text)
            corrected_text = llm_result['corrected']
            explanation = llm_result['explanation']
        else:
            # Use Gramformer result or original text
            corrected_text = gramformer_result if gramformer_result else text
            explanation = "Basic grammar correction applied"
        
        # Step 3: Calculate error density
        error_density = self._calculate_error_density(text, corrected_text)
        
        # Step 4: Analyze with spaCy for additional insights
        spacy_analysis = self._analyze_with_spacy(text, corrected_text)
        
        result = {
            'corrected': corrected_text,
            'explanation': explanation,
            'error_density': error_density,
            'gramformer_only': gramformer_result,
            'spacy_analysis': spacy_analysis
        }
        
        logger.info(f"Grammar correction complete: {len(text)} -> {len(corrected_text)} chars")
        return result
    
    def _correct_with_gramformer(self, text: str) -> Optional[str]:
        """
        Correct text using Gramformer.
        
        Args:
            text: Input text
            
        Returns:
            Corrected text or None if Gramformer unavailable
        """
        if self.gramformer is None:
            return None
        
        try:
            # Gramformer expects a list of sentences
            corrections = self.gramformer.correct(text)
            
            # Take the first correction if available
            if corrections and len(corrections) > 0:
                corrected = list(corrections)[0]
                logger.debug(f"Gramformer correction: '{text}' -> '{corrected}'")
                return corrected
            else:
                return text
                
        except Exception as e:
            logger.error(f"Error in Gramformer correction: {e}")
            return None
    
    def _correct_with_llm(self, text: str) -> Dict[str, str]:
        """
        Correct text using Ollama LLM with British English focus.
        
        Args:
            text: Input text to correct
            
        Returns:
            Dictionary with 'corrected' and 'explanation'
        """
        prompt = f"""Correct the following text to idiomatic British English. Maintain the original meaning.

Output format:
Corrected: [corrected sentence]
Explanation: [brief explanation of changes, if any]

Original: {text}"""
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "max_tokens": 200
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_output = result.get('response', '')
                
                # Parse the response
                corrected = self._parse_llm_correction(llm_output, text)
                explanation = self._parse_llm_explanation(llm_output)
                
                return {
                    'corrected': corrected,
                    'explanation': explanation
                }
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._fallback_correction(text)
                
        except Exception as e:
            logger.error(f"Error in LLM correction: {e}")
            return self._fallback_correction(text)
    
    def _parse_llm_correction(self, llm_output: str, original: str) -> str:
        """
        Parse corrected text from LLM output.
        
        Args:
            llm_output: Raw LLM response
            original: Original text for fallback
            
        Returns:
            Corrected text
        """
        # Try to extract "Corrected:" line
        match = re.search(r'Corrected:\s*(.*?)(?:\n|$)', llm_output, re.IGNORECASE)
        if match:
            corrected = match.group(1).strip()
            if corrected and corrected != original:
                return corrected
        
        # Fallback: return original if no correction found
        return original
    
    def _parse_llm_explanation(self, llm_output: str) -> str:
        """
        Parse explanation from LLM output.
        
        Args:
            llm_output: Raw LLM response
            
        Returns:
            Explanation text
        """
        # Try to extract "Explanation:" line
        match = re.search(r'Explanation:\s*(.*?)(?:\n|$)', llm_output, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return "No explanation provided"
    
    def _fallback_correction(self, text: str) -> Dict[str, str]:
        """
        Fallback correction when LLM fails.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with original text and fallback explanation
        """
        return {
            'corrected': text,
            'explanation': "LLM correction unavailable - using original text"
        }
    
    def _calculate_error_density(self, original: str, corrected: str) -> float:
        """
        Calculate error density (changes per word).
        
        Args:
            original: Original text
            corrected: Corrected text
            
        Returns:
            Error density score (0-1, lower is better)
        """
        original_words = original.split()
        corrected_words = corrected.split()
        
        if len(original_words) == 0:
            return 0.0
        
        # Simple comparison: count different words
        differences = sum(1 for o, c in zip(original_words, corrected_words) if o != c)
        differences += abs(len(original_words) - len(corrected_words))
        
        error_density = differences / len(original_words)
        return min(1.0, error_density)
    
    def _analyze_with_spacy(self, original: str, corrected: str) -> Dict[str, any]:
        """
        Analyze text with spaCy for linguistic insights.
        
        Args:
            original: Original text
            corrected: Corrected text
            
        Returns:
            Dictionary with spaCy analysis results
        """
        if self.nlp is None:
            return {'available': False}
        
        try:
            orig_doc = self.nlp(original)
            corr_doc = self.nlp(corrected)
            
            analysis = {
                'available': True,
                'original': {
                    'tokens': len(orig_doc),
                    'sentences': len(list(orig_doc.sents)),
                    'pos_tags': [token.pos_ for token in orig_doc]
                },
                'corrected': {
                    'tokens': len(corr_doc),
                    'sentences': len(list(corr_doc.sents)),
                    'pos_tags': [token.pos_ for token in corr_doc]
                }
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in spaCy analysis: {e}")
            return {'available': False, 'error': str(e)}
    
    def generate_correction_prompt(self, user_text: str) -> str:
        """
        Generate a prompt for grammar correction (used by response module).
        
        Args:
            user_text: User's text to correct
            
        Returns:
            Formatted prompt for LLM
        """
        return f"""Correct the following to idiomatic British English. Maintain the original meaning. Output only the corrected sentence and a brief explanation of changes.

Original: {user_text}"""