import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.agents.base import AgentState
from backend.app.agents.quality import FactCheckerAgent
from backend.app.agents.reasoning import DebateEngine
from backend.app.infrastructure.db.models import DBDebate

@pytest.mark.asyncio
async def test_fact_checker_scoring():
    agent = FactCheckerAgent()
    
    # 1. Test credibility score helper
    assert agent._evaluate_source_credibility("PubMed") == 95.0
    assert agent._evaluate_source_credibility("arXiv") == 90.0
    assert agent._evaluate_source_credibility("gov site") == 88.0
    assert agent._evaluate_source_credibility("Tavily Web Search") == 70.0
    assert agent._evaluate_source_credibility("Low quality Blog") == 30.0

    # 2. Test year extraction helper
    source = {"title": "Clinical trials in 2021", "content": "Findings presented in 2021 are positive."}
    assert agent._extract_year(source) == 2021
    
    source_no_year = {"title": "No year", "content": "No content year"}
    assert agent._extract_year(source_no_year) == 2024 # default

@pytest.mark.asyncio
async def test_fact_checker_execute_no_sources():
    agent = FactCheckerAgent()
    
    state = AgentState(
        session_id="test-session-456",
        query="test aerobic exercise",
        plan=[],
        evidence=[],
        findings=[{"claim": "Aerobic exercise cures Alzheimers", "confidence_score": 50.0}]
    )
    
    # Execute should map to INSUFFICIENT_EVIDENCE and 0.0 confidence when no sources support
    updated_state = await agent.execute(state)
    assert len(updated_state.findings) == 1
    finding = updated_state.findings[0]
    assert finding["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert finding["confidence_score"] == 0.0
    assert finding["claim"].startswith("[Insufficient Evidence]")

@pytest.mark.asyncio
async def test_debate_engine_and_db_persistence():
    # Mock database session
    db_session = MagicMock()
    
    engine = DebateEngine(db=db_session)
    
    state = AgentState(
        session_id="test-session-123",
        query="exercise and brain health",
        plan=[],
        evidence=[
            {"title": "Study A", "url": "http://study-a.com", "source": "PubMed", "content": "Exercise improves memory."},
            {"title": "Study B", "url": "http://study-b.com", "source": "arXiv", "content": "Exercise does not improve memory."}
        ],
        findings=[
            {"claim": "Exercise improves memory", "confidence_score": 90.0},
            {"claim": "Exercise does not improve memory", "confidence_score": 75.0}
        ]
    )
    
    # Mock LLM provider response to avoid API calls
    mock_provider = AsyncMock()
    mock_provider.generate_structured.return_value = MagicMock(
        model_dump=lambda: {
            "debate_summary": "Dialectic resolved contradiction.",
            "consensus_claim": "Exercise has positive effects on cognitive health but details vary.",
            "resolved_confidence": 85.0
        }
    )
    
    from backend.app.infrastructure.llm.manager import LLMManager
    LLMManager.get_provider = MagicMock(return_value=mock_provider)
    
    updated_state = await engine.execute(state)
    
    # Verify a new finding was added by debate
    assert len(updated_state.findings) == 3
    resolved = updated_state.findings[2]
    assert resolved["claim"] == "Exercise has positive effects on cognitive health but details vary."
    assert resolved["confidence_score"] == 85.0
    assert resolved["verification_status"] == "VERIFIED"
    
    # Verify database persist was called
    assert db_session.add.call_count == 1
    added_obj = db_session.add.call_args[0][0]
    assert isinstance(added_obj, DBDebate)
    assert added_obj.session_id == "test-session-123"
    assert added_obj.final_resolution == resolved["claim"]
    assert db_session.commit.call_count == 1
