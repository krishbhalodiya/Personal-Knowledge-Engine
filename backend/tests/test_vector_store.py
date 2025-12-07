"""Tests for the vector store service."""

import pytest
from app.services.vector_store import VectorStoreService


class TestVectorStoreService:
    """Test cases for VectorStoreService."""
    
    def test_initialization(self):
        """Test that vector store initializes correctly."""
        store = VectorStoreService()
        store.initialize()
        assert store.collection is not None
        assert store.count() >= 0
    
    def test_add_and_query_documents(self):
        """Test adding and querying documents."""
        store = VectorStoreService()
        store.initialize()
        
        # Add test document
        test_id = "test_doc_1"
        test_embedding = [0.1] * 384  # Match embedding dimension
        test_content = "This is a test document about Python programming."
        
        store.add_documents(
            ids=[test_id],
            embeddings=[test_embedding],
            documents=[test_content],
            metadatas=[{"source": "test"}],
        )
        
        # Query
        results = store.query(
            query_embedding=test_embedding,
            n_results=1,
        )
        
        assert len(results["ids"][0]) > 0
        
        # Cleanup
        store.delete_document(test_id)

