"""Search-related Pydantic models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Search query model."""
    
    query: str = Field(..., description="Search query text", min_length=1)
    top_k: int = Field(5, description="Number of results to return", ge=1, le=50)
    filter_doc_type: Optional[str] = Field(None, description="Filter by document type")
    filter_document_id: Optional[str] = Field(None, description="Filter by specific document")
    include_content: bool = Field(True, description="Include chunk content in results")


class SearchResult(BaseModel):
    """Single search result."""
    
    chunk_id: str = Field(..., description="Chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    filename: str = Field(..., description="Source filename")
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., description="Similarity score (0-1)")
    chunk_index: int = Field(..., description="Position in document")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Highlighted content for display
    highlighted_content: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response model."""
    
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: float


class HybridSearchQuery(SearchQuery):
    """Hybrid search combining semantic and keyword search."""
    
    semantic_weight: float = Field(0.7, description="Weight for semantic search (0-1)", ge=0, le=1)
    keyword_weight: float = Field(0.3, description="Weight for keyword search (0-1)", ge=0, le=1)

