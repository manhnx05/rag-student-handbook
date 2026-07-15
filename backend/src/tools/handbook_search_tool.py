from langchain.tools import tool
from src.memory.vector_store import get_vector_store

@tool
def handbook_search_tool(query: str) -> str:
    """Search the Student Handbook for relevant information based on a query."""
    vector_store = get_vector_store()
    results = vector_store.query(query, top_k=3)
    
    documents = results.get("documents", [[]])[0]
    if not documents:
        return "No relevant information found in the handbook."
    
    return "\n\n---\n\n".join(documents)
