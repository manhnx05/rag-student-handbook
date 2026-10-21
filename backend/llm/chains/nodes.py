from pydantic import BaseModel, Field

from backend.llm.chains.state import AgentState
from backend.llm.llm_client import LLMFactory
from backend.prompts import (
    ANSWER_SYSTEM_PROMPT,
    CONTEXTUALIZE_QUERY_SYSTEM_PROMPT,
    DOCUMENT_GRADER_SYSTEM_PROMPT,
    QUERY_REWRITE_SYSTEM_PROMPT,
)
from backend.retrieval.retriever import hybrid_search
from backend.utils.helpers import extract_text_content, get_logger

logger = get_logger(__name__)

# Conversation history kept when contextualising the query and answering.
HISTORY_MESSAGES = 6
HISTORY_CHAR_LIMIT = 1500


class GradeDocuments(BaseModel):
    """Boolean score for relevance check on retrieved documents."""

    binary_score: str = Field(
        description="Documents are relevant to the question, 'yes' or 'no'"
    )


def _history_messages(state: AgentState) -> list:
    """Return past turns only — the last message is the current question."""
    messages = list(state.get("messages", []))
    return messages[:-1][-HISTORY_MESSAGES:]


def _format_history(messages: list) -> str:
    """Render past turns as plain text for the prompt."""
    lines = []
    for message in messages:
        role = "Người dùng" if getattr(message, "type", "") == "human" else "Trợ lý"
        lines.append(f"{role}: {extract_text_content(message.content)}")
    return "\n".join(lines)[-HISTORY_CHAR_LIMIT:]


async def contextualize_query_node(state: AgentState) -> dict:
    """Resolve the question against the conversation history before retrieval.

    Without this step follow-up questions ("học kỳ đó thì sao?") are retrieved
    with no context and return the wrong chunks.
    """
    logger.info("---CONTEXTUALIZE QUERY---")
    question = state["question"]
    history = _history_messages(state)

    if not history:
        return {"search_query": question}

    llm = LLMFactory.get_llm()
    prompt = (
        f"{CONTEXTUALIZE_QUERY_SYSTEM_PROMPT}\n\n"
        f"Lịch sử hội thoại:\n{_format_history(history)}\n\n"
        f"Câu hỏi mới nhất: {question}\n\nCâu truy vấn độc lập:"
    )

    response = await llm.ainvoke(prompt)
    search_query = extract_text_content(response.content).strip() or question
    logger.info("Standalone search query: %s", search_query)

    return {"search_query": search_query}


async def retrieve_node(state: AgentState) -> dict:
    """Retrieve documents from Qdrant and Neo4j based on the question."""
    logger.info("---RETRIEVE---")
    search_query = state.get("search_query") or state["question"]
    steps = state.get("steps", [])

    context = await hybrid_search(search_query)

    steps.append("retrieve")
    return {"context": context, "steps": steps}


async def grade_documents_node(state: AgentState) -> dict:
    """Determines whether the retrieved documents are relevant to the question."""
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

    result = await structured_llm_grader.ainvoke(grade_prompt)
    score = result.binary_score

    is_relevant = score.lower() == "yes"
    logger.info("Document relevant: %s", is_relevant)

    steps.append("grade_documents")
    return {"is_relevant": is_relevant, "steps": steps}


async def generate_node(state: AgentState) -> dict:
    """Generate answer using RAG."""
    logger.info("---GENERATE---")
    question = state["question"]
    context = state.get("context", "")
    steps = state.get("steps", [])

    history = _format_history(_history_messages(state))
    history_block = f"Lịch sử hội thoại:\n{history}\n\n" if history else ""

    llm = LLMFactory.get_llm()
    prompt = (
        f"{ANSWER_SYSTEM_PROMPT}\n\n"
        f"{history_block}"
        f"Ngữ cảnh:\n{context}\n\nCâu hỏi: {question}"
    )

    response = await llm.ainvoke(prompt)
    steps.append("generate")

    return {"messages": [response], "steps": steps}


async def rewrite_query_node(state: AgentState) -> dict:
    """Transform the query to produce a better question."""
    logger.info("---REWRITE QUERY---")
    question = state.get("search_query") or state["question"]
    steps = state.get("steps", [])

    llm = LLMFactory.get_llm()
    prompt = f"{QUERY_REWRITE_SYSTEM_PROMPT}\n\nInitial question: {question}"

    response = await llm.ainvoke(prompt)
    new_query = extract_text_content(response.content).strip() or question

    logger.info("Rewrote query: %s", new_query)
    steps.append("rewrite_query")

    return {"search_query": new_query, "steps": steps}
