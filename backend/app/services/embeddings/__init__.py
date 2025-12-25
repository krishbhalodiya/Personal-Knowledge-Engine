"""
Embedding Providers - Configurable embedding generation for semantic search.

================================================================================
WHAT IS THIS MODULE?
================================================================================

This module provides a UNIFIED INTERFACE for generating text embeddings,
regardless of whether you're using local models or cloud APIs.

┌─────────────────────────────────────────────────────────────────────────────┐
│                           YOUR APPLICATION                                  │
│                                                                             │
│   from app.services.embeddings import get_embedding_provider                │
│                                                                             │
│   provider = get_embedding_provider()  # Returns configured provider        │
│   vector = provider.embed("Hello")     # Works the same for both!           │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PROVIDER FACTORY                                     │
│                                                                             │
│   if settings.embedding_provider == "local":                                │
│       return LocalEmbeddingProvider()   # sentence-transformers             │
│   else:                                                                     │
│       return OpenAIEmbeddingProvider()  # OpenAI Ada-002                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


================================================================================
HOW TO SWITCH PROVIDERS
================================================================================

Option 1: Environment Variable
──────────────────────────────
# In your .env file or shell:
EMBEDDING_PROVIDER=local    # Use sentence-transformers (free, private)
EMBEDDING_PROVIDER=openai   # Use OpenAI Ada-002 (better quality, costs $)

Option 2: Programmatically
──────────────────────────
from app.services.embeddings import LocalEmbeddingProvider, OpenAIEmbeddingProvider

# Force specific provider
local_provider = LocalEmbeddingProvider()
openai_provider = OpenAIEmbeddingProvider()


================================================================================
COMPARISON: LOCAL VS CLOUD
================================================================================

┌────────────────────┬─────────────────────────┬─────────────────────────┐
│ Aspect             │ Local (MiniLM)          │ Cloud (Ada-002)         │
├────────────────────┼─────────────────────────┼─────────────────────────┤
│ Dimensions         │ 384                     │ 1536                    │
│ Quality            │ Good                    │ Excellent               │
│ Speed              │ ~10ms/text              │ ~100-300ms/text         │
│ Cost               │ Free                    │ $0.0001/1K tokens       │
│ Privacy            │ ✅ Data stays local     │ ❌ Data sent to OpenAI  │
│ Offline            │ ✅ Works offline        │ ❌ Needs internet       │
│ First load         │ ~2-5 seconds            │ Instant                 │
│ Max context        │ 512 tokens              │ 8191 tokens             │
│ Languages          │ Good for English        │ Excellent multilingual  │
└────────────────────┴─────────────────────────┴─────────────────────────┘


================================================================================
USAGE EXAMPLES
================================================================================

# Basic usage (uses configured provider)
from app.services.embeddings import get_embedding_provider

provider = get_embedding_provider()
vector = provider.embed("What is machine learning?")
print(f"Vector has {len(vector)} dimensions")

# Batch embedding (much faster for multiple texts)
texts = ["Document 1", "Document 2", "Document 3"]
vectors = provider.embed_batch(texts)

# Check which provider is active
print(f"Using: {provider}")  # e.g., "LocalEmbeddingProvider(model=all-MiniLM-L6-v2, dim=384)"

# Get provider info
if hasattr(provider, 'get_model_info'):
    print(provider.get_model_info())


================================================================================
IMPORTANT NOTES
================================================================================

1. VECTOR DIMENSIONS MUST BE CONSISTENT
   ─────────────────────────────────────
   If you index documents with local provider (384 dims), you CANNOT
   search with OpenAI provider (1536 dims). The vector database will fail.
   
   Solution: Re-index all documents when switching providers.

2. FIRST LOAD IS SLOW (Local)
   ──────────────────────────
   Local provider downloads the model (~90MB) on first use.
   Subsequent uses are fast (model cached in ~/.cache/huggingface/).

3. API KEY REQUIRED (OpenAI)
   ─────────────────────────
   Set OPENAI_API_KEY in environment before using OpenAI provider.
   Provider will raise error if key is missing.


================================================================================
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
    # Base class
    "EmbeddingProvider",
    
    # Implementations
    "LocalEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    
    # Factory functions
    "get_embedding_provider",
    "get_local_embedding_provider",
    "get_openai_embedding_provider",
]


# =============================================================================
# PROVIDER FACTORY
# =============================================================================

# Singleton for the configured provider
_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider(
    provider_type: Optional[Literal["local", "openai"]] = None,
) -> EmbeddingProvider:
    """
    Get the configured embedding provider.
    
    FACTORY PATTERN:
    ================
    
    This function is a FACTORY - it creates and returns the right type
    of provider based on configuration.
    
    ┌─────────────────────────────────────────────────────────────┐
    │  get_embedding_provider()                                   │
    │                                                             │
    │  1. Check settings.embedding_provider                       │
    │     └─> "local" or "openai"                                │
    │                                                             │
    │  2. Create appropriate provider                             │
    │     ├─> LocalEmbeddingProvider()  if "local"               │
    │     └─> OpenAIEmbeddingProvider() if "openai"              │
    │                                                             │
    │  3. Cache as singleton (reuse same instance)               │
    │                                                             │
    │  4. Return provider                                         │
    └─────────────────────────────────────────────────────────────┘
    
    Args:
        provider_type: Override the configured provider type.
                      If None, uses settings.embedding_provider.
    
    Returns:
        An EmbeddingProvider instance (LocalEmbeddingProvider or OpenAIEmbeddingProvider)
    
    Example:
        # Use configured provider
        provider = get_embedding_provider()
        
        # Force specific provider
        local = get_embedding_provider("local")
        cloud = get_embedding_provider("openai")
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
    
    Useful for:
    - Testing (create fresh provider)
    - Switching providers at runtime
    - Clearing memory
    """
    global _embedding_provider
    _embedding_provider = None
    logger.info("Embedding provider reset")


def get_provider_info() -> dict:
    """
    Get information about the current embedding provider.
    
    Useful for:
    - Displaying in UI
    - Debugging
    - API health checks
    
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

