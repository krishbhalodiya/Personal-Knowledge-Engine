"""
OpenAI LLM Provider - Uses OpenAI's Chat Completion API.
"""

import logging
from typing import List, AsyncGenerator, Optional

from .base import LLMProvider
from ...models.chat import ChatMessage, MessageRole
from ...config import settings

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """
    LLM provider using OpenAI API.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key or settings.openai_api_key
        self._model_name = model_name or settings.openai_chat_model
        self._client = None
        
        if not self._api_key:
            logger.warning("OpenAI API key not configured for LLM.")
    
    def _get_client(self):
        if self._client is not None:
            return self._client
            
        if not self._api_key:
            raise ValueError("OpenAI API key not configured.")
            
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
            return self._client
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
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
        client = self._get_client()
        
        # Convert Pydantic models to dicts for API
        api_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        
        try:
            response = await client.chat.completions.create(
                model=self._model_name,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
            
        except Exception as e:
            logger.error(f"OpenAI chat failed: {e}")
            raise
    
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        
        api_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]
        
        try:
            stream = await client.chat.completions.create(
                model=self._model_name,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
                    
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}")
            raise
