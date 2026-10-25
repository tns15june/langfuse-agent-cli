import json
from datetime import datetime, timedelta, timezone

import pytest

from langfuse_cli.cli import main
from langfuse_cli.commands.metrics import parse_filter, parse_metrics

METRICS = "/api/public/v2/metrics"
FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
WEEK = ["--from-ts", "2026-10-18T00:00:00Z", "--to-ts", "2026-10-25T00:00:00Z"]


def run(capsys, *argv):
    code = main([*argv, *FLAGS])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def sent_query(fake_api):
    return json.loads(fake_api.calls[-1][2]["query"])


def test_spend_by_model(fake_api, capsys):
    rows = [{"providedModelName": "gpt-4o-mini", "sum_totalCost": 0.0074}]
    fake_api.route("GET", METRICS, json={"data": rows})

    code, out, _ = run(capsys, "metrics", "--metric", "totalCost", "--by", "providedModelName", *WEEK)

    assert code == 0
    assert json.loads(out) == rows
    assert sent_query(fake_api) == {
        "view": "observations",
        "metrics": [{"measure": "totalCost", "aggregation": "sum"}],
        "dimensions": [{"field": "providedModelName"}],
        "filters": [],
        "fromTimestamp": "2026-10-18T00:00:00Z",
        "toTimestamp": "2026-10-25T00:00:00Z",
        "config": {"row_limit": 100},
    }


def test_default_aggregations_follow_the_measure():
    assert parse_metrics("count,latency,value,totalTokens,latency:p95") == [
        {"measure": "count", "aggregation": "count"},
        {"measure": "latency", "aggregation": "avg"},
        {"measure": "value", "aggregation": "avg"},
        {"measure": "totalTokens", "aggregation": "sum"},
        {"measure": "latency", "aggregation": "p95"},
    ]


def test_unknown_aggregation_fails_before_any_request(fake_api, capsys):
    code, _, err = run(capsys, "metrics", "--metric", "totalCost:median")

    assert code == 1
    assert "median" in err and "p95" in err
    assert fake_api.calls == []


@pytest.mark.parametrize("expr,expected", [
    ("level=ERROR", {"column": "level", "operator": "=", "value": "ERROR", "type": "string"}),
    ("isRootObservation=true", {"column": "isRootObservation", "operator": "=", "value": True, "type": "boolean"}),
    ("isRootObservation=false", {"column": "isRootObservation", "operator": "=", "value": False, "type": "boolean"}),
    ("isRootObservation=TRUE", {"column": "isRootObservation", "operator": "=", "value": True, "type": "boolean"}),
    ("value=0.5", {"column": "value", "operator": "=", "value": 0.5, "type": "number"}),
    ("tags=beta", {"column": "tags", "operator": "any of", "value": ["beta"], "type": "arrayOptions"}),
    ("promptVersion=3", {"column": "promptVersion", "operator": "=", "value": 3, "type": "number"}),
    ("name=a=b", {"column": "name", "operator": "=", "value": "a=b", "type": "string"}),
])
def test_filters_are_typed(expr, expected):
    assert parse_filter(expr) == expected


def test_filter_without_a_value_fails_before_any_request(fake_api, capsys):
    code, _, err = run(capsys, "metrics", "--where", "level")

    assert code == 1
    assert "--where" in err
    assert fake_api.calls == []


