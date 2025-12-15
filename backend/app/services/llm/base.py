"""
Base LLM Provider - Abstract interface for Large Language Model generation.

================================================================================
THE LLM ABSTRACTION LAYER
================================================================================

Why do we need this?
To switch between Local (llama.cpp), OpenAI (GPT-4), and Google (Gemini)
without rewriting our application logic.

┌────────────────────────────┐      ┌─────────────────────────────┐
│      RAG Service           │      │      LLM Provider (ABC)     │
│                            │      │                             │
│  prompt = "Context: ..."   │────▶ │  + chat(messages)           │
│  response = provider.chat()│      │  + chat_stream(messages)    │
│                            │      └──────────────▲──────────────┘
└────────────────────────────┘                     │
                                                   │ implements
                        ┌──────────────────┬───────┴───────────────┐
                        ▼                  ▼                       ▼
                ┌──────────────┐   ┌──────────────┐        ┌──────────────┐
                │ LocalLLM     │   │ OpenAILLM    │        │ GeminiLLM    │
                │ (llama.cpp)  │   │ (GPT-4)      │        │ (Gemini 1.5) │
                └──────────────┘   └──────────────┘        └──────────────┘

================================================================================
STREAMING IS CRITICAL
================================================================================

LLMs are slow. Waiting 10 seconds for a full answer feels like forever.
Streaming lets us show tokens as they arrive (like ChatGPT).

Our abstraction MUST support streaming natively using Python async generators:

async for chunk in provider.chat_stream(messages):
    yield chunk

================================================================================
"""

import logging
from abc import ABC, abstractmethod
from typing import List, AsyncGenerator, Optional, Dict, Any

from ...models.chat import ChatMessage

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    """
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the name of the model being used."""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a chat conversation and get a complete response string.
        
        Args:
            messages: List of chat messages (system, user, assistant)
            temperature: Creativity (0.0 to 1.0)
            max_tokens: Maximum response length
            
        Returns:
            The complete assistant response text
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Send a chat conversation and stream the response.
        
        Usage:
            async for chunk in provider.chat_stream(messages):
                print(chunk, end="", flush=True)
        
        Args:
            messages: List of chat messages
            temperature: Creativity
            max_tokens: Max length
            
        Yields:
            String chunks of the response as they are generated
        """
        pass
    
    def _format_prompt(self, messages: List[ChatMessage]) -> str:
        """
        Helper to format messages into a single prompt string.
        Useful for local models that expect a specific prompt format
        (like Llama-2 chat template).
        
        Default implementation: Simple join.
        Subclasses should override if they need raw prompt construction.
        """
        prompt = ""
        for msg in messages:
            prompt += f"{msg.role.upper()}: {msg.content}\n\n"
        prompt += "ASSISTANT: "
        return prompt

