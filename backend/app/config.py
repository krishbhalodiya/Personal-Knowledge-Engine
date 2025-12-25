from pathlib import Path
from typing import Optional, Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    app_name: str = "Personal Knowledge Engine"
    debug: bool = False
    api_prefix: str = "/api"
    
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = base_dir / "data"
    documents_dir: Path = data_dir / "documents"
    chroma_dir: Path = data_dir / "chroma_db"
    models_dir: Path = data_dir / "models"
    
    chroma_collection_name: str = "knowledge_base"
    
    embedding_provider: Literal["local", "openai"] = "local"
    llm_provider: Literal["local", "openai", "gemini"] = "local"
    
    @field_validator('embedding_provider', 'llm_provider', mode='before')
    @classmethod
    def normalize_provider(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower()
        return v
    
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    local_embedding_dimension: int = 384
    
    openai_api_key: Optional[str] = None
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dimension: int = 3072
    openai_chat_model: str = "gpt-4o"
    
    llm_model_path: Optional[str] = None
    llm_context_length: int = 4096
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7
    llm_gpu_layers: int = 0
    
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    google_gemini_api_key: Optional[str] = None
    google_gemini_model: str = "gemini-3-pro-preview"
    
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
        if self.embedding_provider == "openai":
            model = self.openai_embedding_model.lower()
            if "3-large" in model:
                return 3072
            elif "3-small" in model or "ada-002" in model:
                return 1536
            return self.openai_embedding_dimension
        return self.local_embedding_dimension
    
    def setup_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

