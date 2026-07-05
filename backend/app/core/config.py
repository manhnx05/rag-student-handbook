from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"
    CHROMA_DB_PATH: str = "data/vector_db"
    CHROMA_COLLECTION_NAME: str = "student_handbook"
    TOP_K_RESULTS: int = 3
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"

settings = Settings()
