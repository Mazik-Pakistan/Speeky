"""
Conversation engine module using Ollama LLM.

This module provides conversational AI capabilities using Ollama with Llama 3.1 8B,
focused on British English language coaching and role-play scenarios.
"""

import logging
import requests
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConversationEngine:
    """
    Conversation engine using Ollama LLM for British English coaching.
    
    This class manages conversation history and generates contextual responses
    for language practice scenarios (HR, Technical, Functional).
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        """
        Initialize the conversation engine.
        
        Args:
            ollama_url: URL for Ollama API
            model: Model name to use in Ollama
        """
        self.ollama_url = ollama_url
        self.model = model
        self.conversation_history: List[Dict[str, str]] = []
        self.available = False
        
        self._check_ollama()
        self._initialize_system_prompt()
    
    def _check_ollama(self):
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                self.available = True
                logger.info("Ollama is available for conversation engine")
            else:
                logger.warning(f"Ollama responded with status {response.status_code}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self.available = False
    
    def _initialize_system_prompt(self):
        """Initialize the system prompt for British English coaching."""
        self.system_prompt = """You are a polite British English language coach. Your role is to help users practice their English skills through conversation and role-play.

Guidelines:
- Use British English spelling and vocabulary (e.g., "colour" instead of "color", "centre" instead of "center")
- Be encouraging and constructive in your feedback
- Keep responses concise (2-3 sentences maximum)
- If the user makes errors, gently provide the corrected version in your reply
- Adapt your language to the requested scenario (HR interview, technical meeting, functional conversation)
- Role-play appropriately for the context
- If asked about grammar or vocabulary, provide clear, helpful explanations
- Maintain a professional yet friendly tone"""
    
    def _get_context_system_prompt(self, context_type: str) -> str:
        """
        Get context-specific system prompt.
        
        Args:
            context_type: Type of context ('hr', 'technical', 'functional', 'general')
            
        Returns:
            Context-specific system prompt
        """
        context_prompts = {
            'hr': """Context: HR Interview
You are conducting a professional HR interview. Ask relevant questions about the candidate's experience, skills, and career goals. Provide feedback on their communication style and language use.""",
            
            'technical': """Context: Technical Meeting
You are in a technical discussion about software development. Discuss technical concepts, coding practices, and project details. Use appropriate technical terminology while maintaining clarity.""",
            
            'functional': """Context: Functional Conversation
You are engaging in everyday conversation. Discuss daily life, hobbies, interests, and general topics. Use natural, conversational language."""
        }
        
        context_addition = context_prompts.get(context_type.lower(), "")
        return f"{self.system_prompt}\n\n{context_addition}"
    
    def generate_response(
        self,
        user_text: str,
        context_type: str = "general"
    ) -> str:
        """
        Generate a conversational response to user input.
        
        Args:
            user_text: User's input text
            context_type: Type of conversation context
            
        Returns:
            Generated response text
        """
        if not self.available:
            return self._fallback_response(user_text)
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_text
        })
        
        # Prepare messages with system prompt
        system_prompt = self._get_context_system_prompt(context_type)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "max_tokens": 150
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                assistant_message = result.get('message', {}).get('content', '')
                
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                # Keep history manageable (last 10 messages)
                if len(self.conversation_history) > 10:
                    self.conversation_history = self.conversation_history[-10:]
                
                logger.debug(f"Generated response: {assistant_message[:50]}...")
                return assistant_message
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return self._fallback_response(user_text)
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._fallback_response(user_text)
    
    def _fallback_response(self, user_text: str) -> str:
        """
        Fallback response when Ollama is unavailable.
        
        Args:
            user_text: User's input text
            
        Returns:
            Fallback response
        """
        fallback_responses = [
            "I'm sorry, but I'm having trouble connecting right now. Please try again.",
            "Could you please repeat that? I'm experiencing some technical difficulties.",
            "I apologise, but I'm unable to respond at the moment. Please check if Ollama is running."
        ]
        
        import random
        return random.choice(fallback_responses)
    
    def generate_correction_prompt(self, user_text: str) -> str:
        """
        Generate a grammar correction prompt (used by grammar module).
        
        Args:
            user_text: User's text to correct
            
        Returns:
            Formatted correction prompt
        """
        return f"""Correct the following to idiomatic British English. Maintain the original meaning. Output only the corrected sentence and a brief explanation of changes.

Original: {user_text}"""
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def get_history(self) -> List[Dict[str, str]]:
        """
        Get current conversation history.
        
        Returns:
            List of conversation messages
        """
        return self.conversation_history.copy()
    
    def set_context(self, context_type: str):
        """
        Set the conversation context type.
        
        Args:
            context_type: Type of context ('hr', 'technical', 'functional', 'general')
        """
        valid_contexts = ['hr', 'technical', 'functional', 'general']
        if context_type.lower() in valid_contexts:
            logger.info(f"Context set to: {context_type}")
        else:
            logger.warning(f"Unknown context type: {context_type}. Using 'general'.")
    
    def generate_scenario_prompt(self, scenario: str) -> str:
        """
        Generate a prompt for a specific role-play scenario.
        
        Args:
            scenario: Description of the scenario
            
        Returns:
            Formatted scenario prompt
        """
        return f"""Scenario: {scenario}

Engage in role-play according to this scenario. Stay in character and respond naturally as a British English speaker would in this situation. Keep responses concise and helpful for language practice."""