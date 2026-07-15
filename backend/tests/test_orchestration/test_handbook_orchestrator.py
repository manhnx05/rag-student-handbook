import pytest
from src.orchestration.handbook_orchestrator import HandbookOrchestrator

@pytest.mark.asyncio
async def test_orchestrator_initialization():
    orchestrator = HandbookOrchestrator()
    assert orchestrator.handbook_agent is not None

@pytest.mark.asyncio
async def test_process_query(mocker):
    import asyncio
    orchestrator = HandbookOrchestrator()
    
    async def mock_stream(*args, **kwargs):
        yield "Mocked "
        yield "response "
        yield "from agent"
        
    mocker.patch.object(orchestrator, 'process_query_stream', side_effect=mock_stream)
    
    response_chunks = []
    async for chunk in orchestrator.process_query_stream("What is the tuition fee?"):
        response_chunks.append(chunk)
        
    assert "".join(response_chunks) == "Mocked response from agent"
    orchestrator.process_query_stream.assert_called_once_with("What is the tuition fee?")
