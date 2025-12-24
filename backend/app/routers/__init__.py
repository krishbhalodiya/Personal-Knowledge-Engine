"""API Routers for the Personal Knowledge Engine."""

from .documents import router as documents_router
from .search import router as search_router
from .chat import router as chat_router
from .settings import router as settings_router
from .google_auth import router as google_auth_router
from .gmail import router as gmail_router
from .drive import router as drive_router
from .folders import router as folders_router

__all__ = [
    "documents_router",
    "search_router",
    "chat_router",
    "settings_router",
    "google_auth_router",
    "gmail_router",
    "drive_router",
    "folders_router",
]

