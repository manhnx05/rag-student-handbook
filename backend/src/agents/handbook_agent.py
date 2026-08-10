"""
HandbookAgent — LangGraph ReAct agent with PostgreSQL-backed conversation memory.

Why PostgreSQL instead of in-memory MemorySaver:
  MemorySaver stores checkpoints in process memory, so every server restart
  wipes all conversation history.  AsyncPostgresSaver persists each checkpoint
  to the same Postgres instance already used for users and chat sessions, so
  history survives restarts and scales across multiple worker processes.
"""
import asyncio

from langchain.agents import create_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from src.agents.base_agent import BaseAgent
from src.llms.llm_factory import LLMFactory
from src.tools.handbook_search_tool import handbook_search_tool
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "Bạn là một trợ lý ảo hỗ trợ sinh viên. "
    "Nhiệm vụ của bạn là giải đáp các thắc mắc về sổ tay sinh viên, quy chế học vụ.\n\n"
    "Luôn luôn sử dụng công cụ handbook_search_tool để tìm kiếm thông tin trước khi trả lời. "
    "Dựa vào thông tin tìm được để đưa ra câu trả lời chính xác. "
    "Trả lời bằng tiếng Việt, rõ ràng và mạch lạc. "
    "Nếu thông tin không có trong sổ tay, hãy nói rằng bạn không biết."
)

# Module-level singleton so the connection pool is shared across requests.
_pool: AsyncConnectionPool | None = None
_executor = None
_setup_lock = asyncio.Lock()


async def _get_executor():
    """
    Lazily initialise the connection pool and LangGraph executor once.
    Uses a lock to prevent races on the first concurrent request.
    """
    global _pool, _executor

    if _executor is not None:
        return _executor

    async with _setup_lock:
        # Double-check inside the lock
        if _executor is not None:
            return _executor

        logger.info("Initialising PostgreSQL checkpointer for HandbookAgent …")
        _pool = AsyncConnectionPool(
            conninfo=settings.psycopg_database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"autocommit": True}
        )
        await _pool.open()

        checkpointer = AsyncPostgresSaver(conn=_pool)
        await checkpointer.setup()   # creates checkpoint tables if they don't exist

        llm = LLMFactory.get_llm()
        _executor = create_agent(
            llm,
            tools=[handbook_search_tool],
            system_prompt=SYSTEM_PROMPT,
            checkpointer=checkpointer,
        )

        logger.info("HandbookAgent executor ready with PostgreSQL checkpointer.")
        return _executor


class HandbookAgent(BaseAgent):
    """
    Thin wrapper that exposes the shared LangGraph executor.

    Instantiation is cheap — the actual pool/executor initialisation is
    deferred to the first call of `get_executor()`.
    """

    def get_executor(self):
        """Return the coroutine that resolves to the shared executor."""
        return _get_executor()

    async def run(self, query: str) -> str:
        executor = await self.get_executor()
        result = await executor.ainvoke({"messages": [("user", query)]})
        return result["messages"][-1].content
