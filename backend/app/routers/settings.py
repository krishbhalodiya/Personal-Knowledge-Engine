"""
Settings API Routes - View and manage configuration.

ENDPOINTS:
==========
GET  /api/settings              - Get current settings
GET  /api/settings/providers    - Get available provider information
POST /api/settings/test-embedding - Test embedding generation

WHY A SETTINGS API?
===================

1. VISIBILITY: Users can see which provider is active
2. DEBUGGING: Check if embeddings are working
3. FRONTEND: Settings UI can read current config
4. MONITORING: Track embedding costs and performance

NOTE ON CHANGING SETTINGS:
==========================

Changing embedding provider at runtime is DANGEROUS because:
- Existing documents have embeddings with dimension X
- New provider might have dimension Y
- Search will fail if dimensions don't match

To change providers, you should:
1. Stop the server
2. Delete the ChromaDB data
3. Update the .env file
4. Restart and re-index all documents

This API lets you VIEW settings, not CHANGE them (for safety).
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import settings
from ..services.embeddings import get_embedding_provider, get_provider_info as get_emb_info
from ..services.llm import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class ProviderInfo(BaseModel):
    """Information about an embedding provider."""
    name: str
    type: str  # "local" or "openai"
    model: str
    dimension: int
    description: str


class CurrentSettings(BaseModel):
    """Current application settings."""
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    llm_provider: str
    chunk_size: int
    chunk_overlap: int
    search_top_k: int


class EmbeddingTestResult(BaseModel):
    """Result of an embedding test."""
    success: bool
    provider: str
    model: str
    dimension: int
    time_ms: float
    sample_values: list[float]  # First few values of the embedding
    error: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=CurrentSettings)
async def get_settings():
    """
    Get current application settings.
    
    Returns the active configuration including:
    - Embedding provider (local or openai)
    - Model names
    - Chunking parameters
    - Search settings
    
    EXAMPLE RESPONSE:
    ```json
    {
        "embedding_provider": "local",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dimension": 384,
        "llm_provider": "local",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "search_top_k": 5
    }
    ```
    """
    return CurrentSettings(
        embedding_provider=settings.embedding_provider,
        embedding_model=(
            settings.local_embedding_model 
            if settings.embedding_provider == "local" 
            else settings.openai_embedding_model
        ),
        embedding_dimension=settings.embedding_dimension,
        llm_provider=settings.llm_provider,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        search_top_k=settings.search_top_k,
    )


@router.get("/providers")
async def get_providers():
    """
    Get information about available embedding and LLM providers.
    """
    # Get current embedding provider info
    emb_info = get_emb_info()
    
    # Embedding Providers
    embedding_providers = {
        "local": {
            "name": "Local (sentence-transformers)",
            "type": "local",
            "model": settings.local_embedding_model,
            "dimension": settings.local_embedding_dimension,
            "status": "active" if settings.embedding_provider == "local" else "available",
        },
        "openai": {
            "name": "OpenAI",
            "type": "openai",
            "model": settings.openai_embedding_model,
            "dimension": settings.openai_embedding_dimension,
            "status": (
                "active" if settings.embedding_provider == "openai"
                else "api_key_missing" if not settings.openai_api_key
                else "available"
            ),
        },
    }
    
    # LLM Providers
    llm_providers = {
        "local": {
            "name": "Local (llama.cpp)",
            "type": "local",
            "model": settings.llm_model_path or "Not configured",
            "status": (
                "active" if settings.llm_provider == "local"
                else "model_missing" if not settings.llm_model_path
                else "available"
            ),
        },
        "openai": {
            "name": "OpenAI",
            "type": "openai",
            "model": settings.openai_chat_model,
            "status": (
                "active" if settings.llm_provider == "openai"
                else "api_key_missing" if not settings.openai_api_key
                else "available"
            ),
        },
        "gemini": {
            "name": "Google Gemini",
            "type": "gemini",
            "model": settings.google_gemini_model,
            "status": (
                "active" if settings.llm_provider == "gemini"
                else "api_key_missing" if not settings.google_gemini_api_key
                else "available"
            ),
        }
    }
    
    return {
        "embedding": {
            "current": settings.embedding_provider,
            "info": emb_info,
            "options": embedding_providers
        },
        "llm": {
            "current": settings.llm_provider,
            "options": llm_providers
        }
    }


@router.post("/test-embedding", response_model=EmbeddingTestResult)
async def test_embedding(
    text: str = Query(
        "Hello, this is a test of the embedding system.",
        description="Text to embed for testing",
    ),
):
    """
    Test the embedding provider with a sample text.
    
    This endpoint:
    1. Gets the current embedding provider
    2. Generates an embedding for the test text
    3. Returns timing and dimension info
    
    Useful for:
    - Verifying the provider is working
    - Checking embedding dimensions
    - Measuring latency
    
    EXAMPLE:
    ```bash
    curl -X POST "http://localhost:8000/api/settings/test-embedding?text=Hello%20world"
    ```
    
    RESPONSE:
    ```json
    {
        "success": true,
        "provider": "local",
        "model": "all-MiniLM-L6-v2",
        "dimension": 384,
        "time_ms": 15.3,
        "sample_values": [0.0234, -0.0567, 0.0891, ...]
    }
    ```
    """
    logger.info(f"Testing embedding with text: {text[:50]}...")
    
    try:
        # Get the provider
        provider = get_embedding_provider()
        
        # Time the embedding
        start_time = time.time()
        embedding = provider.embed(text)
        elapsed_ms = (time.time() - start_time) * 1000
        
        return EmbeddingTestResult(
            success=True,
            provider=settings.embedding_provider,
            model=provider.model_name,
            dimension=len(embedding),
            time_ms=round(elapsed_ms, 2),
            sample_values=embedding[:10],  # First 10 values
        )
        
    except Exception as e:
        logger.error(f"Embedding test failed: {e}")
        return EmbeddingTestResult(
            success=False,
            provider=settings.embedding_provider,
            model="unknown",
            dimension=0,
            time_ms=0,
            sample_values=[],
            error=str(e),
        )


@router.get("/health")
async def settings_health():
    """
    Quick health check for the settings/provider system.
    
    Returns status of:
    - Embedding provider
    - OpenAI API key (if configured)
    - Model availability
    """
    health = {
        "status": "healthy",
        "embedding_provider": settings.embedding_provider,
        "openai_configured": bool(settings.openai_api_key),
    }
    
    # Try to verify provider is working
    try:
        provider = get_embedding_provider()
        health["provider_loaded"] = True
        health["model_name"] = provider.model_name
        health["dimension"] = provider.dimension
    except Exception as e:
        health["status"] = "degraded"
        health["provider_loaded"] = False
        health["error"] = str(e)
    
    return health

