"""
Embedding Providers - Configurable embedding generation for semantic search.

This module provides a unified interface for generating text embeddings,
regardless of whether you're using local models or cloud APIs.
"""

import logging
from typing import Optional, Literal

from .base import EmbeddingProvider
from .local import LocalEmbeddingProvider, get_local_embedding_provider
from .openai import OpenAIEmbeddingProvider, get_openai_embedding_provider
from ...config import settings

logger = logging.getLogger(__name__)

# Export classes and functions
__all__ = [
    "EmbeddingProvider",
    "LocalEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
    "get_local_embedding_provider",
    "get_openai_embedding_provider",
]

_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider(
    provider_type: Optional[Literal["local", "openai"]] = None,
) -> EmbeddingProvider:
    """
    Get the configured embedding provider.
    
    Args:
        provider_type: Override the configured provider type.
                      If None, uses settings.embedding_provider.
    
    Returns:
        An EmbeddingProvider instance (LocalEmbeddingProvider or OpenAIEmbeddingProvider)
    """
    global _embedding_provider
    
    # Determine which provider to use
    provider_name = provider_type or settings.embedding_provider
    
    logger.debug(f"Getting embedding provider: {provider_name}")
    
    # If we have a cached provider of the right type, return it
    if _embedding_provider is not None:
        current_type = "local" if isinstance(_embedding_provider, LocalEmbeddingProvider) else "openai"
        if current_type == provider_name:
            return _embedding_provider
        else:
            logger.info(f"Switching embedding provider from {current_type} to {provider_name}")
    
    # Create the appropriate provider
    if provider_name == "local":
        _embedding_provider = get_local_embedding_provider()
        logger.info(f"Using local embedding provider: {_embedding_provider.model_name}")
        
    elif provider_name == "openai":
        try:
            _embedding_provider = get_openai_embedding_provider()
            logger.info(f"Using OpenAI embedding provider: {_embedding_provider.model_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI provider: {e}. Falling back to local embeddings.")
            _embedding_provider = get_local_embedding_provider()
            logger.info(f"Fell back to local embedding provider: {_embedding_provider.model_name}")
        
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider_name}. "
            f"Valid options: 'local', 'openai'"
        )
    
    return _embedding_provider


def reset_provider():
    """
    Reset the cached provider.
    """
    global _embedding_provider
    _embedding_provider = None
    logger.info("Embedding provider reset")


def get_provider_info() -> dict:
    """
    Get information about the current embedding provider.
    
    Returns:
        Dict with provider details
    """
    provider = get_embedding_provider()
    
    info = {
        "provider_type": settings.embedding_provider,
        "model_name": provider.model_name,
        "dimension": provider.dimension,
        "class": provider.__class__.__name__,
    }
    
    # Add provider-specific info if available
    if hasattr(provider, 'get_model_info'):
        info["model_info"] = provider.get_model_info()
    
    if isinstance(provider, OpenAIEmbeddingProvider):
        info["api_configured"] = bool(settings.openai_api_key)
    
    return info
