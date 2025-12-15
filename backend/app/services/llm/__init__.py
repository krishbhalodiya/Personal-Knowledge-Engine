"""LLM Provider Factory."""

import logging
from typing import Optional, Literal

from .base import LLMProvider
from .local import LocalLLMProvider
from .openai import OpenAILLMProvider
from .gemini import GeminiLLMProvider
from ...config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "LLMProvider",
    "LocalLLMProvider",
    "OpenAILLMProvider",
    "GeminiLLMProvider",
    "get_llm_provider",
]

_llm_provider: Optional[LLMProvider] = None


def get_llm_provider(
    provider_type: Optional[Literal["local", "openai", "gemini"]] = None,
) -> LLMProvider:
    """
    Get the configured LLM provider.
    
    Factory creates and caches the provider instance.
    """
    global _llm_provider
    
    provider_name = provider_type or settings.llm_provider
    
    # Check if we need to switch providers
    if _llm_provider is not None:
        current_type = "local"
        if isinstance(_llm_provider, OpenAILLMProvider):
            current_type = "openai"
        elif isinstance(_llm_provider, GeminiLLMProvider):
            current_type = "gemini"
            
        if current_type == provider_name:
            return _llm_provider
        else:
            logger.info(f"Switching LLM provider from {current_type} to {provider_name}")
    
    logger.info(f"Initializing LLM provider: {provider_name}")
    
    if provider_name == "local":
        _llm_provider = LocalLLMProvider()
    elif provider_name == "openai":
        _llm_provider = OpenAILLMProvider()
    elif provider_name == "gemini":
        _llm_provider = GeminiLLMProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
        
    return _llm_provider

