"""Services for the Personal Knowledge Engine."""

from .vector_store import VectorStoreService, get_vector_store
from .ingestion import IngestionService, get_ingestion_service
from .embeddings import (
    EmbeddingProvider,
    LocalEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
    get_local_embedding_provider,
    get_openai_embedding_provider,
)

__all__ = [
    # Vector Store
    "VectorStoreService",
    "get_vector_store",
    # Ingestion
    "IngestionService",
    "get_ingestion_service",
    # Embeddings
    "EmbeddingProvider",
    "LocalEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
    "get_local_embedding_provider",
    "get_openai_embedding_provider",
]

