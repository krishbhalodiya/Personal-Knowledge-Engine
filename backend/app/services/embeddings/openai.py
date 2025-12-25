"""
OpenAI Embedding Provider - Uses OpenAI's API for cloud-based embeddings.

================================================================================
HOW OPENAI EMBEDDINGS API WORKS
================================================================================

When you call OpenAI's embedding API, here's what happens:

YOUR APP                                    OPENAI SERVERS
────────                                    ──────────────

1. PREPARE REQUEST
   ┌────────────────────────────────────┐
   │ {                                  │
   │   "model": "text-embedding-ada-002"│
   │   "input": "Machine learning..."   │
   │ }                                  │
   └────────────────────────────────────┘
                    │
                    │ HTTPS POST
                    │ api.openai.com/v1/embeddings
                    │ Authorization: Bearer sk-...
                    │
                    ▼
2. OPENAI PROCESSING
   ┌────────────────────────────────────────────────────────┐
   │                                                        │
   │  ┌──────────────────┐                                 │
   │  │ Load Balancer    │  Distributes across GPU farms   │
   │  └────────┬─────────┘                                 │
   │           │                                           │
   │           ▼                                           │
   │  ┌──────────────────┐                                 │
   │  │ Tokenizer        │  Text → tokens (cl100k_base)    │
   │  └────────┬─────────┘                                 │
   │           │                                           │
   │           ▼                                           │
   │  ┌──────────────────┐                                 │
   │  │ Ada-002 Model    │  8192 token context            │
   │  │ (Transformer)    │  1536-dim output               │
   │  │                  │  Runs on NVIDIA A100 GPUs      │
   │  └────────┬─────────┘                                 │
   │           │                                           │
   │           ▼                                           │
   │  ┌──────────────────┐                                 │
   │  │ Response Builder │  Package embedding + metadata   │
   │  └──────────────────┘                                 │
   │                                                        │
   └────────────────────────────────────────────────────────┘
                    │
                    │ HTTPS Response
                    │
                    ▼
3. RECEIVE RESPONSE
   ┌────────────────────────────────────────────────────────┐
   │ {                                                      │
   │   "object": "list",                                    │
   │   "data": [{                                           │
   │     "object": "embedding",                             │
   │     "index": 0,                                        │
   │     "embedding": [0.0023, -0.0092, 0.0156, ...]       │
   │   }],                                                  │
   │   "model": "text-embedding-ada-002",                   │
   │   "usage": {                                           │
   │     "prompt_tokens": 5,                                │
   │     "total_tokens": 5                                  │
   │   }                                                    │
   │ }                                                      │
   └────────────────────────────────────────────────────────┘


================================================================================
WHAT IS ADA-002?
================================================================================

Ada-002 is OpenAI's second-generation embedding model:

ARCHITECTURE (Speculated, OpenAI doesn't publish details):
- Based on GPT-3 architecture (transformer)
- Optimized for embedding generation (not text generation)
- Uses special pooling to produce fixed-size output
- Trained on massive dataset of text pairs

CAPABILITIES:
- Context window: 8191 tokens (~32,000 characters)
- Output dimension: 1536 (4x larger than MiniLM)
- Languages: Excellent for English, good for 100+ languages
- Quality: State-of-the-art for many benchmarks

PRICING (as of 2024):
- $0.0001 per 1,000 tokens
- ~4 chars = 1 token
- 1 million words ≈ $0.10

Example cost:
- 1000 documents × 500 words each = 500,000 words
- 500,000 words × 1.3 tokens/word = 650,000 tokens
- Cost = $0.065 (about 6 cents!)


================================================================================
BATCHING IN OPENAI API
================================================================================

OpenAI's API is optimized for batch requests:

SINGLE REQUESTS (Inefficient):
─────────────────────────────
Request 1: "Text 1" → Response (100ms)
Request 2: "Text 2" → Response (100ms)
Request 3: "Text 3" → Response (100ms)
Total: 300ms + connection overhead

BATCH REQUEST (Efficient):
──────────────────────────
Request: ["Text 1", "Text 2", "Text 3"] → Response (150ms)
Total: 150ms, 3 embeddings

OpenAI processes batches in parallel on their GPUs!

RATE LIMITS:
- 3,000 requests per minute
- 1,000,000 tokens per minute
- Batch up to 2048 texts per request


================================================================================
SECURITY CONSIDERATIONS
================================================================================

When using OpenAI's API:

DATA SENT TO OPENAI:
- Your API key (in header)
- The text you want to embed
- Your IP address

DATA OPENAI RETURNS:
- The embedding vector
- Token count used

PRIVACY IMPLICATIONS:
⚠️ Your document content is sent to OpenAI's servers
⚠️ OpenAI may log requests for abuse monitoring
⚠️ Data travels over the internet (HTTPS encrypted)

OpenAI's data policy:
- API data NOT used to train models (as of 2024)
- 30-day retention for abuse monitoring
- Enterprise plans offer zero retention

For sensitive data, consider:
- Using local embeddings (MiniLM)
- Self-hosted models
- Azure OpenAI with data residency


================================================================================
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
    
    ADVANTAGES:
    ===========
    ✅ Highest quality embeddings
    ✅ No local compute needed
    ✅ Fast (OpenAI's GPUs are powerful)
    ✅ Handles long texts (8191 tokens)
    ✅ Multilingual support
    
    DISADVANTAGES:
    ==============
    ❌ Costs money ($0.0001/1K tokens)
    ❌ Requires internet connection
    ❌ Data sent to OpenAI (privacy concern)
    ❌ Rate limits
    ❌ API can be slow/unavailable
    
    API KEY SETUP:
    ==============
    1. Go to platform.openai.com
    2. Create account / sign in
    3. Go to API Keys section
    4. Create new secret key
    5. Set OPENAI_API_KEY environment variable
    
    USAGE:
    ======
    # Set API key in environment or .env file
    # OPENAI_API_KEY=sk-...
    
    provider = OpenAIEmbeddingProvider()
    vector = provider.embed("Hello world")  # Returns 1536-dim vector
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
        
        WHY LAZY LOADING?
        =================
        - Importing 'openai' takes time
        - Client creation validates API key
        - Fail fast if key is invalid
        - But only when actually used
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
        
        API CALL BREAKDOWN:
        ===================
        
        1. Validate input
        2. Create API request
        3. Send to api.openai.com/v1/embeddings
        4. Parse response
        5. Return embedding vector
        
        WHAT THE API RETURNS:
        =====================
        {
            "object": "list",
            "data": [{
                "object": "embedding",
                "index": 0,
                "embedding": [0.0023, -0.0092, ...]  # 1536 floats
            }],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 5, "total_tokens": 5}
        }
        
        Args:
            text: Text to embed
        
        Returns:
            1536-dimensional vector as list of floats
        
        Raises:
            ValueError: If API key not configured
            openai.APIError: If API call fails
        """
        client = self._get_client()
        
        # Handle empty text
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self._dimension
        
        try:
            # Make API call
            # The model parameter specifies which embedding model to use
            # Input can be a string or list of strings
            response = client.embeddings.create(
                model=self._model_name,
                input=text,
            )
            
            # Extract embedding from response
            # response.data is a list of embedding objects
            # We sent one text, so we get one embedding at index 0
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
        
        BATCH API CALL:
        ===============
        
        Instead of:
            POST /embeddings {"input": "text1"}
            POST /embeddings {"input": "text2"}
            POST /embeddings {"input": "text3"}
        
        We send:
            POST /embeddings {"input": ["text1", "text2", "text3"]}
        
        OpenAI processes all texts in parallel on their GPUs!
        
        BATCH LIMITS:
        =============
        - Max 2048 texts per request
        - Max 8191 tokens per text
        - We chunk into batches of 100 for safety
        
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
                # Response data is in same order as input
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
        
        COST CALCULATION:
        =================
        
        Ada-002 pricing: $0.0001 per 1,000 tokens
        
        Token estimation:
        - Average English word ≈ 1.3 tokens
        - We estimate: chars / 4 ≈ tokens
        
        Example:
        - 1000 documents × 1000 chars = 1,000,000 chars
        - 1,000,000 / 4 = 250,000 tokens
        - Cost = 250,000 / 1000 × $0.0001 = $0.025
        
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

