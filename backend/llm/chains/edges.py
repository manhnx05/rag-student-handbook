from backend.llm.chains.state import AgentState
from backend.utils.helpers import get_logger

logger = get_logger(__name__)


def check_relevance(state: AgentState) -> str:
    """Determines whether to generate an answer or re-generate a question."""
    logger.info("---CHECK RELEVANCE---")
    is_relevant = state.get("is_relevant", False)
    steps = state.get("steps", [])

    if is_relevant:
        logger.info("DECISION: DOCS RELEVANT -> GENERATE")
        return "generate"
    else:
        # Avoid infinite loops — if we've rewritten the query twice, force generate
        if steps.count("rewrite_query") >= 2:
            logger.info("DECISION: REWRITE LIMIT REACHED -> GENERATE")
            return "generate"
        logger.info("DECISION: DOCS NOT RELEVANT -> REWRITE QUERY")
        return "rewrite_query"
