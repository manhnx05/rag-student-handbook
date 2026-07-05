from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.config import settings
from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store
from typing import Optional


class RAGService:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set")
        
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.vector_store = get_vector_store()
        
        try:
            self.graph_store = get_graph_store()
            self.use_graph = True
        except Exception as e:
            print(f"Graph store not available: {e}")
            self.use_graph = False
        
        # Create the prompt template
        self.prompt = ChatPromptTemplate.from_template("""
You are a helpful assistant that answers questions about the student handbook.
Use the following context from the handbook to answer the question. If you don't know the answer, just say you don't know.

Context from vector store (semantic search):
{vector_context}

Context from graph store (knowledge graph):
{graph_context}

Question: {question}

Answer in Vietnamese:
""")
        
        # Create the chain
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def query(self, question: str, top_k: int = None, use_graph: bool = True) -> dict:
        """
        Queries the RAG system with a question.
        
        Returns:
            A dictionary containing the answer and retrieved context.
        """
        if top_k is None:
            top_k = settings.TOP_K_RESULTS
        
        # Retrieve from vector store
        results = self.vector_store.query(question, top_k=top_k)
        
        # Format vector context
        vector_context_parts = []
        for doc, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            source = metadata.get("source", "unknown")
            page = metadata.get("page", "unknown")
            vector_context_parts.append(f"[Source: {source}, Page: {page}]\n{doc}")
        
        vector_context = "\n\n---\n\n".join(vector_context_parts)
        
        # Retrieve from graph store (optional)
        graph_context = "No graph context available."
        graph_results = []
        if self.use_graph and use_graph:
            try:
                graph_results = self.graph_store.query_graph(question, top_k=top_k)
                if graph_results:
                    graph_context_parts = []
                    for item in graph_results:
                        node = item.get("node", {})
                        connections = item.get("connections", [])
                        name = node.get("name", "Unknown")
                        score = item.get("score", 0)
                        graph_context_parts.append(f"[Node: {name} (score: {score:.4f})]\nConnections: {connections}")
                    graph_context = "\n\n---\n\n".join(graph_context_parts)
            except Exception as e:
                print(f"Graph query error: {e}")
        
        # Generate answer
        answer = self.chain.invoke({
            "vector_context": vector_context,
            "graph_context": graph_context,
            "question": question
        })
        
        return {
            "question": question,
            "answer": answer,
            "vector_sources": [
                {
                    "content": doc,
                    "metadata": meta,
                    "distance": dist
                }
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )
            ],
            "graph_sources": graph_results
        }


# Singleton instance
_rag_service_instance = None


def get_rag_service() -> RAGService:
    """
    Returns the singleton RAGService instance.
    """
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    return _rag_service_instance
