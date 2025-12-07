"""Document management API routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List

from ..models.documents import DocumentResponse, DocumentListResponse
from ..services.vector_store import VectorStoreService, get_vector_store

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Upload and index a new document."""
    # TODO: Implement in Phase 1.2/1.3
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """List all indexed documents."""
    # TODO: Implement document listing
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Get a specific document by ID."""
    # TODO: Implement document retrieval
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Delete a document and its chunks from the index."""
    # TODO: Implement document deletion
    raise HTTPException(status_code=501, detail="Not implemented yet")

