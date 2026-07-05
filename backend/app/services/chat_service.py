
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.app.config import settings
from backend.app.rag.retriever import hybrid_retrieve
from backend.app.core.graph_store import get_graph_store
from typing import Optional

class ChatService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.graph = get_graph_store()
        
        self.prompt = ChatPromptTemplate.from_template("""
You are a helpful assistant that answers questions about the student handbook and patient data.
Use the following context to answer the question. If you don't know, just say you don't know.

Context: {context}

Question: {question}

Answer in Vietnamese:
""")
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    def query(self, question: str, patient_id: Optional[str] = None):
        # Retrieve from vector store
        vector_results = hybrid_retrieve(question)
        
        # Retrieve from graph store
        graph_context = ""
        try:
            graph_results = self.graph.query_graph(question)
            if graph_results:
                graph_context_parts = []
                for res in graph_results:
                    graph_context_parts.append(f"- {res['node']}: {res.get('connections', [])}")
                graph_context = "\n".join(graph_context_parts)
        except Exception as e:
            print(f"Graph query error: {e}")
        
        # Combine context
        context_parts = []
        for r in vector_results:
            context_parts.append(r.payload["content"])
        
        if graph_context:
            context_parts.append(graph_context)
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Generate answer
        answer = self.chain.invoke({
            "context": context,
            "question": question
        })
        
        return {
            "answer": answer,
            "sources": [r.payload for r in vector_results]
        }

chat_service = ChatService()
