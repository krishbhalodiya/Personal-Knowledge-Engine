"""
Local Embedding Provider - Uses sentence-transformers for local embedding generation.

================================================================================
WHAT IS SENTENCE-TRANSFORMERS?
================================================================================

Sentence-Transformers is a Python library that provides pre-trained models
for generating embeddings. The models run LOCALLY on your machine.

KEY POINTS:
- Based on transformer architecture (like BERT, but optimized for embeddings)
- Pre-trained on millions of sentence pairs
- Produces fixed-size vectors regardless of input length
- FREE to use, no API costs
- Works OFFLINE

================================================================================
HOW THE EMBEDDING MODEL WORKS (MiniLM-L6-v2)
================================================================================

Step 1: TOKENIZATION
────────────────────
The tokenizer converts text into tokens (subwords):

"Machine learning is cool"
    ↓
["Machine", "learning", "is", "cool"]
    ↓
[3456, 2789, 1045, 4521]  (token IDs)

Special tokens are added:
[CLS] Machine learning is cool [SEP]
[101, 3456, 2789, 1045, 4521, 102]

- [CLS] = Classification token (used for pooling)
- [SEP] = Separator token (marks end)


Step 2: EMBEDDING LOOKUP
────────────────────────
Each token ID maps to a 384-dimensional vector:

Token 3456 → [0.1, 0.2, -0.3, ...]  (384 dims)
Token 2789 → [0.4, -0.1, 0.2, ...]  (384 dims)
...

This creates a matrix: (num_tokens × 384)


Step 3: TRANSFORMER LAYERS
──────────────────────────
The model has 6 transformer layers. Each layer:

┌─────────────────────────────────────────────────────────────┐
│                    Transformer Layer                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SELF-ATTENTION                                     │   │
│  │                                                     │   │
│  │  Each token "looks at" all other tokens             │   │
│  │  and decides how much to "pay attention" to each    │   │
│  │                                                     │   │
│  │  "Machine" attends to: "learning" (high), "is" (low)│   │
│  │  "learning" attends to: "Machine" (high)            │   │
│  │                                                     │   │
│  │  This captures RELATIONSHIPS between words          │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  FEED-FORWARD NETWORK                               │   │
│  │                                                     │   │
│  │  Two linear layers with ReLU activation             │   │
│  │  Adds non-linearity for complex patterns            │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  Output: Updated token embeddings with context             │
└─────────────────────────────────────────────────────────────┘

After 6 layers, each token's embedding contains information
from ALL other tokens in the sentence (contextual embeddings).


Step 4: POOLING
───────────────
We need ONE vector for the whole sentence, not per-token vectors.

Mean Pooling (what MiniLM uses):
┌─────────────────────────────────────────────────────────────┐
│  Token embeddings after transformer:                        │
│                                                             │
│  [CLS]:      [0.1, 0.2, ...]                               │
│  Machine:    [0.3, 0.4, ...]                               │
│  learning:   [0.5, 0.6, ...]                               │
│  is:         [0.2, 0.1, ...]                               │
│  cool:       [0.4, 0.3, ...]                               │
│  [SEP]:      [0.1, 0.1, ...]                               │
│                                                             │
│  Mean Pooling = Average of all token vectors               │
│                                                             │
│  Final: [(0.1+0.3+0.5+0.2+0.4+0.1)/6, ...]                │
│       = [0.267, ...]                                       │
│                                                             │
│  Result: Single 384-dim vector for the sentence            │
└─────────────────────────────────────────────────────────────┘


Step 5: NORMALIZATION (Optional)
────────────────────────────────
Vectors are often L2-normalized (length = 1):

vector = vector / ||vector||

This makes cosine similarity = dot product (faster computation).


================================================================================
WHY MiniLM-L6-v2 SPECIFICALLY?
================================================================================

| Model               | Params | Layers | Dim  | Speed | Quality |
|---------------------|--------|--------|------|-------|---------|
| BERT-base           | 110M   | 12     | 768  | Slow  | Good    |
| all-mpnet-base-v2   | 110M   | 12     | 768  | Slow  | Best    |
| all-MiniLM-L6-v2    | 22M    | 6      | 384  | Fast  | Good    | ← OUR CHOICE
| all-MiniLM-L12-v2   | 33M    | 12     | 384  | Med   | Better  |

MiniLM-L6-v2 is the sweet spot:
- 5x smaller than BERT
- 3x faster inference
- ~95% of the quality
- Perfect for personal knowledge base scale

================================================================================
"""

import logging
from typing import List, Optional
import numpy as np

from .base import EmbeddingProvider
from ...config import settings

