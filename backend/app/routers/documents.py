"""
Document Management API Routes.

ENDPOINTS:
==========
POST   /api/documents/upload     - Upload and index a document
GET    /api/documents            - List all indexed documents
GET    /api/documents/{id}       - Get a specific document
DELETE /api/documents/{id}       - Delete a document

WHY SEPARATE FROM SERVICES?
===========================
Routers handle HTTP concerns:
- Request parsing and validation
- File upload handling
- HTTP response formatting
- Error response formatting

Services handle business logic:
- Document parsing
- Chunking
- Storage
- Validation rules

This separation makes the code:
1. Easier to test (services can be tested without HTTP)
2. More reusable (services can be called from CLI, scripts, etc.)
3. Cleaner (each layer has one responsibility)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import JSONResponse

from ..models.documents import DocumentResponse, DocumentListResponse, Document
from ..services.ingestion import IngestionService, get_ingestion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.md', '.markdown', '.txt', '.text'}


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload"),
    title: Optional[str] = Form(None, description="Optional document title"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """
    Upload and index a new document.
    
    SUPPORTED FORMATS:
    - PDF (.pdf)
    - Word Documents (.docx, .doc)
    - Markdown (.md, .markdown)
    - Plain Text (.txt, .text)
    
    PROCESS:
    1. Validate file type and size
    2. Read file content
    3. Parse document to extract text
    4. Chunk text into smaller pieces
    5. Store in vector database
    
    RESPONSE:
    Returns document metadata including:
    - id: Unique document identifier
    - filename: Original filename
    - title: Extracted or provided title
    - doc_type: Detected document type
    - chunk_count: Number of chunks created
    
    EXAMPLE:
    ```bash
    curl -X POST "http://localhost:8000/api/documents/upload" \\
         -F "file=@document.pdf" \\
         -F "title=My Document"
    ```
    """
    logger.info(f"Upload request received: {file.filename}")
    
    # =========================================================================
    # STEP 1: VALIDATE FILE
    # =========================================================================
    
    # Check filename exists
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )
    
    # Check file extension
    extension = '.' + file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}. "
                   f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    
    # =========================================================================
    # STEP 2: READ FILE CONTENT
    # =========================================================================
    
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=400,
            detail="Failed to read uploaded file"
        )
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded"
        )
    
    # =========================================================================
    # STEP 3: INGEST DOCUMENT
    # =========================================================================
    
    try:
        document = await ingestion_service.ingest_bytes(
            content=content,
            filename=file.filename,
            title=title,
        )
    except ValueError as e:
        # Validation errors (unsupported type, no text, etc.)
        logger.warning(f"Document validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected errors
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process document. Please try again."
        )
    
    # =========================================================================
    # STEP 4: RETURN RESPONSE
    # =========================================================================
    
    logger.info(f"Successfully uploaded document: {document.id}")
    
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        title=document.title,
        doc_type=document.doc_type,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
        message=f"Document uploaded successfully. Created {document.chunk_count} searchable chunks."
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(100, ge=1, le=1000, description="Maximum documents to return"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """
    List all indexed documents.
    
    PAGINATION:
    - limit: Maximum number of documents to return (default: 100)
    - offset: Number of documents to skip (default: 0)
    
    EXAMPLE:
    ```bash
    # Get first 10 documents
    curl "http://localhost:8000/api/documents?limit=10"
    
    # Get next 10 documents (page 2)
    curl "http://localhost:8000/api/documents?limit=10&offset=10"
    ```
    """
    documents = ingestion_service.list_documents(limit=limit, offset=offset)
    total = ingestion_service.get_document_count()
    
    return DocumentListResponse(
        documents=documents,
        total=total,
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    include_content: bool = Query(False, description="Include full document content"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """
    Get a specific document by ID.
    
    PARAMETERS:
    - document_id: The unique document identifier
    - include_content: Whether to include full text content (default: false)
    
    NOTE:
    Full content can be large. Only request it when needed.
    
    EXAMPLE:
    ```bash
    # Get metadata only
    curl "http://localhost:8000/api/documents/doc_abc123"
    
    # Get with full content
    curl "http://localhost:8000/api/documents/doc_abc123?include_content=true"
    ```
    """
    document = ingestion_service.get_document(document_id)
    
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}"
        )
    
    # Build response
    response = {
        "id": document.id,
        "filename": document.filename,
        "title": document.title,
        "doc_type": document.doc_type.value,
        "chunk_count": document.chunk_count,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
        "metadata": document.metadata,
    }
    
    if include_content:
        response["content"] = document.content
        response["content_length"] = len(document.content)
    
    return response


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """
    Delete a document and all its chunks from the index.
    
    This operation:
    1. Removes all chunks from the vector store
    2. Deletes the stored file from disk
    3. Removes the document from the registry
    
    WARNING: This operation cannot be undone!
    
    EXAMPLE:
    ```bash
    curl -X DELETE "http://localhost:8000/api/documents/doc_abc123"
    ```
    """
    # Check if document exists
    document = ingestion_service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}"
        )
    
    # Delete the document
    success = await ingestion_service.delete_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document"
        )
    
    logger.info(f"Deleted document: {document_id}")
    
    return {
        "message": f"Document {document_id} deleted successfully",
        "document_id": document_id,
        "chunks_deleted": document.chunk_count,
    }


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    limit: int = Query(10, ge=1, le=100, description="Maximum chunks to return"),
    offset: int = Query(0, ge=0, description="Number of chunks to skip"),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """
    Get chunks for a specific document.
    
    This endpoint is useful for:
    - Debugging chunking results
    - Viewing how a document was split
    - Understanding search results context
    
    EXAMPLE:
    ```bash
    curl "http://localhost:8000/api/documents/doc_abc123/chunks?limit=5"
    ```
    """
    # Check if document exists
    document = ingestion_service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}"
        )
    
    # Get chunks from vector store
    vector_store = ingestion_service.vector_store
    
    # Query chunks by document_id metadata
    # Note: ChromaDB's get() with where filter
    results = vector_store.collection.get(
        where={"document_id": document_id},
        limit=limit,
        offset=offset,
        include=["documents", "metadatas"],
    )
    
    chunks = []
    for i, chunk_id in enumerate(results["ids"]):
        chunks.append({
            "chunk_id": chunk_id,
            "content": results["documents"][i] if results["documents"] else None,
            "metadata": results["metadatas"][i] if results["metadatas"] else None,
        })
    
    # Sort by chunk_index
    chunks.sort(key=lambda c: c.get("metadata", {}).get("chunk_index", 0))
    
    return {
        "document_id": document_id,
        "filename": document.filename,
        "total_chunks": document.chunk_count,
        "chunks": chunks,
        "limit": limit,
        "offset": offset,
    }
