"""
Document Ingestion Service - Orchestrates the document processing pipeline.

WHAT IS INGESTION?
==================
Ingestion is the process of taking a raw document and making it searchable.

PIPELINE OVERVIEW:
==================

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Upload  │───▶│  Parse   │───▶│  Chunk   │───▶│  Embed   │───▶│  Store   │
│  (bytes) │    │  (text)  │    │  (list)  │    │ (vectors)│    │ (ChromaDB)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘

Step 1: UPLOAD
- Receive file bytes from API
- Validate file type and size
- Generate unique document ID

Step 2: PARSE
- Detect document type from extension
- Use appropriate parser (PDF, DOCX, etc.)
- Extract plain text content

Step 3: CHUNK
- Split text into overlapping chunks
- Preserve character positions for citations
- Store chunk metadata

Step 4: EMBED (Phase 3)
- Generate embeddings for each chunk
- Use configured provider (local/OpenAI)
- Batch processing for efficiency

Step 5: STORE
- Store embeddings in ChromaDB
- Store metadata (document ID, chunk index, etc.)
- Enable similarity search

WHY SEPARATE SERVICE?
=====================
1. Single Responsibility: Router handles HTTP, service handles logic
2. Testability: Service can be tested without HTTP layer
3. Reusability: Can be called from different routes or scripts
4. Transaction boundary: Can handle rollback if any step fails
"""

import logging
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import aiofiles

from ..config import settings
from ..models.documents import (
    Document,
    DocumentResponse,
    DocumentType,
    DocumentChunk,
)
from ..utils.parsers import parse_document_bytes, detect_document_type, get_parser
from ..utils.chunking import chunk_text, Chunk
from .vector_store import VectorStoreService, get_vector_store

