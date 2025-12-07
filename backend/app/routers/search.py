"""Search API routes."""

from fastapi import APIRouter, HTTPException, Depends, Query

from ..models.search import SearchQuery, SearchResponse, HybridSearchQuery
from ..services.vector_store import VectorStoreService, get_vector_store

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(..., description="Search query", min_length=1),
    top_k: int = Query(5, description="Number of results", ge=1, le=50),
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Perform semantic search across indexed documents."""
    # TODO: Implement in Phase 2.1
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    query: HybridSearchQuery,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Perform hybrid semantic + keyword search."""
    # TODO: Implement in Phase 2.1
    raise HTTPException(status_code=501, detail="Not implemented yet")

