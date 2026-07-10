import pytest
from src.orchestration.handbook_orchestrator import HandbookOrchestrator

@pytest.mark.asyncio
async def test_orchestrator_initialization():
    orchestrator = HandbookOrchestrator()
    assert orchestrator.agent is not None

@pytest.mark.asyncio
async def test_process_query(mocker):
    import asyncio
    # Mock the HandbookAgent.run method
    orchestrator = HandbookOrchestrator()
    
    async def mock_run(query):
        return "Mocked response from agent"
        
    mocker.patch.object(orchestrator.agent, 'run', side_effect=mock_run)
    
    response = await orchestrator.process_query("What is the tuition fee?")
    assert response == "Mocked response from agent"
    orchestrator.agent.run.assert_called_once_with("What is the tuition fee?")
