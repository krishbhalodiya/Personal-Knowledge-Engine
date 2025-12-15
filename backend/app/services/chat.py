"""
Chat Service - RAG Pipeline Implementation.

================================================================================
RAG PIPELINE (Retrieve-Augment-Generate)
================================================================================

1. RETRIEVE
   - User asks: "How do neural networks learn?"
   - SearchService finds relevant chunks:
     * "Neural networks learn through backpropagation..."
     * "Gradient descent optimizes the network..."

2. AUGMENT
   - Construct a prompt with context:
     "You are a helpful assistant. Use the following context to answer the user's question.
      Context:
      - Neural networks learn through backpropagation...
      - Gradient descent optimizes...
      
      User: How do neural networks learn?"

3. GENERATE
   - LLM generates answer based on context.
   - We stream this back to the user.

================================================================================
"""

import logging
from typing import List, AsyncGenerator, Dict, Any

from ..models.chat import (
    ChatRequest, 
    ChatResponse, 
    ChatMessage, 
    MessageRole, 
    SourceCitation
)
from .search import SearchService, get_search_service
from .llm import LLMProvider, get_llm_provider

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for RAG-powered chat.
    """
    
    def __init__(self):
        self.search_service = get_search_service()
        self.llm_provider = get_llm_provider()
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Full RAG chat (non-streaming).
        """
        # 1. Retrieve Context
        search_results = await self.search_service.hybrid_search(
            query=request.message,
            top_k=request.top_k_context,
        )
        
        # 2. Construct Prompt
        system_prompt = self._build_system_prompt(search_results.results)
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=request.message)
        ]
        
        # 3. Generate Answer
        response_text = await self.llm_provider.chat(messages)
        
        # 4. Format Response
        sources = [
            SourceCitation(
                document_id=res.document_id,
                filename=res.filename,
                chunk_id=res.chunk_id,
                content_preview=res.content[:200] + "...",
                relevance_score=res.score
            )
            for res in search_results.results
        ]
        
        return ChatResponse(
            message=response_text,
            conversation_id=request.conversation_id or "new",
            sources=sources if request.include_sources else [],
            model_used=self.llm_provider.model_name,
            response_time_ms=0, # TODO: Track time
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Streaming RAG chat.
        Yields chunks of the answer.
        """
        # 1. Retrieve Context
        search_results = await self.search_service.hybrid_search(
            query=request.message,
            top_k=request.top_k_context,
        )
        
        # 2. Construct Prompt
        system_prompt = self._build_system_prompt(search_results.results)
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=request.message)
        ]
        
        # 3. Stream Answer
        # We assume the caller handles source citation separately (or we yield a special event)
        # For simplicity, we just stream text.
        async for chunk in self.llm_provider.chat_stream(messages):
            yield chunk

    def _build_system_prompt(self, results: List[Any]) -> str:
        """
        Construct the system prompt with context.
        """
        context_str = ""
        for i, res in enumerate(results):
            context_str += f"\n--- Source {i+1} ({res.filename}) ---\n{res.content}\n"
            
        return f"""You are a helpful AI assistant for a personal knowledge engine.
Your goal is to answer the user's question accurately using ONLY the provided context.

Rules:
1. Use the provided context to answer.
2. If the answer is not in the context, say "I cannot answer this based on the available documents."
3. Cite your sources implicitly (e.g., "According to the document...").
4. Be concise and direct.

Context:{context_str}
"""

# Singleton
_chat_service = None

def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

