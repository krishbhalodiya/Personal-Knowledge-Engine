"""ChromaDB Vector Store Service."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing ChromaDB vector storage."""
    
    def __init__(self):
        """Initialize ChromaDB client with persistent storage."""
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None
    
    def initialize(self) -> None:
        """Initialize the ChromaDB client and collection."""
        logger.info(f"Initializing ChromaDB at {settings.chroma_dir}")
        
        # Ensure directory exists
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        
        # Create persistent client
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={
                "description": "Personal Knowledge Engine document embeddings",
                "embedding_dimension": settings.embedding_dimension,
            }
        )
        
        logger.info(f"ChromaDB initialized. Collection '{settings.chroma_collection_name}' ready.")
        logger.info(f"Current document count: {self._collection.count()}")
    
    @property
    def client(self) -> chromadb.PersistentClient:
        """Get the ChromaDB client."""
        if self._client is None:
            self.initialize()
        return self._client
    
    @property
    def collection(self) -> chromadb.Collection:
        """Get the main collection."""
        if self._collection is None:
            self.initialize()
        return self._collection
    
    def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add documents with embeddings to the collection."""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas or [{}] * len(ids),
        )
        logger.info(f"Added {len(ids)} documents to collection")
    
    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Query the collection for similar documents."""
        include = include or ["documents", "metadatas", "distances"]
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=include,
        )
        
        return results
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID."""
        results = self.collection.get(
            ids=[doc_id],
            include=["documents", "metadatas", "embeddings"],
        )
        
        if results["ids"]:
            return {
                "id": results["ids"][0],
                "document": results["documents"][0] if results["documents"] else None,
                "metadata": results["metadatas"][0] if results["metadatas"] else None,
                "embedding": results["embeddings"][0] if results["embeddings"] else None,
            }
        return None
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"Deleted document {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
    
    def delete_by_metadata(self, where: Dict[str, Any]) -> int:
        """Delete documents matching metadata filter."""
        # Get matching IDs first
        results = self.collection.get(
            where=where,
            include=["metadatas"],
        )
        
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} documents matching filter")
            return len(results["ids"])
        return 0
    
    def get_all_documents(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get all documents with pagination."""
        return self.collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"],
        )
    
    def count(self) -> int:
        """Get total document count."""
        return self.collection.count()
    
    def reset(self) -> None:
        """Reset the collection (delete all data)."""
        logger.warning("Resetting ChromaDB collection - all data will be deleted!")
        self.client.delete_collection(settings.chroma_collection_name)
        self._collection = self.client.create_collection(
            name=settings.chroma_collection_name,
            metadata={
                "description": "Personal Knowledge Engine document embeddings",
                "embedding_dimension": settings.embedding_dimension,
            }
        )
        logger.info("Collection reset complete")


# Singleton instance
_vector_store: Optional[VectorStoreService] = None


def get_vector_store() -> VectorStoreService:
    """Get the singleton VectorStoreService instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
        _vector_store.initialize()
    return _vector_store

