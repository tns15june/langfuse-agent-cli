from langfuse_cli.formatters.agent import compact_trace, format_agent_output


def test_compact_trace_formatter():
    raw_trace = {
        "id": "tr_123",
        "name": "agent_execution",
        "timestamp": "2026-10-24T20:00:00Z",
        "latency": 3.14159,
        "totalCost": 0.005432,
        "sessionId": "sess_001",
        "observations": [
            {"type": "SPAN", "name": "router", "latency": 0.5, "level": "DEFAULT", "model": "claude-3-5"},
            {"type": "GENERATION", "name": "tool", "level": "ERROR", "statusMessage": "Failed with code 500"},
        ],
    }
    compacted = compact_trace(raw_trace)
    assert compacted["id"] == "tr_123"
    assert compacted["latency_sec"] == 3.142
    assert compacted["cost_usd"] == 0.00543
    assert compacted["models"] == ["claude-3-5"]
    assert "tool: Failed with code 500" in compacted["errors"]
