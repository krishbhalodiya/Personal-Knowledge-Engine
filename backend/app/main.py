"""
Personal Knowledge Engine - FastAPI Application Entry Point.

A privacy-first personal knowledge engine with semantic search and Q&A capabilities.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import documents_router, search_router, chat_router, settings_router
from .services.vector_store import get_vector_store

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    
    # Setup directories
    settings.setup_directories()
    logger.info(f"Data directory: {settings.data_dir}")
    
    # Initialize vector store
    vector_store = get_vector_store()
    logger.info(f"Vector store initialized with {vector_store.count()} documents")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="""
    A privacy-first personal knowledge engine that indexes your documents locally
    and provides semantic search and Q&A capabilities using local LLMs.
    
    ## Features
    - **Document Indexing**: Upload and index PDF, DOCX, Markdown, and text files
    - **Semantic Search**: Find relevant content using natural language queries
    - **Q&A Chat**: Ask questions about your knowledge base with RAG-powered responses
    - **Privacy-First**: All processing happens locally, your data never leaves your machine
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(search_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(settings_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    vector_store = get_vector_store()
    return {
        "status": "healthy",
        "vector_store": {
            "connected": True,
            "document_count": vector_store.count(),
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

