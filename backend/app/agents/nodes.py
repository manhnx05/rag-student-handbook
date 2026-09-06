from pydantic import BaseModel, Field
from app.retrieval.hybrid_retriever import hybrid_search
from app.llm.llm_factory import LLMFactory
from app.agents.state import AgentState
from app.core.logger import get_logger

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

    system_prompt = (
        "You are a grader assessing relevance of a retrieved document to a user question. "
        "If the document contains keyword(s) or semantic meaning related to the question, grade it as relevant. "
        "Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question."
    )

    grade_prompt = f"{system_prompt}\n\nRetrieved document:\n{context}\n\nUser question: {question}"

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
    system_prompt = (
        "Bạn là một trợ lý ảo hỗ trợ sinh viên. "
        "Nhiệm vụ của bạn là giải đáp các thắc mắc về sổ tay sinh viên, quy chế học vụ.\n\n"
        "Sử dụng các thông tin ngữ cảnh được cung cấp để trả lời câu hỏi ở cuối. "
        "Nếu bạn không biết câu trả lời từ ngữ cảnh, hãy nói rằng bạn không tìm thấy thông tin trong sổ tay. "
        "Luôn trả lời bằng tiếng Việt, rõ ràng và mạch lạc."
    )

    prompt = f"{system_prompt}\n\nNgữ cảnh:\n{context}\n\nCâu hỏi: {question}"

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
    system_prompt = (
        "You are an assistant that translates a user question into a better query for a vector database and graph search. "
        "Look at the input and try to reason about the underlying semantic intent / meaning. "
        "Provide a better, more focused query in Vietnamese."
    )
    prompt = f"{system_prompt}\n\nInitial question: {question}"

    response = await llm.ainvoke(prompt)
    new_question = response.content

    logger.info(f"Rewrote query: {new_question}")
    steps.append("rewrite_query")

    return {"question": new_question, "steps": steps}
