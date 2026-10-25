import json
import os
import stat
from pathlib import Path

from helpers import load_fixture

from langfuse_cli.cli import main

OBS = "/api/public/v2/observations"
FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
TRACE_ID = "487b674e9a38e8d85cd683d2f022bf1d"


def run(capsys, *argv):
    code = main([*argv, *FLAGS])
    return code, capsys.readouterr().out


def big_trace(rows=None):
    """A trace response well over 16 KB, made by repeating the recorded rows."""
    return {"data": (rows or load_fixture("obs_trace")["data"]) * 10, "meta": {}}


def test_large_json_is_written_to_a_file(fake_api, capsys):
    fake_api.route("GET", OBS, json=big_trace())

    _, plain = run(capsys, "trace", "get", TRACE_ID)
    code, out = run(capsys, "trace", "get", TRACE_ID, "--output-summary")

    envelope = json.loads(out)
    path = Path(envelope["outputFile"])
    assert code == 0
    assert envelope["summary"] is True
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(plain)
    assert envelope["bytes"] == path.stat().st_size
    assert envelope["rows"] == 30
    assert "id" in envelope["rowKeys"]
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_small_json_is_unchanged(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_trace"))

    _, plain = run(capsys, "trace", "get", TRACE_ID)
    _, summarized = run(capsys, "trace", "get", TRACE_ID, "--output-summary")

    assert summarized == plain


def test_size_is_measured_after_agent_fields(fake_api, capsys):
    fake_api.route("GET", OBS, json=big_trace())

    _, out = run(capsys, "trace", "get", TRACE_ID, "--agent-fields", "id", "--output-summary")

    assert isinstance(json.loads(out), list)


def test_object_summary_lists_keys(fake_api, capsys):
    items = load_fixture("dataset_items")
    fake_api.route("GET", "/api/public/v2/datasets/intent-classification-evals", json=load_fixture("dataset_get"))
    fake_api.route("GET", "/api/public/dataset-items", json={**items, "data": items["data"] * 20})

    _, out = run(capsys, "dataset", "get", "intent-classification-evals", "--output-summary")

    envelope = json.loads(out)
    assert envelope["summary"] is True
    assert "items" in envelope["keys"]
    assert "rows" not in envelope


def test_file_escapes_control_characters(fake_api, capsys):
    rows = load_fixture("obs_trace")["data"]
    fake_api.route("GET", OBS, json=big_trace([{**rows[0], "name": "bad\x9bname"}, *rows[1:]]))

    _, out = run(capsys, "trace", "get", TRACE_ID, "--output-summary")

    text = Path(json.loads(out)["outputFile"]).read_text(encoding="utf-8")
    assert "\\u009b" in text and "\x9b" not in text
    assert "bad\x9bname" in [row["name"] for row in json.loads(text)]


def test_text_output_is_never_summarized(fake_api, capsys):
    roots = load_fixture("obs_roots")
    fake_api.route("GET", OBS, json={**roots, "data": roots["data"] * 3})

    _, out = run(capsys, "trace", "list", "-o", "text", "--output-summary")

    assert out.startswith("  - [")
