
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            '.env'
        ),
        env_file_encoding='utf-8',
        extra='ignore'
    )
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Postgres
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/student_handbook"
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DB: str = "neo4j"
    
    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "student_handbook"
    
    # Retrieval
    TOP_K_RESULTS: int = 3
    
    # Auth
    JWT_SECRET_KEY: str = "super_secret_key_please_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Resend
    RESEND_API_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # CORS — comma-separated list of allowed origins.
    # Example: "http://localhost:3000,https://myapp.example.com"
    CORS_ORIGINS: str = "http://localhost:3000"

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
