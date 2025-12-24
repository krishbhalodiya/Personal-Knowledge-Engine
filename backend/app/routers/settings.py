import logging
import time
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from ..config import settings
from ..services.embeddings import get_embedding_provider, get_provider_info as get_emb_info
from ..services.llm import get_llm_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderInfo(BaseModel):
    name: str
    type: str
    model: str
    dimension: int
    description: str


class CurrentSettings(BaseModel):
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    llm_provider: str
    chunk_size: int
    chunk_overlap: int
    search_top_k: int


class EmbeddingTestResult(BaseModel):
    success: bool
    provider: str
    model: str
    dimension: int
    time_ms: float
    sample_values: list[float]
    error: Optional[str] = None


@router.get("", response_model=CurrentSettings)
async def get_settings():
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
    emb_info = get_emb_info()
    
    embedding_models = {
        "text-embedding-3-small": {"dimension": 1536, "cost": "cheap"},
        "text-embedding-3-large": {"dimension": 3072, "cost": "expensive"},
        "text-embedding-ada-002": {"dimension": 1536, "cost": "cheap"},
    }
    
    current_model = settings.openai_embedding_model
    current_dim = embedding_models.get(current_model, {}).get("dimension", 1536)
    
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
            "model": current_model,
            "dimension": current_dim,
            "status": (
                "active" if settings.embedding_provider == "openai"
                else "api_key_missing" if not settings.openai_api_key
                else "available"
            ),
            "available_models": embedding_models,
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


@router.post("/embedding/model/switch")
async def switch_embedding_model(
    model: Literal["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"] = Body(..., embed=True),
):
    if settings.embedding_provider != "openai":
        raise HTTPException(status_code=400, detail="Can only switch models when using OpenAI provider")
    
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    
    object.__setattr__(settings, 'openai_embedding_model', model)
    
    if "3-large" in model:
        object.__setattr__(settings, 'openai_embedding_dimension', 3072)
    else:
        object.__setattr__(settings, 'openai_embedding_dimension', 1536)
    
    logger.info(f"Switched embedding model to {model}")
    
    return {
        "message": f"Embedding model switched to {model}",
        "model": model,
        "dimension": settings.openai_embedding_dimension,
        "warning": "⚠️ Changing embedding models requires re-indexing all documents!"
    }


@router.post("/test-embedding", response_model=EmbeddingTestResult)
async def test_embedding(
    text: str = Query("Hello, this is a test of the embedding system.", description="Text to embed for testing"),
):
    logger.info(f"Testing embedding with text: {text[:50]}...")
    
    try:
        provider = get_embedding_provider()
        start_time = time.time()
        embedding = provider.embed(text)
        elapsed_ms = (time.time() - start_time) * 1000
        
        return EmbeddingTestResult(
            success=True,
            provider=settings.embedding_provider,
            model=provider.model_name,
            dimension=len(embedding),
            time_ms=round(elapsed_ms, 2),
            sample_values=embedding[:10],
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


class SwitchLLMRequest(BaseModel):
    provider: str


class SwitchLLMResponse(BaseModel):
    success: bool
    previous_provider: str
    current_provider: str
    model: str
    message: str


@router.post("/llm/switch", response_model=SwitchLLMResponse)
async def switch_llm_provider(request: SwitchLLMRequest):
    from ..services.llm import get_llm_provider
    import app.services.llm as llm_module
    
    valid_providers = ["local", "openai", "gemini"]
    if request.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Must be one of: {valid_providers}")
    
    previous_provider = settings.llm_provider
    
    if request.provider == "openai" and not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    if request.provider == "gemini" and not settings.google_gemini_api_key:
        raise HTTPException(status_code=400, detail="Gemini API key not configured")
    if request.provider == "local" and not settings.llm_model_path:
        raise HTTPException(status_code=400, detail="Local LLM model not configured")
    
    try:
        llm_module._llm_provider = None
        object.__setattr__(settings, 'llm_provider', request.provider)
        new_provider = get_llm_provider(request.provider)
        
        logger.info(f"Switched LLM provider from {previous_provider} to {request.provider}")
        
        return SwitchLLMResponse(
            success=True,
            previous_provider=previous_provider,
            current_provider=request.provider,
            model=new_provider.model_name,
            message=f"Successfully switched to {request.provider}"
        )
    except Exception as e:
        object.__setattr__(settings, 'llm_provider', previous_provider)
        llm_module._llm_provider = None
        get_llm_provider(previous_provider)
        logger.error(f"Failed to switch LLM provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def settings_health():
    health = {
        "status": "healthy",
        "embedding_provider": settings.embedding_provider,
        "openai_configured": bool(settings.openai_api_key),
    }
    
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

