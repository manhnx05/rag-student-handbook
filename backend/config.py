from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    
    # Gemini
    GEMINI_API_KEY: str
    EMBEDDING_MODEL: str = "dangvantuan/vietnamese-embedding"
    EMBEDDING_DIMENSION: int = 768
    LLM_MODEL: str = "gemini-3.1-flash-lite"
    
    # Postgres
    DATABASE_URL: str
    
    # Neo4j
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    NEO4J_DB: str = "neo4j"
    
    # Qdrant
    QDRANT_URL: str
    QDRANT_COLLECTION: str = "student_handbook"
    
    # Retrieval
    TOP_K_RESULTS: int = 3
    # Number of candidates pulled from the dense index before reranking.
    # Must be >= TOP_K_RESULTS; larger values improve recall at the cost of latency.
    RETRIEVAL_RECALL_K: int = 20

    # Graph ingestion — set False to skip Neo4j extraction during PDF ingest
    # (useful when Neo4j is unavailable or during initial setup)
    GRAPH_INGESTION_ENABLED: bool = True
    
    # Redis
    REDIS_URL: str

    # CORS — comma-separated list of allowed browser client origins.
    # Example: "http://localhost:8501,https://myapp.example.com"
    CORS_ORIGINS: str = "http://localhost:8501"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list, stripping whitespace."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        # asyncpg requires postgresql+asyncpg
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL

    @property
    def psycopg_database_url(self) -> str:
        """Connection string for psycopg3 (used by LangGraph AsyncPostgresSaver)."""
        # psycopg3 uses the plain postgresql:// scheme
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
        return self.DATABASE_URL

settings = Settings()
