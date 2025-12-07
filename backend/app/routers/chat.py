"""Chat/Q&A API routes."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from ..models.chat import ChatRequest, ChatResponse, ConversationHistory
from ..services.vector_store import VectorStoreService, get_vector_store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Send a message and get a RAG-powered response."""
    # TODO: Implement in Phase 2.2
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    vector_store: VectorStoreService = Depends(get_vector_store),
):
    """Send a message and get a streaming RAG-powered response."""
    # TODO: Implement streaming in Phase 2.2
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/history/{conversation_id}", response_model=ConversationHistory)
async def get_conversation_history(conversation_id: str):
    """Get conversation history by ID."""
    # TODO: Implement conversation history
    raise HTTPException(status_code=501, detail="Not implemented yet")

