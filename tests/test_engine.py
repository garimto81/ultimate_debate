"""Test ultimate debate engine."""

import pytest

from ultimate_debate.engine import UltimateDebate
from ultimate_debate.consensus.protocol import ConsensusChecker


@pytest.mark.asyncio
async def test_debate_with_mock_clients():
    """Test debate engine with mock AI clients."""
    debate = UltimateDebate(
        task="Analyze the best approach for caching",
        max_rounds=2,
        consensus_threshold=0.8,
    )

    # Run without real clients (uses mock)
    result = await debate.run()

    assert result["status"] in ["FULL_CONSENSUS", "PARTIAL_CONSENSUS", "NO_CONSENSUS"]
    assert result["total_rounds"] <= 2
    assert "task_id" in result
    assert "consensus_percentage" in result


def test_consensus_checker():
    """Test consensus checker logic."""
    checker = ConsensusChecker(threshold=0.8)

    analyses = [
        {"model": "claude", "conclusion": "Use Redis for caching"},
        {"model": "gpt", "conclusion": "Use Redis for caching"},
        {"model": "gemini", "conclusion": "Use Memcached"},
    ]

    result = checker.check_consensus(analyses)

    assert result.status == "PARTIAL_CONSENSUS"
    assert result.consensus_percentage == pytest.approx(2 / 3)
    assert len(result.agreed_items) == 1
    assert len(result.disputed_items) == 1


def test_full_consensus():
    """Test full consensus detection."""
    checker = ConsensusChecker(threshold=0.8)

    analyses = [
        {"model": "claude", "conclusion": "Use Redis"},
        {"model": "gpt", "conclusion": "Use Redis"},
        {"model": "gemini", "conclusion": "Use Redis"},
    ]

    result = checker.check_consensus(analyses)

    assert result.status == "FULL_CONSENSUS"
    assert result.consensus_percentage == 1.0
    assert result.next_action is None
