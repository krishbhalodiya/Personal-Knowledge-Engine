"""Search API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, Body

from ..models.search import SearchQuery, SearchResponse, HybridSearchQuery
from ..services.search import SearchService, get_search_service
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(..., description="Search query", min_length=1),
    top_k: int = Query(5, description="Number of results", ge=1, le=50),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    search_service: SearchService = Depends(get_search_service),
):
    """
    Perform semantic search across indexed documents.
    
    This endpoint uses vector similarity to find relevant content.
    It works best for natural language questions or concept exploration.
    
    EXAMPLE:
    GET /api/search?q=how%20do%20neural%20networks%20learn
    """
    filters = {}
    if doc_type:
        filters["doc_type"] = doc_type
        
    try:
        return await search_service.semantic_search(
            query=q,
            top_k=top_k,
            filter_metadata=filters if filters else None
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    query: HybridSearchQuery = Body(...),
    search_service: SearchService = Depends(get_search_service),
):
    """
    Perform hybrid semantic + keyword search.
    
    This combines vector similarity (Semantic) with BM25 (Keyword)
    to provide the most robust search results.
    
    PARAMETERS:
    - query: The search text
    - top_k: Number of results
    - semantic_weight: Weight for vector search (0.0 to 1.0, default 0.7)
    
    EXAMPLE:
    POST /api/search/hybrid
    {
      "query": "python decorators",
      "top_k": 5,
      "semantic_weight": 0.6
    }
    """
    filters = {}
    if query.filter_doc_type:
        filters["doc_type"] = query.filter_doc_type
    if query.filter_document_id:
        filters["document_id"] = query.filter_document_id
        
    try:
        return await search_service.hybrid_search(
            query=query.query,
            top_k=query.top_k,
            semantic_weight=query.semantic_weight,
            filter_metadata=filters if filters else None
        )
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex", tags=["admin"])
async def trigger_reindex(
    search_service: SearchService = Depends(get_search_service),
):
    """
    Trigger a rebuild of the BM25 index.
    
    Useful after bulk uploads if you want immediate keyword search availability.
    Usually BM25 is built lazily on first search, but this forces an update.
    """
    try:
        # Force rebuild by clearing existing index
        search_service._bm25 = None
        search_service._ensure_bm25_index()
        
        doc_count = len(search_service._bm25_doc_ids) if search_service._bm25 else 0
        return {"message": "Index rebuilt successfully", "indexed_documents": doc_count}
    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
