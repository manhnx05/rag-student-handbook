from langchain_openai import OpenAIEmbeddings
from backend.src.core.config import settings


def get_embedding_model():
    """
    Returns the OpenAI embedding model instance.
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set in environment variables or config.py")
    
    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY
    )
    return embeddings


def embed_text(text: str) -> list[float]:
    """
    Embeds a single text string into a vector.
    """
    embeddings = get_embedding_model()
    return embeddings.embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embeds multiple text strings into vectors.
    """
    embeddings = get_embedding_model()
    return embeddings.embed_documents(texts)
