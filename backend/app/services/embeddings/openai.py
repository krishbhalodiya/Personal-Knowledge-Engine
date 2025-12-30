"""
OpenAI Embedding Provider - Uses OpenAI's API for cloud-based embeddings.
"""

import logging
from typing import List, Optional
import time

from .base import EmbeddingProvider
from ...config import settings

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider using the OpenAI API.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """
        Initialize the OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key. Default from settings/environment.
            model_name: Model to use. Default: "text-embedding-ada-002"
        """
        self._api_key = api_key or settings.openai_api_key
        self._model_name = model_name or settings.openai_embedding_model
        # Use the property that auto-detects dimension based on model
        self._dimension = settings.embedding_dimension
        
        # Lazy load the client
        self._client = None
        
        if not self._api_key:
            logger.warning(
                "OpenAI API key not configured. "
                "Set OPENAI_API_KEY environment variable or in .env file."
            )
        else:
            # Mask the key for logging
            masked_key = self._api_key[:8] + "..." + self._api_key[-4:]
            logger.info(f"OpenAIEmbeddingProvider initialized with key: {masked_key}")
    
    def _get_client(self):
        """
        Get or create the OpenAI client.
        """
        if self._client is not None:
            return self._client
        
        if not self._api_key:
            raise ValueError(
                "OpenAI API key not configured. "
                "Set OPENAI_API_KEY environment variable."
            )
        
        try:
            from openai import OpenAI
            
            self._client = OpenAI(api_key=self._api_key)
            logger.info("OpenAI client created successfully")
            return self._client
            
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension (1536 for ada-002)."""
        return self._dimension
    
    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text using OpenAI API.
        
        Args:
            text: Text to embed
        
        Returns:
            1536-dimensional vector as list of floats
        """
        client = self._get_client()
        
        # Handle empty text
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self._dimension
        
        try:
            # Make API call
            response = client.embeddings.create(
                model=self._model_name,
                input=text,
            )
            
            # Extract embedding from response
            embedding = response.data[0].embedding
            
            # Log token usage for cost tracking
            tokens_used = response.usage.total_tokens
            logger.debug(f"Embedded text ({tokens_used} tokens)")
            
            return embedding
            
        except Exception as e:
            error_str = str(e)
            # Check for quota/rate limit errors
            if "429" in error_str or "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
                logger.error(f"OpenAI quota exceeded or rate limited: {e}")
                raise ValueError(
                    f"OpenAI API quota exceeded. Please check your billing or switch to local embeddings. "
                    f"Error: {error_str}"
                )
            logger.error(f"OpenAI embedding failed: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single API call.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors (same order as input)
        """
        client = self._get_client()
        
        if not texts:
            return []
        
        # Handle empty texts
        processed_texts = []
        empty_indices = set()
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_indices.add(i)
                processed_texts.append("placeholder")
            else:
                processed_texts.append(text)
        
        # Process in batches (OpenAI recommends max 2048, we use 100 for safety)
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(processed_texts), batch_size):
            batch = processed_texts[i:i + batch_size]
            
            try:
                # Make batch API call
                response = client.embeddings.create(
                    model=self._model_name,
                    input=batch,
                )
                
                # Extract embeddings (maintain order)
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Log progress for large batches
                if len(processed_texts) > batch_size:
                    logger.info(f"Processed batch {i//batch_size + 1}/{(len(processed_texts)-1)//batch_size + 1}")
                
                # Small delay between batches to avoid rate limits
                if i + batch_size < len(processed_texts):
                    time.sleep(0.1)
                    
            except Exception as e:
                error_str = str(e)
                # Check for quota/rate limit errors
                if "429" in error_str or "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
                    logger.error(f"OpenAI quota exceeded or rate limited: {e}")
                    raise ValueError(
                        f"OpenAI API quota exceeded. Please check your billing or switch to local embeddings. "
                        f"Error: {error_str}"
                    )
                logger.error(f"OpenAI batch embedding failed at batch {i}: {e}")
                raise
        
        # Replace empty text embeddings with zero vectors
        result = []
        for i, embedding in enumerate(all_embeddings):
            if i in empty_indices:
                result.append([0.0] * self._dimension)
            else:
                result.append(embedding)
        
        logger.info(f"Generated {len(result)} embeddings via OpenAI API")
        return result
    
    def estimate_cost(self, texts: List[str]) -> dict:
        """
        Estimate the cost of embedding these texts.
        
        Args:
            texts: List of texts to estimate
        
        Returns:
            Dict with token estimate and cost estimate
        """
        total_chars = sum(len(text) for text in texts)
        estimated_tokens = total_chars // 4  # Rough estimate
        
        # Ada-002 pricing
        cost_per_1k_tokens = 0.0001
        estimated_cost = (estimated_tokens / 1000) * cost_per_1k_tokens
        
        return {
            "text_count": len(texts),
            "total_characters": total_chars,
            "estimated_tokens": estimated_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "model": self._model_name,
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_openai_provider: Optional[OpenAIEmbeddingProvider] = None


def get_openai_embedding_provider() -> OpenAIEmbeddingProvider:
    """
    Get or create the singleton OpenAIEmbeddingProvider instance.
    
    Note: Will raise error if OPENAI_API_KEY not set when first used.
    """
    global _openai_provider
    if _openai_provider is None:
        _openai_provider = OpenAIEmbeddingProvider()
    return _openai_provider
