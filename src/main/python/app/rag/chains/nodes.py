from pydantic import BaseModel, Field
from app.rag.retrievers.hybrid_retriever import hybrid_search
from app.rag.llm.llm_factory import LLMFactory
from app.rag.chains.state import AgentState
from app.rag.prompts import (
    ANSWER_SYSTEM_PROMPT,
    DOCUMENT_GRADER_SYSTEM_PROMPT,
    QUERY_REWRITE_SYSTEM_PROMPT,
)
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

class GradeDocuments(BaseModel):
    """Boolean score for relevance check on retrieved documents."""
    binary_score: str = Field(description="Documents are relevant to the question, 'yes' or 'no'")

async def retrieve_node(state: AgentState) -> dict:
    """
    Retrieve documents from Qdrant and Neo4j based on the question.
    """
    logger.info("---RETRIEVE---")
    question = state["question"]
    steps = state.get("steps", [])

    # Retrieve documents
    context = await hybrid_search(question)

    steps.append("retrieve")
    return {"context": context, "steps": steps}

async def grade_documents_node(state: AgentState) -> dict:
    """
    Determines whether the retrieved documents are relevant to the question.
    """
    logger.info("---GRADE DOCUMENTS---")
    question = state["question"]
    context = state.get("context", "")
    steps = state.get("steps", [])

    llm = LLMFactory.get_llm()
    structured_llm_grader = llm.with_structured_output(GradeDocuments)

    grade_prompt = (
        f"{DOCUMENT_GRADER_SYSTEM_PROMPT}\n\n"
        f"Retrieved document:\n{context}\n\nUser question: {question}"
    )

    # In Langchain v0.2+, invoke returns the BaseModel instance directly
    result = await structured_llm_grader.ainvoke(grade_prompt)
    score = result.binary_score

    is_relevant = score.lower() == "yes"
    logger.info(f"Document relevant: {is_relevant}")

    steps.append("grade_documents")
    return {"is_relevant": is_relevant, "steps": steps}

async def generate_node(state: AgentState) -> dict:
    """
    Generate answer using RAG.
    """
    logger.info("---GENERATE---")
    question = state["question"]
    context = state.get("context", "")
    steps = state.get("steps", [])

    llm = LLMFactory.get_llm()
    prompt = f"{ANSWER_SYSTEM_PROMPT}\n\nNgữ cảnh:\n{context}\n\nCâu hỏi: {question}"

    response = await llm.ainvoke(prompt)
    steps.append("generate")

    return {"messages": [response], "steps": steps}

async def rewrite_query_node(state: AgentState) -> dict:
    """
    Transform the query to produce a better question.
    """
    logger.info("---REWRITE QUERY---")
    question = state["question"]
    steps = state.get("steps", [])

    llm = LLMFactory.get_llm()
    prompt = f"{QUERY_REWRITE_SYSTEM_PROMPT}\n\nInitial question: {question}"

    response = await llm.ainvoke(prompt)
    new_question = response.content

    logger.info(f"Rewrote query: {new_question}")
    steps.append("rewrite_query")

    return {"question": new_question, "steps": steps}
