"""Chat/Q&A API routes."""

import logging
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..models.chat import ChatRequest, ChatResponse, ChatMessage, MessageRole, SourceCitation
from ..services.chat import ChatService, get_chat_service
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Chat history storage directory
CHAT_HISTORY_DIR = settings.data_dir / "chat_history"
CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Models for conversation management
# ============================================================================

class ConversationSummary(BaseModel):
    """Summary of a conversation for listing."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    preview: str  # First user message or summary


class ConversationFull(BaseModel):
    """Full conversation with messages."""
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[dict]  # List of message dicts with role, content, sources


class SaveMessageRequest(BaseModel):
    """Request to save a message to a conversation."""
    conversation_id: str
    role: str  # "user" or "assistant"
    content: str
    sources: Optional[List[dict]] = None


# ============================================================================
# Helper functions for chat history
# ============================================================================

def _get_conversation_path(conversation_id: str) -> Path:
    """Get the file path for a conversation."""
    return CHAT_HISTORY_DIR / f"{conversation_id}.json"


def _load_conversation(conversation_id: str) -> Optional[dict]:
    """Load a conversation from disk."""
    path = _get_conversation_path(conversation_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.error(f"Failed to load conversation {conversation_id}: {e}")
        return None


def _save_conversation(conversation: dict) -> bool:
    """Save a conversation to disk."""
    try:
        path = _get_conversation_path(conversation["id"])
        path.write_text(json.dumps(conversation, indent=2, default=str))
        return True
    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")
        return False


def _generate_title(first_message: str) -> str:
    """Generate a title from the first message."""
    # Take first 50 chars, clean up
    title = first_message[:50].strip()
    if len(first_message) > 50:
        title += "..."
    return title or "New Chat"


# ============================================================================
# Conversation management endpoints
# ============================================================================

@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
):
    """
    List all saved conversations, sorted by most recent.
    """
    conversations = []
    
    for file_path in CHAT_HISTORY_DIR.glob("*.json"):
        try:
            data = json.loads(file_path.read_text())
            messages = data.get("messages", [])
            
            # Get first user message for preview
            preview = ""
            for msg in messages:
                if msg.get("role") == "user":
                    preview = msg.get("content", "")[:100]
                    break
            
            conversations.append(ConversationSummary(
                id=data["id"],
                title=data.get("title", "Untitled"),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                message_count=len(messages),
                preview=preview,
            ))
        except Exception as e:
            logger.warning(f"Failed to parse conversation file {file_path}: {e}")
            continue
    
    # Sort by updated_at descending
    conversations.sort(key=lambda c: c.updated_at, reverse=True)
    
    return conversations[:limit]


@router.post("/conversations/new")
async def create_conversation():
    """
    Create a new conversation and return its ID.
    """
    conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow()
    
    conversation = {
        "id": conversation_id,
        "title": "New Chat",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "messages": [],
    }
    
    _save_conversation(conversation)
    
    return {"id": conversation_id, "title": "New Chat"}


@router.get("/conversations/{conversation_id}", response_model=ConversationFull)
async def get_conversation(conversation_id: str):
    """
    Get a full conversation with all messages.
    """
    conversation = _load_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return ConversationFull(
        id=conversation["id"],
        title=conversation.get("title", "Untitled"),
        created_at=datetime.fromisoformat(conversation["created_at"]),
        updated_at=datetime.fromisoformat(conversation["updated_at"]),
        messages=conversation.get("messages", []),
    )


@router.post("/conversations/{conversation_id}/message")
async def save_message(conversation_id: str, request: SaveMessageRequest):
    """
    Save a message to an existing conversation.
    """
    conversation = _load_conversation(conversation_id)
    
    if not conversation:
        # Create new conversation
        now = datetime.utcnow()
        conversation = {
            "id": conversation_id,
            "title": "New Chat",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "messages": [],
        }
    
    # Add message
    message = {
        "role": request.role,
        "content": request.content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if request.sources:
        message["sources"] = request.sources
    
    conversation["messages"].append(message)
    conversation["updated_at"] = datetime.utcnow().isoformat()
    
    # Update title from first user message
    if request.role == "user" and len(conversation["messages"]) == 1:
        conversation["title"] = _generate_title(request.content)
    
    _save_conversation(conversation)
    
    return {"success": True, "message_count": len(conversation["messages"])}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation.
    """
    path = _get_conversation_path(conversation_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    try:
        path.unlink()
        return {"success": True, "message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Send a message and get a complete RAG-powered response.
    
    This endpoint waits for the full generation before returning.
    Useful for non-streaming clients.
    """
    try:
        return await chat_service.chat(request)
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest = Body(...),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Send a message and get a streaming RAG-powered response.
    
    Returns a stream of JSON lines:
    {"type": "chunk", "content": "Hello"}
    {"type": "chunk", "content": " world"}
    {"type": "sources", "data": [...]}
    
    This allows the frontend to render text progressively AND show citations.
    """
    async def stream_generator():
        # 1. Get Context (Search)
        search_results = await chat_service.search_service.hybrid_search(
            query=request.message,
            top_k=request.top_k_context,
        )
        
        # 2. Send Sources Event
        sources = [
            {
                "document_id": res.document_id,
                "filename": res.filename,
                "chunk_id": res.chunk_id,
                "score": res.score,
                "preview": res.content[:100] + "..."
            }
            for res in search_results.results
        ]
        yield json.dumps({"type": "sources", "data": sources}) + "\n"
        
        # 3. Build Prompt & Stream Answer
        system_prompt = chat_service._build_system_prompt(search_results.results)
        from ..models.chat import ChatMessage, MessageRole
        
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=request.message)
        ]
        
        try:
            async for chunk in chat_service.llm_provider.chat_stream(messages):
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
