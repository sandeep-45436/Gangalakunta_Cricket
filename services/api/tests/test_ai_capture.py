"""
Tests for LangGraph Multi-Agent Live Capture, Gemini Vision,
and Direct Player Reel Attribution.
"""
import pytest
from httpx import AsyncClient

from app.ai.agents import CricketCaptureState, get_cricket_capture_graph


@pytest.mark.asyncio
async def test_langgraph_cricket_agent_workflow():
    """
    Directly tests the compiled LangGraph 4-agent state graph:
    1. DeliverySegmenterAgent
    2. CricketEventRecognizerAgent
    3. ScoreCaptureFusionAgent
    4. PlayerReelPublisherAgent
    """
    graph = get_cricket_capture_graph()
    assert graph is not None

    initial_state: CricketCaptureState = {
        "session_id": "test-session-123",
        "match_id": "test-match-456",
        "current_timestamp_ms": 14200,
        "striker_id": "player-striker-1",
        "striker_name": "Virat Kohli",
        "bowler_id": "player-bowler-1",
        "bowler_name": "Jasprit Bumrah",
        "admin_runs": 6,
        "admin_is_wicket": False,
        "logs": [],
    }

    result = await graph.ainvoke(initial_state)

    # 1. Delivery Segmenter output
    assert result["delivery_detected"] is True
    assert result["delivery_phase"] == "completed"
    assert result["window_start_ms"] == 10700  # 14200 - 3500
    assert result["window_impact_ms"] == 14200
    assert result["window_end_ms"] == 18700

    # 2. Cricket Vision Recognizer output
    assert result["event_type"] == "six"
    assert result["shot_name"] is not None and len(result["shot_name"]) > 0
    assert result["gemini_confidence"] >= 0.70

    # 3. Score Fusion output
    assert result["score_reconciled"] is True
    assert result["config_before_sec"] >= 3.5

    # 4. Player Reel Publisher output (Core requirement: must go to the player!)
    assert result["player_records_updated"] is True
    assert len(result["attributed_records"]) == 2

    striker_rec = next(r for r in result["attributed_records"] if r["role"] == "striker")
    assert striker_rec["player_id"] == "player-striker-1"
    assert striker_rec["player_name"] == "Virat Kohli"
    assert striker_rec["event_type"] == "six"

    bowler_rec = next(r for r in result["attributed_records"] if r["role"] == "bowler")
    assert bowler_rec["player_id"] == "player-bowler-1"
    assert bowler_rec["player_name"] == "Jasprit Bumrah"
    assert "Bowler" in bowler_rec["role"].capitalize()


@pytest.mark.asyncio
async def test_langgraph_wicket_delivery_attribution():
    """
    Tests that a wicket delivery is attributed directly to the bowler (and striker dismissal).
    """
    graph = get_cricket_capture_graph()

    state: CricketCaptureState = {
        "session_id": "test-session-wicket",
        "match_id": "test-match-w",
        "current_timestamp_ms": 25000,
        "striker_id": "batter-id-7",
        "striker_name": "Babar Azam",
        "bowler_id": "bowler-id-93",
        "bowler_name": "Shaheen Afridi",
        "admin_runs": 0,
        "admin_is_wicket": True,
        "admin_wicket_type": "bowled",
        "logs": [],
    }

    result = await graph.ainvoke(state)

    assert result["event_type"] == "wicket"
    assert len(result["attributed_records"]) == 2

    bowler_rec = next(r for r in result["attributed_records"] if r["role"] == "bowler")
    assert bowler_rec["player_id"] == "bowler-id-93"
    assert bowler_rec["event_type"] == "wicket"
    assert bowler_rec["metrics"]["wicket_taken"] is True


def _make_test_token() -> str:
    import jwt
    return jwt.encode({"sub": "00000000-0000-0000-0000-000000000001"}, "secret", algorithm="HS256")


@pytest.mark.asyncio
async def test_ai_capture_api_endpoints(client: AsyncClient):
    """
    Tests POST /api/ai/analyze-stream and POST /api/ai/auto-capture-delivery endpoints.
    """
    token = _make_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "session_id": "a0000000-0000-0000-0000-000000000001",
        "match_id": "b0000000-0000-0000-0000-000000000001",
        "current_timestamp_ms": 12500,
        "striker_name": "Rohit Sharma",
        "bowler_name": "Mitchell Starc",
        "admin_runs": 4,
        "admin_is_wicket": False,
    }

    # 1. Analyze stream
    resp = await client.post("/api/ai/analyze-stream", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["delivery_detected"] is True
    assert data["event_type"] == "four"
    assert len(data["attributed_players"]) >= 1

    # 2. Auto-capture delivery
    resp2 = await client.post("/api/ai/auto-capture-delivery", json=payload, headers=headers)
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["score_reconciled"] is True
    assert data2["status_message"] != ""
