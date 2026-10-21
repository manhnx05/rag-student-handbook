from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Represents the state of our CRAG/Self-RAG agent."""

    # List of messages in the conversation. `add_messages` appends new ones.
    messages: Annotated[List[BaseMessage], add_messages]

    # The current user query (extracted for easier access during nodes)
    question: str

    # Standalone query used for retrieval: `question` resolved against the
    # conversation history (falls back to `question` when there is no history)
    search_query: str

    # Retrieved documents context
    context: str

    # Flag to indicate if retrieved documents are relevant
    is_relevant: bool

    # Track the steps taken (e.g., retrieve -> grade -> rewrite)
    steps: List[str]
