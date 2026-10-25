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

    assert out.strip() == "No data in this time range."


def test_server_error_detail_reaches_the_user(fake_api, capsys):
    fake_api.route("GET", METRICS, status=400, json={
        "message": "Invalid request data",
        "error": [{"message": 'Invalid option: expected one of "observations"|"scores-numeric"'}],
    })

    code, _, err = run(capsys, "metrics", "--metric", "count", *WEEK)

    assert code == 1
    assert "Invalid request data" in err and "expected one of" in err


@pytest.mark.parametrize("limit", ["0", "1001", "x"])
def test_limit_outside_1_to_1000_is_rejected(limit):
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
