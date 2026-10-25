"""Checks against a real Langfuse seeded by scripts/seed_langfuse.py. Skipped unless LF_LIVE=1."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from langfuse_cli.cli import main
from langfuse_cli.formatters import agent

pytestmark = pytest.mark.skipif(not os.environ.get("LF_LIVE"),
                                reason="set LF_LIVE=1 with LANGFUSE_* pointing at a seeded instance")

# Read once at import: the autouse isolated_config fixture removes LANGFUSE_* before each test.
FLAGS = [
    "--host", os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST", ""),
    "--public-key", os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
    "--secret-key", os.environ.get("LANGFUSE_SECRET_KEY", ""),
]
SEEDED_ERRORS = {"503 Service Unavailable", "timeout after 30s"}


def run(capsys, *argv):
    code = main([*argv, *FLAGS])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def run_json(capsys, *argv):
    code, out, err = run(capsys, *argv)
    assert code == 0, err
    return json.loads(out)


def test_doctor_passes(capsys):
    code, out, _ = run(capsys, "doctor")
    assert code == 0, out


def test_trace_list_returns_traces(capsys):
    assert run_json(capsys, "trace", "list", "--limit", "5")


def test_status_error_finds_seeded_failures(capsys):
    groups = run_json(capsys, "trace", "list", "--status", "error", "--limit", "10")
    assert any(e["statusMessage"] in SEEDED_ERRORS for g in groups for e in g["errors"])


def test_trace_get_timeline_marks_the_error(capsys):
    trace_id = run_json(capsys, "trace", "list", "--status", "error", "--limit", "1")[0]["traceId"]
    code, out, _ = run(capsys, "trace", "get", trace_id, "--timeline")
    assert code == 0
    assert "✗ [ERROR]" in out


def test_output_summary_writes_the_trace_to_a_file(capsys, monkeypatch):
    monkeypatch.setattr(agent, "SUMMARY_THRESHOLD_BYTES", 1024)  # a seeded trace with --io is about 12 KB
    trace_id = run_json(capsys, "trace", "list", "--status", "error", "--limit", "1")[0]["traceId"]

    envelope = run_json(capsys, "trace", "get", trace_id, "--io", "--output-summary")

    rows = json.loads(Path(envelope["outputFile"]).read_text(encoding="utf-8"))
    assert envelope["summary"] is True
    assert len(rows) == envelope["rows"]
    assert {"input", "output"} <= set(envelope["rowKeys"])


def test_metrics_counts_observations_by_type(capsys):
    start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = run_json(capsys, "metrics", "--metric", "count", "--by", "type", "--from-ts", start)
    assert rows and all("count_count" in row for row in rows)


def test_metrics_reports_a_bad_view_with_the_server_detail(capsys):
    code, _, err = run(capsys, "metrics", "--view", "observations", "--metric", "notAMeasure")
    assert code == 1 and err.startswith("Error: HTTP 400")


def test_trace_session_lists_its_traces(capsys):
    assert run_json(capsys, "trace", "session", "sess-a")


def test_prompt_get_with_folder_name(capsys):
    assert run_json(capsys, "prompt", "get", "support/greeter")["name"] == "support/greeter"


def test_prompt_get_compiles_variables(capsys):
    prompt = run_json(capsys, "prompt", "get", "welcome-bot", "--vars", '{"user_name": "A", "plan": "pro"}')
    assert prompt["compiled_prompt"] == "Hello A, welcome to the pro plan!"


def test_dataset_get_includes_items(capsys):
    assert len(run_json(capsys, "dataset", "get", "intent-classification-evals")["items"]) >= 3


def test_score_create_returns_id(capsys):
    trace_id = run_json(capsys, "trace", "list", "--limit", "1")[0]["traceId"]
    assert run_json(capsys, "score", "create", "--trace-id", trace_id, "--name", "live-test", "--value", "1")["id"]


def test_prompt_push_creates_a_version(capsys):
    created = run_json(capsys, "prompt", "push", "live-test-push", "--text", "Hi {{user_name}}", "--labels", "staging")
    assert created["version"] >= 1
