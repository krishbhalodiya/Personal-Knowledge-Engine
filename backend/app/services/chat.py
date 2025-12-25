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
    
    def __init__(self):
        self.search_service = get_search_service()
        self.llm_provider = get_llm_provider()
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            search_results = await self.search_service.hybrid_search(
                query=request.message,
                top_k=request.top_k_context,
            )
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise
        
        system_prompt = self._build_system_prompt(search_results.results)
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ]
        
        # Add conversation history if provided
        if request.history:
            for hist_msg in request.history[-10:]:  # Last 10 messages for context
                messages.append(hist_msg)
        
        # Add current user message
        messages.append(ChatMessage(role=MessageRole.USER, content=request.message))
        
        response_text = await self.llm_provider.chat(messages)
        
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
            response_time_ms=0,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        search_results = await self.search_service.hybrid_search(
            query=request.message,
            top_k=request.top_k_context,
        )
        
        system_prompt = self._build_system_prompt(search_results.results)
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ]
        
        # Add conversation history if provided
        if request.history:
            for hist_msg in request.history[-10:]:  # Last 10 messages for context
                messages.append(hist_msg)
        
        # Add current user message
        messages.append(ChatMessage(role=MessageRole.USER, content=request.message))
        
        async for chunk in self.llm_provider.chat_stream(messages):
            yield chunk

    def _build_system_prompt(self, results: List[Any]) -> str:
        context_str = ""
        for i, res in enumerate(results):
            context_str += f"\n--- Source {i+1}: {res.filename} ---\n{res.content}\n"
            
        return f"""You are a personal AI assistant for a knowledge management system. Your name is PK Assistant.

YOUR PURPOSE:
You help users search, understand, and query their personal documents, emails, notes, and files.
You have access to the user's indexed documents and will answer questions based on this knowledge base.

INSTRUCTIONS:
1. Answer questions using ONLY the provided context from the user's documents
2. When you use information from a source, mention which document it came from (e.g., "According to your email from...", "In your notes about...")
3. If multiple sources contain relevant information, synthesize them into a coherent answer
4. If the context doesn't contain enough information to fully answer, say so clearly
5. Be conversational, helpful, and direct - this is the user's personal assistant
6. If asked about yourself, explain you're a personal knowledge assistant that helps query their documents

CONTEXT FROM USER'S DOCUMENTS:
{context_str}

Remember: You're helping the user understand THEIR OWN data. Be helpful and personable."""

# Singleton
_chat_service = None

def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

