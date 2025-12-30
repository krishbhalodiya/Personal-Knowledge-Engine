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
        logger.info(f"Initializing ChromaDB at {settings.chroma_dir}")
        
        try:
            settings.chroma_dir.mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.PersistentClient(
                path=str(settings.chroma_dir),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                )
            )
            
            # Check if collection already exists
            try:
                existing_collection = self._client.get_collection(name=settings.chroma_collection_name)
                existing_count = existing_collection.count()
                
                # Detect dimension from existing collection
                if existing_count > 0:
                    existing_dim = self.get_collection_dimension()
                    current_dim = settings.embedding_dimension
                    
                    if existing_dim and existing_dim != current_dim:
                        logger.error(
                            f"CRITICAL: Dimension mismatch detected! "
                            f"Collection has {existing_dim}-dimensional embeddings, "
                            f"but current settings use {current_dim}-dimensional embeddings."
                        )
                        raise ValueError(
                            f"Embedding dimension mismatch detected! "
                            f"The existing collection was created with {existing_dim}-dimensional embeddings, "
                            f"but your current configuration uses {current_dim}-dimensional embeddings.\n\n"
                            f"This mismatch will cause all search and indexing operations to fail.\n\n"
                            f"To fix this:\n"
                            f"1. Reset the knowledge base: DELETE http://localhost:8000/api/documents/reset\n"
                            f"2. OR switch to the embedding provider/model that matches the collection dimension\n"
                            f"   (Collection dimension: {existing_dim})\n\n"
                            f"DO NOT continue with mismatched dimensions - it will break everything!"
                        )
                    elif existing_dim:
                        logger.info(f"Collection dimension verified: {existing_dim} (matches current settings)")
                
                # Collection exists and dimension matches (or is empty)
                self._collection = existing_collection
            except Exception as get_error:
                # Collection doesn't exist, create it
                if "does not exist" in str(get_error).lower() or "not found" in str(get_error).lower():
                    logger.info(f"Collection '{settings.chroma_collection_name}' does not exist, creating new one")
                    self._collection = self._client.create_collection(
                        name=settings.chroma_collection_name,
                        metadata={
                            "description": "Personal Knowledge Engine document embeddings",
                            "embedding_dimension": settings.embedding_dimension,
                        }
                    )
                else:
                    raise
            
            count = self._collection.count()
            logger.info(f"ChromaDB initialized. Collection '{settings.chroma_collection_name}' ready.")
            logger.info(f"Current document count: {count}")
            logger.info(f"Collection embedding dimension: {settings.embedding_dimension}")
        except ValueError:
            # Re-raise dimension mismatch errors
            raise
        except Exception as e:
            logger.error(f"Vector store initialization failed: {e}", exc_info=True)
            raise
    
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
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=include,
            )
            return results
        except Exception as e:
            error_str = str(e)
            # Check for dimension mismatch
            if "dimension" in error_str.lower() or "expecting" in error_str.lower():
                # Try to extract the expected dimension from error
                import re
                dim_match = re.search(r'(\d+)', error_str)
                expected_dim = dim_match.group(1) if dim_match else None
                actual_dim = len(query_embedding)
                
                # Try to detect actual collection dimension
                collection_dim = self.get_collection_dimension()
                if collection_dim:
                    expected_dim = str(collection_dim)
                
                logger.error(
                    f"Dimension mismatch: Collection expects {expected_dim} dimensions, "
                    f"but got {actual_dim}. This usually happens when switching embedding providers. "
                    f"Please reset the collection or use the matching embedding provider."
                )
                
                # Provide helpful guidance based on dimensions
                guidance = ""
                if expected_dim == "3072":
                    guidance = "The collection uses OpenAI text-embedding-3-large (3072 dims). Switch to OpenAI provider or reset the collection."
                elif expected_dim == "1536":
                    guidance = "The collection uses OpenAI text-embedding-3-small or ada-002 (1536 dims). Switch to OpenAI provider or reset the collection."
                elif expected_dim == "384":
                    guidance = "The collection uses local embeddings (384 dims). Switch to local provider or reset the collection."
                
                raise ValueError(
                    f"Embedding dimension mismatch: Collection was created with {expected_dim}-dimensional embeddings, "
                    f"but current provider generates {actual_dim}-dimensional embeddings.\n\n"
                    f"{guidance}\n\n"
                    f"To fix this:\n"
                    f"1. Reset the knowledge base: DELETE http://localhost:8000/api/documents/reset (this will delete all indexed documents)\n"
                    f"2. Switch to the embedding provider that matches the collection dimension in Settings\n"
                    f"3. Re-index all documents with the current provider"
                )
            raise
    
    def get_collection_dimension(self) -> Optional[int]:
        """Detect the dimension of embeddings in the collection."""
        try:
            # Try to get one document to check its embedding dimension
            results = self.collection.get(limit=1, include=["embeddings"])
            if results.get("embeddings") and len(results["embeddings"]) > 0:
                embedding = results["embeddings"][0]
                if isinstance(embedding, list) and len(embedding) > 0:
                    return len(embedding)
        except Exception as e:
            logger.debug(f"Could not detect collection dimension: {e}")
        return None
    
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
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
        _vector_store.initialize()
    return _vector_store