logger = logging.getLogger(__name__)


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.
    
    ADVANTAGES:
    ===========
    ✅ Free (no API costs)
    ✅ Fast (runs on your CPU/GPU)
    ✅ Private (data never leaves your machine)
    ✅ Offline (works without internet)
    ✅ Consistent (same input = same output)
    
    DISADVANTAGES:
    ==============
    ❌ Lower quality than OpenAI's Ada-002
    ❌ Uses local compute resources (CPU/RAM)
    ❌ First load is slow (downloads model)
    
    MODEL LOADING:
    ==============
    The model is loaded LAZILY (on first use) because:
    1. Importing sentence-transformers is slow
    2. Model download happens on first load
    3. App starts faster if model isn't needed immediately
    
    USAGE:
    ======
    provider = LocalEmbeddingProvider()
    
    # First call loads the model (~2-5 seconds, downloads if needed)
    vector = provider.embed("Hello world")
    
    # Subsequent calls are fast (~10ms)
    vector2 = provider.embed("Another text")
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the local embedding provider.
        
        Args:
            model_name: HuggingFace model name. Default from settings.
                       Examples:
                       - "sentence-transformers/all-MiniLM-L6-v2" (fast, good)
                       - "sentence-transformers/all-mpnet-base-v2" (slow, best)
        """
        self._model_name = model_name or settings.local_embedding_model
        self._dimension = settings.local_embedding_dimension
        
        # Lazy loading: model loaded on first use
        self._model = None
        
        logger.info(f"LocalEmbeddingProvider initialized with model: {self._model_name}")
    
    def _load_model(self):
        """
        Load the sentence-transformers model.
        
        WHAT HAPPENS DURING LOADING:
        ============================
        
        1. Check if model exists in cache (~/.cache/huggingface/)
        2. If not cached, download from HuggingFace Hub (~90MB)
        3. Load model weights into memory
        4. Move to GPU if available (we use CPU by default)
        
        FIRST LOAD:
        - Downloads model: ~30 seconds (depends on internet)
        - Loads into memory: ~2-3 seconds
        
        SUBSEQUENT LOADS:
        - From cache: ~2-3 seconds
        
        MEMORY USAGE:
        - MiniLM-L6-v2: ~100MB RAM
        - Larger models: 300-500MB RAM
        """
        if self._model is not None:
            return
        
        logger.info(f"Loading sentence-transformers model: {self._model_name}")
        
        try:
            # Import here to avoid slow startup
            # sentence_transformers imports torch, which is heavy
            from sentence_transformers import SentenceTransformer
            
            # Load the model
            # device='cpu' ensures we don't accidentally use GPU
            # (GPU is faster but may not be available)
            self._model = SentenceTransformer(
                self._model_name,
                device='cpu',  # Use 'cuda' for GPU
            )
            
            # Verify dimension matches expected
            test_embedding = self._model.encode("test", convert_to_numpy=True)
            actual_dim = len(test_embedding)
            
            if actual_dim != self._dimension:
                logger.warning(
                    f"Model dimension ({actual_dim}) differs from config ({self._dimension}). "
                    f"Updating to actual dimension."
                )
                self._dimension = actual_dim
            
            logger.info(f"Model loaded successfully. Dimension: {self._dimension}")
            
        except Exception as e:
            logger.error(f"Failed to load model {self._model_name}: {e}")
            raise RuntimeError(f"Failed to load embedding model: {e}")
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension (384 for MiniLM)."""
        return self._dimension
    
    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name
    
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        PROCESS:
        ========
        1. Load model if not loaded
        2. Tokenize text (max 512 tokens, truncate if longer)
        3. Forward pass through transformer
        4. Mean pooling
        5. Return as Python list
        
        Args:
            text: Text to embed (string)
        
        Returns:
            384-dimensional vector as list of floats
        
        Performance:
            - First call: ~2-5 seconds (loads model)
            - Subsequent: ~5-15ms per text
        """
        # Load model on first use
        self._load_model()
        
        # Handle empty text
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self._dimension
        
        try:
            # Generate embedding
            # convert_to_numpy=True returns numpy array (faster)
            # normalize_embeddings=True makes vectors unit length
            embedding = self._model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            
            # Convert numpy array to Python list for JSON serialization
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.
        
        BATCH PROCESSING INTERNALS:
        ===========================
        
        1. All texts tokenized together
        2. Padded to same length (for parallel processing)
        3. Processed in mini-batches through GPU/CPU
        4. Results collected and returned
        
        BATCH SIZE:
        ===========
        - Too small: Underutilizes GPU/CPU
        - Too large: Out of memory
        - Default (32): Good balance
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors (same order as input)
        
        Performance:
            - 100 texts: ~200ms (2ms per text)
            - 1000 texts: ~1.5s (1.5ms per text)
            - Batch is ~5-10x faster than individual calls
        """
        # Load model on first use
        self._load_model()
        
        if not texts:
            return []
        
        # Handle empty texts in batch
        # Replace empty strings with placeholder (will be zero vector)
        processed_texts = []
        empty_indices = set()
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_indices.add(i)
                processed_texts.append("placeholder")  # Will be replaced
            else:
                processed_texts.append(text)
        
        try:
            # Generate embeddings in batch
            # batch_size controls mini-batch size for memory management
            embeddings = self._model.encode(
                processed_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=len(processed_texts) > 100,  # Show progress for large batches
                batch_size=32,
            )
            
            # Convert to list and handle empty texts
            result = []
            for i, embedding in enumerate(embeddings):
                if i in empty_indices:
                    result.append([0.0] * self._dimension)
                else:
                    result.append(embedding.tolist())
            
            logger.debug(f"Generated {len(result)} embeddings")
            return result
            
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}")
            raise
    
    def get_model_info(self) -> dict:
        """
        Get information about the loaded model.
        
        Useful for debugging and monitoring.
        """
        self._load_model()
        
        return {
            "model_name": self._model_name,
            "dimension": self._dimension,
            "max_seq_length": self._model.max_seq_length,
            "device": str(self._model.device),
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_local_provider: Optional[LocalEmbeddingProvider] = None


def get_local_embedding_provider() -> LocalEmbeddingProvider:
    """
    Get or create the singleton LocalEmbeddingProvider instance.
    
    WHY SINGLETON?
    ==============
    - Model loading is expensive (~2-5 seconds)
    - Model uses ~100MB RAM
    - We only need one instance
    - Reuse across all embedding requests
    """
    global _local_provider
    if _local_provider is None:
        _local_provider = LocalEmbeddingProvider()
    return _local_provider

