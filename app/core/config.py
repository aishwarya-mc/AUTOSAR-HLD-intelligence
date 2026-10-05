from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM
    llm_provider: str = Field(default="local", alias="LLM_PROVIDER")
    llm_model: str = Field(default="", alias="LLM_MODEL")

    # Embeddings
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")

    # ChromaDB
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")

    # Database
    database_url: str = Field(
        default="sqlite:///./data/autosar.db",
        alias="DATABASE_URL",
    )

    # Retrieval
    top_k: int = Field(default=8, alias="TOP_K", ge=1)
    chunk_size: int = Field(default=1200, alias="CHUNK_SIZE", ge=100)
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP", ge=0)

    # Upload
    max_upload_mb: int = Field(default=100, alias="MAX_UPLOAD_MB", ge=1)

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def sample_data_dir(self) -> Path:
        return self.data_dir / "sample"

    @property
    def evaluation_data_dir(self) -> Path:
        return self.data_dir / "evaluation"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def document_dir(self) -> Path:
        return self.data_dir / "documents"


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()
