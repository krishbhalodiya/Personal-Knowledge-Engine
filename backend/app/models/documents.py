"""Document-related Pydantic models."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DocumentType(str, Enum):
    """Supported document types."""
    MARKDOWN = "markdown"
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"


class DocumentChunk(BaseModel):
    """A chunk of a document with its embedding."""
    
    id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    content: str = Field(..., description="Chunk text content")
    chunk_index: int = Field(..., description="Position in document")
    start_char: int = Field(..., description="Start character position")
    end_char: int = Field(..., description="End character position")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentBase(BaseModel):
    """Base document model."""
    
    filename: str = Field(..., description="Original filename")
    title: Optional[str] = Field(None, description="Document title")
    doc_type: DocumentType = Field(..., description="Document type")


class DocumentCreate(DocumentBase):
    """Model for creating a new document."""
    
    content: Optional[str] = Field(None, description="Raw text content if provided directly")


class Document(DocumentBase):
    """Full document model with metadata."""
    
    id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Full document content")
    file_path: Optional[str] = Field(None, description="Path to stored file")
    chunk_count: int = Field(0, description="Number of chunks")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    """Response model for document operations."""
    
    id: str
    filename: str
    title: Optional[str]
    doc_type: DocumentType
    chunk_count: int
    created_at: datetime
    message: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response model for listing documents."""
    
    documents: List[DocumentResponse]
    total: int