# Import embedding provider (lazy import to avoid circular dependencies)
# The actual import happens in the method to allow for flexible provider switching

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Service for ingesting documents into the knowledge base.
    
    RESPONSIBILITIES:
    =================
    - Coordinate the ingestion pipeline
    - Generate and track document IDs
    - Store document files locally
    - Manage chunk creation and storage
    - Handle errors and rollback
    
    USAGE:
    ======
    service = IngestionService()
    
    # From uploaded file bytes
    doc = await service.ingest_bytes(file_content, "document.pdf")
    
    # From file path
    doc = await service.ingest_file(Path("/path/to/document.pdf"))
    """
    
    def __init__(self, vector_store: Optional[VectorStoreService] = None):
        """
        Initialize the ingestion service.
        
        Args:
            vector_store: Vector store service (default: singleton instance)
        """
        self.vector_store = vector_store or get_vector_store()
        
        # Document storage tracking (in-memory for now)
        # In production, this would be a database
        self._documents: Dict[str, Document] = {}
    
    async def ingest_bytes(
        self,
        content: bytes,
        filename: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Ingest a document from raw bytes.
        
        This is the main entry point for uploaded files.
        
        PROCESS:
        ========
        1. Validate input
        2. Generate document ID (based on content hash for deduplication)
        3. Detect document type
        4. Parse to extract text
        5. Chunk the text
        6. Store file locally
        7. Add chunks to vector store (without embeddings for now)
        8. Return document metadata
        
        Args:
            content: Raw file bytes
            filename: Original filename
            title: Optional document title
            metadata: Optional additional metadata
            
        Returns:
            Document object with ID and metadata
        """
        logger.info(f"Starting ingestion for: {filename} ({len(content)} bytes)")
        
        # Step 1: Validate
        if not content:
            raise ValueError("Empty file content")
        
        if not filename:
            raise ValueError("Filename required")
        
        # Step 2: Generate document ID
        # Using content hash provides deduplication:
        # Same file uploaded twice gets same ID
        doc_id = self._generate_document_id(content, filename)
        
        # Check if already exists
        if doc_id in self._documents:
            logger.info(f"Document already exists: {doc_id}")
            return self._documents[doc_id]
        
        # Step 3: Detect type
        try:
            doc_type = detect_document_type(filename)
        except ValueError as e:
            logger.error(f"Unsupported file type: {filename}")
            raise ValueError(f"Unsupported file type: {e}")
        
        # Step 4: Parse
        try:
            text, _ = parse_document_bytes(content, filename)
        except Exception as e:
            logger.error(f"Failed to parse document: {e}")
            raise ValueError(f"Failed to parse document: {e}")
        
        if not text.strip():
            raise ValueError("Document contains no extractable text")
        
        # Step 5: Chunk
        chunks = chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 6: Store file locally
        file_path = await self._store_file(content, filename, doc_id)
        
        # Step 7: Create document record
        now = datetime.utcnow()
        document = Document(
            id=doc_id,
            filename=filename,
            title=title or self._extract_title(text, filename),
            doc_type=doc_type,
            content=text,
            file_path=str(file_path),
            chunk_count=len(chunks),
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        
        # Step 8: Store chunks in vector store
        # NOTE: For now, we store chunks WITHOUT embeddings
        # Embeddings will be added in Phase 3
        await self._store_chunks(document, chunks)
        
        # Save document reference
        self._documents[doc_id] = document
        
        logger.info(f"Successfully ingested document: {doc_id}")
        return document
    
    async def ingest_file(
        self,
        file_path: Path,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Ingest a document from a file path.
        
        Reads the file and delegates to ingest_bytes.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        content = file_path.read_bytes()
        return await self.ingest_bytes(
            content=content,
            filename=file_path.name,
            title=title,
            metadata=metadata,
        )
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document and all its chunks.
        
        CLEANUP STEPS:
        ==============
        1. Remove chunks from vector store
        2. Delete local file
        3. Remove from document registry
        """
        logger.info(f"Deleting document: {doc_id}")
        
        if doc_id not in self._documents:
            logger.warning(f"Document not found: {doc_id}")
            return False
        
        document = self._documents[doc_id]
        
        # Step 1: Remove from vector store
        # Delete all chunks for this document
        deleted = self.vector_store.delete_by_metadata({"document_id": doc_id})
        logger.info(f"Deleted {deleted} chunks from vector store")
        
        # Step 2: Delete local file
        if document.file_path:
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
        
        # Step 3: Remove from registry
        del self._documents[doc_id]
        
        return True
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        return self._documents.get(doc_id)
    
    def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DocumentResponse]:
        """
        List all documents.
        
        Returns DocumentResponse (metadata only, not full content).
        """
        documents = list(self._documents.values())
        
        # Sort by created_at descending (newest first)
        documents.sort(key=lambda d: d.created_at, reverse=True)
        
        # Apply pagination
        documents = documents[offset:offset + limit]
        
        # Convert to response model (excludes content)
        return [
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                title=doc.title,
                doc_type=doc.doc_type,
                chunk_count=doc.chunk_count,
                created_at=doc.created_at,
            )
            for doc in documents
        ]
    
    def get_document_count(self) -> int:
        """Get total number of documents."""
        return len(self._documents)
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    def _generate_document_id(self, content: bytes, filename: str) -> str:
        """
        Generate a unique document ID.
        
        STRATEGY:
        =========
        We use a content-based hash for deduplication:
        - Same file content = same ID (prevents duplicates)
        - Include filename in hash (different named copies get different IDs)
        - Use first 12 chars of SHA-256 (short but collision-resistant)
        
        WHY NOT UUID?
        =============
        UUID would be simpler but:
        - Same document uploaded twice gets different IDs
        - No deduplication
        - Harder to track duplicates
        
        Content hash provides:
        - Automatic deduplication
        - Deterministic IDs
        - Easy to verify integrity
        """
        # Combine content and filename for hash
        hash_input = content + filename.encode('utf-8')
        content_hash = hashlib.sha256(hash_input).hexdigest()[:12]
        
        # Prefix with doc_ for clarity
        return f"doc_{content_hash}"
    
    def _extract_title(self, text: str, filename: str) -> str:
        """
        Extract a title from the document.
        
        HEURISTICS:
        ===========
        1. Use first non-empty line if it looks like a title
           - Short (< 100 chars)
           - Starts with capital letter
           - Doesn't end with comma (probably not a sentence)
        2. Fall back to filename without extension
        """
        lines = text.strip().split('\n')
        
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if not line:
                continue
            
            # Check if it looks like a title
            if (
                len(line) < 100 and
                line[0].isupper() and
                not line.endswith(',')
            ):
                return line
        
        # Fall back to filename
        return Path(filename).stem
    
    async def _store_file(
        self,
        content: bytes,
        filename: str,
        doc_id: str,
    ) -> Path:
        """
        Store file locally for future reference.
        
        WHY STORE LOCALLY?
        ==================
        1. Allows re-processing if we update chunking strategy
        2. Users can download their original files
        3. Enables re-indexing with different settings
        4. Backup in case vector store is corrupted
        
        FILE NAMING:
        ============
        {doc_id}_{original_filename}
        
        This prevents collisions while keeping filenames readable.
        """
        # Ensure documents directory exists
        settings.documents_dir.mkdir(parents=True, exist_ok=True)
        
        # Create safe filename
        safe_filename = f"{doc_id}_{filename}"
        file_path = settings.documents_dir / safe_filename
        
        # Write file asynchronously (non-blocking)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"Stored file: {file_path}")
        return file_path
    
    async def _store_chunks(
        self,
        document: Document,
        chunks: List[Chunk],
    ) -> None:
        """
        Store document chunks in the vector store WITH REAL EMBEDDINGS.
        
        EMBEDDING PROCESS:
        ==================
        
        1. Extract text content from each chunk
        2. Generate embeddings using configured provider (local or OpenAI)
        3. Store embeddings + text + metadata in ChromaDB
        
        WHY BATCH EMBEDDING?
        ====================
        
        Instead of:
            for chunk in chunks:
                embedding = provider.embed(chunk.content)  # Slow!
        
        We do:
            embeddings = provider.embed_batch([c.content for c in chunks])  # Fast!
        
        Batch processing is 5-10x faster because:
        - GPU processes all at once
        - Reduces API call overhead (for OpenAI)
        - More efficient memory usage
        
        WHAT GETS STORED IN CHROMADB:
        =============================
        
        For each chunk:
        - id: "doc_abc123_chunk_0"
        - embedding: [0.234, -0.567, ...] (384 or 1536 floats)
        - document: "The actual chunk text..."
        - metadata: {document_id, filename, chunk_index, ...}
        """
        if not chunks:
            return
        
        # Import embedding provider here to avoid circular imports
        from .embeddings import get_embedding_provider
        
        # Get the configured embedding provider
        embedding_provider = get_embedding_provider()
        
        logger.info(
            f"Generating embeddings for {len(chunks)} chunks "
            f"using {embedding_provider.model_name}"
        )
        
        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []
        
        for chunk in chunks:
            # Generate unique chunk ID
            chunk_id = f"{document.id}_chunk_{chunk.index}"
            
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append({
                "document_id": document.id,
                "filename": document.filename,
                "doc_type": document.doc_type.value,
                "chunk_index": chunk.index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "token_count": chunk.token_count,
            })
        
        # Generate REAL embeddings using the configured provider
        # This is the key change from Phase 2!
        try:
            embeddings = embedding_provider.embed_batch(documents)
            logger.info(f"Generated {len(embeddings)} embeddings ({embedding_provider.dimension} dimensions)")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise ValueError(f"Embedding generation failed: {e}")
        
        # Verify embedding dimensions match what ChromaDB expects
        if embeddings and len(embeddings[0]) != settings.embedding_dimension:
            logger.warning(
                f"Embedding dimension ({len(embeddings[0])}) differs from "
                f"configured dimension ({settings.embedding_dimension}). "
                f"This may cause issues with existing data."
            )
        
        # Add to vector store
        self.vector_store.add_documents(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        
        logger.info(f"Stored {len(chunks)} chunks with embeddings for document {document.id}")


# =============================================================================
# SINGLETON AND FACTORY
# =============================================================================

_ingestion_service: Optional[IngestionService] = None


def get_ingestion_service() -> IngestionService:
    """Get or create the singleton IngestionService instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service

