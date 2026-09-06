from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    Represents the state of our CRAG/Self-RAG agent.
    """
    # List of messages in the conversation. `add_messages` appends new ones.
    messages: Annotated[List[BaseMessage], add_messages]

    # The current user query (extracted for easier access during nodes)
    question: str

    # Retrieved documents context
    context: str

    # Flag to indicate if retrieved documents are relevant
    is_relevant: bool

    # Track the steps taken (e.g., retrieve -> grade -> rewrite)
    steps: List[str]
