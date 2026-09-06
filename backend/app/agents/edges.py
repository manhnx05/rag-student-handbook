from app.agents.state import AgentState
from app.core.logger import get_logger

logger = get_logger(__name__)

def check_relevance(state: AgentState) -> str:
    """
    Determines whether to generate an answer, or re-generate a question.
    """
    logger.info("---CHECK RELEVANCE---")
    is_relevant = state.get("is_relevant", False)
    steps = state.get("steps", [])

    if is_relevant:
        logger.info("DECISION: DOCS RELEVANT -> GENERATE")
        return "generate"
    else:
        # Avoid infinite loops by checking if we have rewritten the query already
        # E.g., if "rewrite_query" appears 2 times in steps, we force generate (which will say it doesn't know)
        if steps.count("rewrite_query") >= 2:
            logger.info("DECISION: REWRITE LIMIT REACHED -> GENERATE")
            return "generate"

        logger.info("DECISION: DOCS NOT RELEVANT -> REWRITE QUERY")
        return "rewrite_query"
