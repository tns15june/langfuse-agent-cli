import io
import json
import os
import stat
from pathlib import Path

import pytest
from helpers import load_fixture

from langfuse_cli.cli import main
from langfuse_cli.formatters.agent import format_agent_output

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
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert list(envelope) == ["summary", "outputFile", "bytes", "rows", "rowKeys", "hint"]  # documented in OUTPUT.md


def test_small_json_is_unchanged(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_trace"))

    _, plain = run(capsys, "trace", "get", TRACE_ID)
    _, summarized = run(capsys, "trace", "get", TRACE_ID, "--output-summary")

    assert summarized == plain


def test_size_is_measured_after_agent_fields(fake_api, capsys):
    fake_api.route("GET", OBS, json=big_trace())

    _, out = run(capsys, "trace", "get", TRACE_ID, "--agent-fields", "id", "--output-summary")

    assert isinstance(json.loads(out), list)


def test_size_is_measured_after_compact(fake_api, capsys):
    fake_api.route("GET", OBS, json={"data": load_fixture("obs_trace")["data"] * 6, "meta": {}})

    _, plain = run(capsys, "trace", "get", TRACE_ID)
    _, out = run(capsys, "trace", "get", TRACE_ID, "--compact", "--output-summary")

    assert len(plain.encode("utf-8")) > 16 * 1024  # only --compact brings it under
    assert isinstance(json.loads(out), list)


def test_flag_before_the_subcommand(fake_api, capsys):
    fake_api.route("GET", OBS, json=big_trace())

    main(["--output-summary", "trace", "get", TRACE_ID, *FLAGS])

    assert json.loads(capsys.readouterr().out)["summary"] is True


PAD = "x" * (17 * 1024)


@pytest.mark.parametrize("argv,method,path,body", [
    (["trace", "list"], "GET", OBS, {"data": [{"traceId": "t1", "name": PAD}], "meta": {}}),
    (["trace", "list", "--status", "error"], "GET", OBS,
     {"data": [{"traceId": "t1", "name": "llm", "statusMessage": PAD}], "meta": {}}),
    (["trace", "session", "s1"], "GET", OBS, {"data": [{"traceId": "t1", "name": PAD}], "meta": {}}),
    (["prompt", "list"], "GET", "/api/public/v2/prompts", {"data": [{"name": PAD}]}),
    (["prompt", "get", "p"], "GET", "/api/public/v2/prompts/p", {"name": "p", "prompt": PAD}),
    (["prompt", "push", "p", "--text", "hi"], "POST", "/api/public/v2/prompts", {"name": "p", "prompt": PAD}),
    (["dataset", "list"], "GET", "/api/public/v2/datasets", {"data": [{"name": PAD}]}),
    (["score", "create", "--trace-id", "t1", "--name", "n", "--value", "1"], "POST", "/api/public/scores",
     {"id": "s1", "comment": PAD}),
], ids=["trace-list", "error-list", "session", "prompt-list", "prompt-get", "prompt-push", "dataset-list",
        "score-create"])
def test_every_json_command_honours_output_summary(fake_api, capsys, argv, method, path, body):
    fake_api.route(method, path, json=body)

    code, out = run(capsys, *argv, "--output-summary")

    envelope = json.loads(out)
    assert code == 0 and envelope["summary"] is True
    assert PAD in Path(envelope["outputFile"]).read_text(encoding="utf-8")


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


def test_failed_write_leaves_no_file(monkeypatch, tmp_path):
    class FullDisk(io.BytesIO):
        def write(self, data):
            raise OSError(28, "No space left on device")

    def fdopen(fd, *_args, **_kwargs):
        os.close(fd)
        return FullDisk()

    monkeypatch.setattr(os, "fdopen", fdopen)
    with pytest.raises(OSError):
        format_agent_output([{"name": PAD}], summary=True)
    assert list(tmp_path.glob("lf-*.json")) == []  # conftest points tempfile at tmp_path


def surrogate_trace(copies):
    """A recorded trace whose first observation name ends in half an emoji, as a JS app can produce."""
    rows = load_fixture("obs_trace")["data"]
    return {"data": [{**rows[0], "name": "cut \ud83d"}, *rows[1:]] * copies, "meta": {}}


def test_lone_surrogates_are_printed_escaped(fake_api, capsys):
    fake_api.route("GET", OBS, json=surrogate_trace(1))

    _, out = run(capsys, "trace", "get", TRACE_ID)

    assert "\\ud83d" in out
    assert "cut \ud83d" in [row["name"] for row in json.loads(out)]


def test_lone_surrogates_are_escaped_in_the_summary_file(fake_api, capsys):
    fake_api.route("GET", OBS, json=surrogate_trace(10))

    _, out = run(capsys, "trace", "get", TRACE_ID, "--output-summary")

    assert "\\ud83d" in Path(json.loads(out)["outputFile"]).read_text(encoding="utf-8")