def test_errors_per_hour_ordered_and_limited(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    run(capsys, "metrics", "--metric", "count", "--where", "level=ERROR", "--where", "name=search_tool_call",
        "--granularity", "hour", "--order-by", "count_count", "--limit", "5", *WEEK)

    query = sent_query(fake_api)
    assert [f["column"] for f in query["filters"]] == ["level", "name"]
    assert query["timeDimension"] == {"granularity": "hour"}
    assert query["orderBy"] == [{"field": "count_count", "direction": "desc"}]
    assert query["config"] == {"row_limit": 5}


def test_order_by_can_be_ascending(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    run(capsys, "metrics", "--metric", "latency:p95", "--by", "name", "--order-by", "p95_latency:asc", *WEEK)

    assert sent_query(fake_api)["orderBy"] == [{"field": "p95_latency", "direction": "asc"}]


def test_default_window_is_the_last_24_hours(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    run(capsys, "metrics")

    query = sent_query(fake_api)
    start = datetime.fromisoformat(query["fromTimestamp"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(query["toTimestamp"].replace("Z", "+00:00"))
    assert end - start == timedelta(hours=24)
    assert abs(datetime.now(timezone.utc) - end) < timedelta(minutes=1)
    assert query["metrics"] == [{"measure": "count", "aggregation": "count"}]


def test_scores_view(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": [{"name": "accuracy", "avg_value": 0.8}]})

    run(capsys, "metrics", "--view", "scores-numeric", "--metric", "value", "--by", "name", *WEEK)

    query = sent_query(fake_api)
    assert query["view"] == "scores-numeric"
    assert query["metrics"] == [{"measure": "value", "aggregation": "avg"}]


def test_text_output_is_an_aligned_table(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": [{"name": "search_tool_call", "count_count": 12},
                                                  {"name": "plan-step", "count_count": None}]})

    _, out, _ = run(capsys, "metrics", "--by", "name", "-o", "text", *WEEK)

    assert out.splitlines() == [
        "name              count_count",
        "search_tool_call  12",
        "plan-step         -",
    ]


def test_text_output_without_rows(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    _, out, _ = run(capsys, "metrics", "-o", "text", *WEEK)

    assert out.strip().startswith("No data from ")


def test_server_error_detail_reaches_the_user(fake_api, capsys):
    fake_api.route("GET", METRICS, status=400, json={
        "message": "Invalid request data",
        "error": [{"message": 'Invalid option: expected one of "observations"|"scores-numeric"'}],
    })

    code, _, err = run(capsys, "metrics", "--metric", "count", *WEEK)

    assert code == 1
    assert "Invalid request data" in err and "expected one of" in err
    assert err.count("\n") == 1


@pytest.mark.parametrize("limit", ["0", "1001", "x"])
def test_limit_outside_1_to_1000_is_rejected(fake_api, limit):
    with pytest.raises(SystemExit) as exc:
        main(["metrics", "--limit", limit, *FLAGS])
    assert exc.value.code == 2


def test_time_series_default_to_the_largest_row_limit(fake_api, capsys):
    # A week in hours is 168 buckets: at the API's 100-row default the newest hours went missing.
    fake_api.route("GET", METRICS, json={"data": []})

    run(capsys, "metrics", "--where", "level=ERROR", "--granularity", "hour", *WEEK)

    assert sent_query(fake_api)["config"] == {"row_limit": 1000}


def test_an_explicit_limit_wins_over_the_time_series_default(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    run(capsys, "metrics", "--granularity", "hour", "--limit", "50", *WEEK)

    assert sent_query(fake_api)["config"] == {"row_limit": 50}


def test_a_result_at_the_row_limit_warns_that_rows_may_be_missing(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": [{"name": f"step-{i}", "count_count": 1} for i in range(5)]})

    code, out, err = run(capsys, "metrics", "--by", "name", "--limit", "5", *WEEK)

    assert code == 0
    assert len(json.loads(out)) == 5
    assert "5 rows" in err and "--limit" in err


def test_a_result_under_the_row_limit_does_not_warn(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": [{"name": "a", "count_count": 1}]})

    _, _, err = run(capsys, "metrics", "--by", "name", *WEEK)

    assert err == ""


@pytest.mark.parametrize("expr,needs", [("isRootObservation=yes", "true or false"), ("promptVersion=abc", "a number")])
def test_filter_values_of_the_wrong_kind_fail_before_any_request(fake_api, capsys, expr, needs):
    code, _, err = run(capsys, "metrics", "--where", expr)

    assert code == 1
    assert f"--where {expr.split('=')[0]}" in err and needs in err
    assert fake_api.calls == []


def test_metric_spec_tolerates_spaces_and_trailing_commas():
    assert parse_metrics(" count , latency:p95 ,") == [
        {"measure": "count", "aggregation": "count"}, {"measure": "latency", "aggregation": "p95"}]


def test_empty_metric_spec_fails_before_any_request(fake_api, capsys):
    code, _, err = run(capsys, "metrics", "--metric", " , ")

    assert code == 1 and "--metric" in err
    assert fake_api.calls == []


@pytest.mark.parametrize("limit", ["1", "1000"])
def test_limit_boundaries_are_accepted(fake_api, capsys, limit):
    fake_api.route("GET", METRICS, json={"data": []})

    assert run(capsys, "metrics", "--limit", limit, *WEEK)[0] == 0
    assert sent_query(fake_api)["config"] == {"row_limit": int(limit)}


def test_default_window_is_named_on_stderr(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    _, out, err = run(capsys, "metrics")

    assert json.loads(out) == []
    assert "last 24 hours" in err and "--from-ts" in err


def test_an_explicit_window_is_not_announced(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": [{"count_count": 1}]})

    _, _, err = run(capsys, "metrics", *WEEK)

    assert err == ""


def test_empty_text_output_names_the_window(fake_api, capsys):
    fake_api.route("GET", METRICS, json={"data": []})

    _, out, _ = run(capsys, "metrics", "-o", "text", *WEEK)

    assert out.strip() == "No data from 2026-10-18T00:00:00Z to 2026-10-25T00:00:00Z."


@pytest.mark.parametrize("body", [
    {"message": "Prompt not found", "error": "LangfuseNotFoundError"},  # Langfuse's typed errors: a string
    {"message": "Prompt not found", "error": []},
    {"message": "Prompt not found", "error": ["x"]},
    {"message": "Prompt not found", "error": [{"code": 1}]},
    {"message": "Prompt not found", "error": [{"message": ""}]},
    {"message": "Prompt not found"},
], ids=["string", "empty-list", "list-of-str", "dict-without-message", "empty-detail", "no-error-key"])
def test_error_bodies_without_a_usable_detail_keep_the_message(fake_api, capsys, body):
    fake_api.route("GET", METRICS, status=404, json=body)

    code, _, err = run(capsys, "metrics", *WEEK)

    assert code == 1
    assert err == "Error: HTTP 404: Prompt not found\n"
