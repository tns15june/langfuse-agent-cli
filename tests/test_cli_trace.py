import json

from helpers import load_fixture

from langfuse_cli.cli import main
from langfuse_cli.commands.trace import group_errors

OBS = "/api/public/v2/observations"
FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
ERROR_TRACES = [
    "487b674e9a38e8d85cd683d2f022bf1d",
    "004541ddd1478534e00b85025cf0889e",
    "e32d9c049420961ffcc75c75ef1e4c1f",
    "f560c3a044b00c56eb3418c5998d6389",
]


def run(capsys, *argv):
    code = main([*argv, *FLAGS])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_trace_list_reads_root_observations(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_roots"))

    code, out, _ = run(capsys, "trace", "list", "--limit", "5")

    assert code == 0
    assert json.loads(out) == load_fixture("obs_roots")["data"]
    assert fake_api.calls[-1][2] == {"isRootObservation": "true", "fields": "core,basic,metrics", "limit": "5"}


def test_trace_list_maps_filters_to_v2_names(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_roots"))

    run(capsys, "trace", "list", "--session-id", "s1", "--user-id", "u1",
        "--from-ts", "2026-10-24T00:00:00Z", "--to-ts", "2026-10-25T00:00:00Z")

    params = fake_api.calls[-1][2]
    assert (params["sessionId"], params["userId"]) == ("s1", "u1")
    assert (params["fromStartTime"], params["toStartTime"]) == ("2026-10-24T00:00:00Z", "2026-10-25T00:00:00Z")


def test_status_error_groups_errors_by_trace(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_errors"))

    code, out, _ = run(capsys, "trace", "list", "--status", "error")

    groups = json.loads(out)
    assert code == 0
    assert [g["traceId"] for g in groups] == ERROR_TRACES
    assert [e["statusMessage"] for g in groups for e in g["errors"]] == [
        "503 Service Unavailable", "timeout after 30s", "503 Service Unavailable", "timeout after 30s"]
    params = fake_api.calls[-1][2]
    assert params["level"] == "ERROR"
    assert "isRootObservation" not in params  # errors usually sit on child observations


def test_status_error_text_names_each_failure(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_errors"))

    _, out, _ = run(capsys, "trace", "list", "--status", "error", "-o", "text")

    assert f"  - [{ERROR_TRACES[0]}] 1 error(s): search_tool_call: 503 Service Unavailable" in out.splitlines()


def test_group_errors_merges_per_trace_and_stops_at_limit():
    rows = [{"traceId": t, "name": n, "statusMessage": "boom"} for t, n in
            [("A", "a1"), ("A", "a2"), ("B", "b1"), ("C", "c1")]]

    groups = group_errors(iter(rows), limit=2)

    assert [(g["traceId"], [e["name"] for e in g["errors"]]) for g in groups] == [("A", ["a1", "a2"]), ("B", ["b1"])]


def test_trace_get_timeline_shows_error(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_trace"))

    code, out, _ = run(capsys, "trace", "get", ERROR_TRACES[0], "--timeline")

    assert code == 0
    assert "  ✗ [ERROR] TOOL search_tool_call [0ms]" in out.splitlines()
    assert fake_api.calls[-1][2]["traceId"] == ERROR_TRACES[0]
    assert fake_api.calls[-1][2]["fields"] == "core,basic,time,model,usage,metrics"


def test_trace_get_json_is_observations_in_start_order(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_trace"))

    _, out, _ = run(capsys, "trace", "get", ERROR_TRACES[0])

    assert [o["name"] for o in json.loads(out)] == ["support-agent-turn", "plan-step", "search_tool_call"]


def test_trace_get_io_requests_io_group(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_trace"))

    run(capsys, "trace", "get", ERROR_TRACES[0], "--io")

    assert fake_api.calls[-1][2]["fields"] == "core,basic,time,model,usage,metrics,io"


def test_trace_get_unknown_id_exits_1(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_empty"))

    code, out, err = run(capsys, "trace", "get", "does-not-exist")

    assert (code, out) == (1, "")
    assert "trace does-not-exist not found" in err


def test_trace_session_sorted_oldest_first(fake_api, capsys):
    fake_api.route("GET", OBS, json=load_fixture("obs_session"))  # API order: newest first

    code, out, _ = run(capsys, "trace", "session", "sess-a")

    assert code == 0
    assert [r["startTime"] for r in json.loads(out)] == [
        "2026-10-24T21:46:02.166Z", "2026-10-24T21:46:02.168Z", "2026-10-24T21:46:02.170Z", "2026-10-24T21:46:02.172Z"]
    params = fake_api.calls[-1][2]
    assert (params["sessionId"], params["isRootObservation"]) == ("sess-a", "true")
