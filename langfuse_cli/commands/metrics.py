"""Aggregates from GET /api/public/v2/metrics: cost, tokens, latency, error counts and scores."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from langfuse_cli.client import LangfuseClient
from langfuse_cli.config import resolve_from_args
from langfuse_cli.formatters.agent import print_json

AGGREGATIONS = ("sum", "avg", "count", "max", "min", "p50", "p75", "p90", "p95", "p99")
# Measures where a sum means nothing; every other measure defaults to sum.
DEFAULT_AGGREGATION = {"count": "count", "value": "avg", "latency": "avg", "streamingLatency": "avg",
                       "timeToFirstToken": "avg", "outputTokensPerSecond": "avg", "tokensPerSecond": "avg"}
BOOLEAN_COLUMNS = {"isRootObservation"}
NUMBER_COLUMNS = {"promptVersion", "value"}
ARRAY_COLUMNS = {"tags"}


def parse_metrics(spec: str) -> List[Dict[str, str]]:
    """'totalCost:sum,count' -> API metric objects; a measure without ':agg' gets its default aggregation."""
    metrics = []
    for item in filter(None, (part.strip() for part in spec.split(","))):
        measure, _, aggregation = item.partition(":")
        aggregation = aggregation or DEFAULT_AGGREGATION.get(measure, "sum")
        if aggregation not in AGGREGATIONS:
            raise ValueError(f"unknown aggregation '{aggregation}' in --metric; use one of {', '.join(AGGREGATIONS)}")
        metrics.append({"measure": measure, "aggregation": aggregation})
    if not metrics:
        raise ValueError("--metric needs at least one measure, e.g. totalCost:sum")
    return metrics


def parse_filter(expr: str) -> Dict[str, Any]:
    """'level=ERROR' -> an API filter, typed by column."""
    column, _, value = expr.partition("=")
    if not column or not value:
        raise ValueError(f"--where needs column=value, got '{expr}'")
    if column in BOOLEAN_COLUMNS:
        if value.lower() not in ("true", "false"):
            raise ValueError(f"--where {column} takes true or false, got '{value}'")
        return {"column": column, "operator": "=", "value": value.lower() == "true", "type": "boolean"}
    if column in ARRAY_COLUMNS:
        return {"column": column, "operator": "any of", "value": [value], "type": "arrayOptions"}
    if column in NUMBER_COLUMNS:
        try:
            number: Any = int(value) if value.lstrip("-").isdigit() else float(value)
        except ValueError:
            raise ValueError(f"--where {column} takes a number, got '{value}'") from None
        return {"column": column, "operator": "=", "value": number, "type": "number"}
    return {"column": column, "operator": "=", "value": value, "type": "string"}


def row_limit(text: str) -> int:
    value = int(text) if text.isdigit() else 0
    if not 1 <= value <= 1000:
        raise argparse.ArgumentTypeError("must be a number from 1 to 1000")
    return value


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_query(args: argparse.Namespace) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    query: Dict[str, Any] = {
        "view": args.view,
        "metrics": parse_metrics(args.metric),
        "dimensions": [{"field": d.strip()} for d in (args.by or "").split(",") if d.strip()],
        "filters": [parse_filter(expr) for expr in args.where or []],
        "fromTimestamp": args.from_ts or _iso(now - timedelta(hours=24)),
        "toTimestamp": args.to_ts or _iso(now),
        # A time series needs every bucket (a week in hours is 168); the API returns only 100 rows by default.
        "config": {"row_limit": args.limit or (1000 if args.granularity else 100)},
    }
    if args.granularity:
        query["timeDimension"] = {"granularity": args.granularity}
    if args.order_by:
        field, _, direction = args.order_by.partition(":")
        query["orderBy"] = [{"field": field, "direction": direction or "desc"}]
    return query


def _table(rows: List[Dict[str, Any]]) -> str:
    columns = list(dict.fromkeys(k for row in rows for k in row))
    cells = [["-" if row.get(c) is None else str(row[c]) for c in columns] for row in rows]
    lines = [columns, *cells]
    widths = [max(len(v) for v in column) for column in zip(*lines)]
    return "\n".join("  ".join(v.ljust(w) for v, w in zip(line, widths)).rstrip() for line in lines)


def handle_metrics(args: argparse.Namespace) -> int:
    try:
        query = build_query(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    rows = LangfuseClient(resolve_from_args(args)).metrics(query).get("data", [])
    window = f"{query['fromTimestamp']} to {query['toTimestamp']}"
    if not args.from_ts and not args.to_ts:  # the default window is easy to miss in the rows
        print(f"lf: metrics for the last 24 hours ({window}); pass --from-ts for a longer range.", file=sys.stderr)
    limit = query["config"]["row_limit"]
    if len(rows) >= limit:
        print(f"lf: the result has {limit} rows, the --limit; more rows may exist. Narrow the time range or the "
              "groups, or raise --limit (up to 1000).", file=sys.stderr)
    if args.output == "json":
        print_json(args, rows)
    else:
        print(_table(rows) if rows else f"No data from {window}.")
    return 0
