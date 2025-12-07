"""
Application configuration using Pydantic Settings.
All settings can be overridden via environment variables.
"""

from pathlib import Path
from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "Personal Knowledge Engine"
    debug: bool = False
    api_prefix: str = "/api"
    
    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = base_dir / "data"
    documents_dir: Path = data_dir / "documents"
    chroma_dir: Path = data_dir / "chroma_db"
    models_dir: Path = data_dir / "models"
    
    # ChromaDB
    chroma_collection_name: str = "knowledge_base"
    
    # =========================
    # Provider Configuration
    # =========================
    
    # Embedding Provider: "local" (sentence-transformers) or "openai"
    embedding_provider: Literal["local", "openai"] = "local"
    
    # LLM Provider: "local" (llama.cpp) or "openai"  
    llm_provider: Literal["local", "openai"] = "local"
    
    # =========================
    # Local Embeddings (sentence-transformers)
    # =========================
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    local_embedding_dimension: int = 384
    
    # =========================
    # OpenAI Configuration
    # =========================
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-ada-002"
    openai_embedding_dimension: int = 1536
    openai_chat_model: str = "gpt-4-turbo-preview"
    
    # =========================
    # Local LLM (llama.cpp)
    # =========================
    llm_model_path: Optional[str] = None  # Path to GGUF model file
    llm_context_length: int = 4096
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7
    llm_gpu_layers: int = 0  # Set > 0 for GPU acceleration
    
    # =========================
    # Google API Configuration
    # =========================
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    
    # =========================
    # Chunking
    # =========================
    chunk_size: int = 512  # tokens
    chunk_overlap: int = 50  # tokens
    
    # =========================
    # Search
    # =========================
    search_top_k: int = 5  # Number of results to return
    hybrid_search_semantic_weight: float = 0.7  # Weight for semantic vs keyword
    
    # =========================
    # Server
    # =========================
    host: str = "0.0.0.0"
    port: int = 8000
    
    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension based on selected provider."""
        if self.embedding_provider == "openai":
            return self.openai_embedding_dimension
        return self.local_embedding_dimension
    
    def setup_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

