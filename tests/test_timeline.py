from helpers import load_fixture

from langfuse_cli.formatters.timeline import render_trace_timeline


def observations():
    return load_fixture("obs_trace")["data"]  # GENERATION, TOOL (ERROR), AGENT root — API order


def test_timeline_nests_children_under_root():
    out = render_trace_timeline("t1", observations())

    assert out.splitlines() == [
        "Trace t1: 3 observations, 1 error",
        "✓ AGENT support-agent-turn [1ms]",
        "  ✓ GENERATION plan-step [0ms] (model: gpt-4o-mini)",
        "  ✗ [ERROR] TOOL search_tool_call [0ms]",
        "      Message: 503 Service Unavailable",
    ]


def test_timeline_orphan_parent_is_treated_as_root():
    root = observations()[2]
    orphan = {**root, "parentObservationId": "not-in-this-response"}

    assert render_trace_timeline("t1", [orphan]).splitlines()[1] == "✓ AGENT support-agent-turn [1ms]"


def test_timeline_shows_only_short_io():
    root = observations()[2]
    rows = [{**root, "input": "hello", "output": "x" * 500}]

    lines = render_trace_timeline("t1", rows).splitlines()

    assert "    Input: hello" in lines
    assert not any(line.lstrip().startswith("Output:") for line in lines)
