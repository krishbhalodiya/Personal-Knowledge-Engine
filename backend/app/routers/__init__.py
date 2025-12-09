"""API Routers for the Personal Knowledge Engine."""

from .documents import router as documents_router
from .search import router as search_router
from .chat import router as chat_router
from .settings import router as settings_router

__all__ = [
    "documents_router",
    "search_router", 
    "chat_router",
    "settings_router",
]

