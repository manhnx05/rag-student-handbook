
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
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

settings = Settings()
