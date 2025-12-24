import logging
from typing import List, Optional
import numpy as np

from .base import EmbeddingProvider
from ...config import settings

logger = logging.getLogger(__name__)


class LocalEmbeddingProvider(EmbeddingProvider):
    
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.local_embedding_model
        self._dimension = settings.local_embedding_dimension
        self._model = None
        
        logger.info(f"LocalEmbeddingProvider initialized with model: {self._model_name}")
    
    def _load_model(self):
        if self._model is not None:
            return
        
        logger.info(f"Loading sentence-transformers model: {self._model_name}")
        
        try:
            from sentence_transformers import SentenceTransformer
            
            self._model = SentenceTransformer(
                self._model_name,
                device='cpu',
            )
            
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
        return self._dimension
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    def embed(self, text: str) -> List[float]:
        self._load_model()
        
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self._dimension
        
        try:
            embedding = self._model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        
        if not texts:
            return []
        
        processed_texts = []
        empty_indices = set()
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_indices.add(i)
                processed_texts.append("placeholder")
            else:
                processed_texts.append(text)
        
        try:
            embeddings = self._model.encode(
                processed_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=len(processed_texts) > 100,
                batch_size=32,
            )
            
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
        self._load_model()
        
        return {
            "model_name": self._model_name,
            "dimension": self._dimension,
            "max_seq_length": self._model.max_seq_length,
            "device": str(self._model.device),
        }


_local_provider: Optional[LocalEmbeddingProvider] = None


def get_local_embedding_provider() -> LocalEmbeddingProvider:
    global _local_provider
    if _local_provider is None:
        _local_provider = LocalEmbeddingProvider()
    return _local_provider

