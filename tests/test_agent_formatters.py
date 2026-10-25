import json

from helpers import load_fixture

from langfuse_cli.formatters.agent import format_agent_output, prune


def test_prune_drops_empty_values():
    data = {"a": None, "b": "", "c": [], "d": {"e": None}, "f": 0, "g": False}

    assert prune(data) == {"f": 0, "g": False}


def test_compact_prunes_each_row():
    rows = load_fixture("obs_trace")["data"]

    out = json.loads(format_agent_output(rows, compact=True))

    assert "statusMessage" not in out[0]  # "" on a DEFAULT-level row
    assert out[1]["statusMessage"] == "503 Service Unavailable"
    assert "completionStartTime" not in out[0]  # null in the recorded response


def test_agent_fields_apply_per_list_item():
    rows = load_fixture("obs_trace")["data"]

    out = json.loads(format_agent_output(rows, agent_fields="name,level"))

    assert out == [
        {"name": "plan-step", "level": "DEFAULT"},
        {"name": "search_tool_call", "level": "ERROR"},
        {"name": "support-agent-turn", "level": "DEFAULT"},
    ]


def test_compact_projection_keeps_one_entry_per_row():
    rows = load_fixture("obs_trace")["data"]

    out = json.loads(format_agent_output(rows, compact=True, agent_fields="nonexistent"))

    assert out == [{}, {}, {}]  # [] would read as "no rows" to an agent


def test_agent_fields_traverse_lists():
    data = {"obs": [{"name": "x"}, {"name": "y"}]}

    assert json.loads(format_agent_output(data, agent_fields="obs.name")) == {"obs.name": ["x", "y"]}
