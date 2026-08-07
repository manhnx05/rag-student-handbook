from langchain.tools import tool
from src.knowledge.retriever import hybrid_search


@tool
async def handbook_search_tool(query: str) -> str:
    """Search the Student Handbook for relevant information based on a query.

    Uses hybrid retrieval: semantic vector search (Qdrant) combined with
    knowledge-graph search (Neo4j) to return the most relevant context.
    """
    return await hybrid_search(query)
