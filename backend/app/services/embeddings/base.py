"""
Base Embedding Provider - Abstract interface for embedding generation.

================================================================================
WHAT IS THIS FILE?
================================================================================

This file defines the ABSTRACT BASE CLASS for embedding providers.
Think of it as a CONTRACT that all embedding implementations must follow.

WHY DO WE NEED THIS?
====================

Imagine you're building a house with interchangeable parts:
- The blueprint says "there should be a door here"
- You can install a wooden door, metal door, or glass door
- All doors must: open(), close(), lock()
- The house doesn't care WHICH door, just that it follows the blueprint

Similarly:
- Our system says "I need embeddings"
- We can use LocalProvider (MiniLM) or OpenAIProvider (Ada-002)
- All providers must: embed(), embed_batch(), get dimension
- The rest of the code doesn't care WHICH provider

THIS IS THE "DOOR BLUEPRINT" FOR EMBEDDING PROVIDERS.

================================================================================
DESIGN PATTERN: STRATEGY PATTERN
================================================================================

We're using the Strategy Pattern here:

┌─────────────────────────────────────────────────────────────────┐
│                        Context                                  │
│  (IngestionService, SearchService)                             │
│                                                                 │
│  Uses: EmbeddingProvider                                       │
│  Doesn't know: Which specific provider                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  EmbeddingProvider (Abstract)                   │
│                                                                 │
│  Defines the interface:                                         │
│  - embed(text) → List[float]                                   │
│  - embed_batch(texts) → List[List[float]]                      │
│  - dimension → int                                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│   LocalEmbedding      │       │   OpenAIEmbedding     │
│   Provider            │       │   Provider            │
│                       │       │                       │
│   Uses:               │       │   Uses:               │
│   sentence-transformers│      │   OpenAI API          │
│                       │       │                       │
│   Runs on YOUR CPU    │       │   Runs on CLOUD       │
└───────────────────────┘       └───────────────────────┘

Benefits:
1. Add new providers without changing existing code
2. Switch providers at runtime via configuration
3. Test with mock providers
4. Each provider handles its own complexity

================================================================================
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    All embedding providers MUST implement this interface.
    This ensures consistent behavior across local and cloud providers.
    
    WHAT EACH METHOD DOES:
    ======================
    
    embed(text):
        Convert a single piece of text into a vector.
        
        Input:  "Machine learning is fascinating"
        Output: [0.234, -0.567, 0.891, ...] (list of floats)
        
        The output vector captures the MEANING of the text.
        Similar texts will have similar vectors.
    
    embed_batch(texts):
        Convert multiple texts into vectors efficiently.
        
        Input:  ["Text 1", "Text 2", "Text 3"]
        Output: [[...], [...], [...]] (list of vectors)
        
        WHY BATCH?
        - GPU processes batches more efficiently
        - API calls have overhead; batching reduces calls
        - Can be 10-100x faster than calling embed() repeatedly
    
    dimension:
        The size of the output vectors.
        
        - MiniLM: 384 dimensions
        - Ada-002: 1536 dimensions
        
        IMPORTANT: All vectors in the same index must have the same dimension!
        You can't mix 384-dim and 1536-dim vectors in one ChromaDB collection.
    
    USAGE EXAMPLE:
    ==============
    
    # Get the configured provider (could be local or cloud)
    provider = get_embedding_provider()
    
    # Embed a single text
    vector = provider.embed("What is machine learning?")
    
    # Embed multiple texts efficiently
    vectors = provider.embed_batch([
        "Python programming",
        "JavaScript frameworks",
        "Database design"
    ])
    
    # Check the dimension
    print(f"Vectors have {provider.dimension} dimensions")
    """
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this provider.
        
        WHAT IS DIMENSION?
        ==================
        
        The dimension is the "size" of the embedding vector.
        
        Think of it like coordinates:
        - 2D space: (x, y) → 2 dimensions
        - 3D space: (x, y, z) → 3 dimensions
        - Embedding: (x1, x2, ..., x384) → 384 dimensions
        
        WHY DIFFERENT DIMENSIONS?
        =========================
        
        More dimensions = more "space" to capture meaning
        
        | Model      | Dimensions | Quality | Speed  |
        |------------|------------|---------|--------|
        | MiniLM     | 384        | Good    | Fast   |
        | Ada-002    | 1536       | Best    | Medium |
        | GPT-4 emb  | 3072       | Best+   | Slower |
        
        Trade-off: More dimensions = better quality but more storage/compute.
        384 is a sweet spot for most use cases.
        
        IMPORTANT: Don't mix dimensions in the same vector store!
        """
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Used for logging and debugging.
        Examples: "all-MiniLM-L6-v2", "text-embedding-ada-002"
        """
        pass
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text.
        
        HOW IT WORKS (Conceptually):
        ============================
        
        1. TOKENIZE: Split text into tokens
           "Hello world" → ["Hello", "world"]
        
        2. ENCODE: Convert tokens to numbers
           ["Hello", "world"] → [15496, 995]
        
        3. TRANSFORM: Pass through neural network
           [15496, 995] → [[0.1, 0.2, ...], [0.3, 0.4, ...]]
        
        4. POOL: Combine into single vector
           [[...], [...]] → [0.234, -0.567, ...]
        
        Args:
            text: The text to embed. Can be a word, sentence, or paragraph.
                  Longer texts are truncated (typically at 512 tokens).
        
        Returns:
            A list of floats representing the embedding vector.
            Length equals self.dimension.
        
        Example:
            >>> provider = LocalEmbeddingProvider()
            >>> vector = provider.embed("Hello world")
            >>> len(vector)
            384
            >>> vector[:3]
            [0.234, -0.567, 0.891]
        """
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        WHY BATCH PROCESSING?
        =====================
        
        Single embeddings (BAD for many texts):
        ┌──────────────────────────────────────────────┐
        │  for text in 1000_texts:                     │
        │      embed(text)  # 1000 separate operations │
        │                                              │
        │  Time: ~10 seconds (10ms × 1000)             │
        └──────────────────────────────────────────────┘
        
        Batch embeddings (GOOD):
        ┌──────────────────────────────────────────────┐
        │  embed_batch(1000_texts)  # 1 operation      │
        │                                              │
        │  GPU processes all at once                   │
        │  Time: ~0.5 seconds                          │
        └──────────────────────────────────────────────┘
        
        For API calls (OpenAI), batching also reduces:
        - Network round trips
        - API rate limiting issues
        - Total latency
        
        Args:
            texts: List of texts to embed.
        
        Returns:
            List of embedding vectors, one per input text.
            Order is preserved (texts[i] → embeddings[i]).
        
        Example:
            >>> provider = LocalEmbeddingProvider()
            >>> vectors = provider.embed_batch(["Hello", "World"])
            >>> len(vectors)
            2
            >>> len(vectors[0])
            384
        """
        pass
    
    def embed_with_retry(
        self,
        text: str,
        max_retries: int = 3,
    ) -> Optional[List[float]]:
        """
        Embed with automatic retry on failure.
        
        WHY RETRY?
        ==========
        - Network failures (for cloud providers)
        - Temporary API errors
        - Rate limiting
        
        Uses exponential backoff: wait 1s, 2s, 4s between retries.
        
        This is a DEFAULT IMPLEMENTATION that subclasses can override.
        """
        import time
        
        for attempt in range(max_retries):
            try:
                return self.embed(text)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to embed after {max_retries} attempts: {e}")
                    raise
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Embed failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
        
        return None
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}(model={self.model_name}, dim={self.dimension})"

