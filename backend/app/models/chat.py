"""Chat/Q&A related Pydantic models."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Chat message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Single chat message."""
    
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SourceCitation(BaseModel):
    """Source citation for RAG responses."""
    
    document_id: str
    filename: str
    chunk_id: str
    content_preview: str = Field(..., description="Preview of the cited content")
    relevance_score: float


class ChatRequest(BaseModel):
    """Chat request model."""
    
    message: str = Field(..., description="User message", min_length=1)
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    include_sources: bool = Field(True, description="Include source citations")
    top_k_context: int = Field(3, description="Number of context chunks to retrieve")
    stream: bool = Field(False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Chat response model."""
    
    message: str = Field(..., description="Assistant response")
    conversation_id: str
    sources: List[SourceCitation] = Field(default_factory=list)
    model_used: str
    response_time_ms: float
    tokens_used: Optional[int] = None


class ConversationHistory(BaseModel):
    """Conversation history model."""
    
    id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

