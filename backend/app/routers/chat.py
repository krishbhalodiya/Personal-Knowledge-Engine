"""Chat/Q&A API routes."""

import logging
import json
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import StreamingResponse

from ..models.chat import ChatRequest, ChatResponse
from ..services.chat import ChatService, get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


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
