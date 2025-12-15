"""
Gemini LLM Provider - Uses Google's Generative AI API.

================================================================================
GEMINI API
================================================================================

Google's Gemini models are multimodal and handle massive context windows.
- Gemini 1.5 Pro: 1M token context (can read whole books!)
- Gemini 1.5 Flash: Fast, cheap

We use the `google-generativeai` SDK.

Authentication:
Using API Key (AI Studio) is simplest for prototyping.
For production (Vertex AI), we'd use Application Default Credentials.
We'll implement the API Key method here.

================================================================================
"""

import logging
from typing import List, AsyncGenerator, Optional

from .base import LLMProvider
from ...models.chat import ChatMessage, MessageRole
from ...config import settings

logger = logging.getLogger(__name__)


class GeminiLLMProvider(LLMProvider):
    """
    LLM provider using Google Gemini API.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key or settings.google_gemini_api_key
        self._model_name = model_name or settings.google_gemini_model
        self._model = None
        
        if not self._api_key:
            logger.warning("Google Gemini API key not configured.")
    
    def _configure(self):
        if self._model is not None:
            return
            
        if not self._api_key:
            raise ValueError("Google Gemini API key not configured.")
            
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
            logger.info(f"Gemini model configured: {self._model_name}")
            
        except Exception as e:
            logger.error(f"Failed to configure Gemini: {e}")
            raise
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        self._configure()
        
        # Convert messages to Gemini format
        # Gemini expects "user" and "model" roles
        # System messages are usually set at initialization or prepended
        history = []
        last_message = None
        
        for msg in messages[:-1]:  # All except last
            role = "user" if msg.role == MessageRole.USER else "model"
            history.append({"role": role, "parts": [msg.content]})
            
        last_content = messages[-1].content
        
        try:
            # Create a chat session
            chat = self._model.start_chat(history=history)
            
            # Send message asynchronously
            response = await chat.send_message_async(
                last_content,
                generation_config=dict(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini chat failed: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        self._configure()
        
        # Format messages
        history = []
        for msg in messages[:-1]:
            role = "user" if msg.role == MessageRole.USER else "model"
            history.append({"role": role, "parts": [msg.content]})
            
        last_content = messages[-1].content
        
        try:
            chat = self._model.start_chat(history=history)
            
            response = await chat.send_message_async(
                last_content,
                stream=True,
                generation_config=dict(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Gemini stream failed: {e}")
            raise

