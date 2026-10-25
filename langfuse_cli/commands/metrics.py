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
    return metrics


def parse_filter(expr: str) -> Dict[str, Any]:
    """'level=ERROR' -> an API filter, typed by column."""
    column, sep, value = expr.partition("=")
    if not sep or not column or not value:
        raise ValueError(f"--where needs column=value, got '{expr}'")
    if column in BOOLEAN_COLUMNS:
        return {"column": column, "operator": "=", "value": value.lower() == "true", "type": "boolean"}
    if column in ARRAY_COLUMNS:
        return {"column": column, "operator": "any of", "value": [value], "type": "arrayOptions"}
    if column in NUMBER_COLUMNS:
        try:
            number: Any = int(value)
        except ValueError:
            number = float(value)
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
    now = datetime.now(timezone.utc).replace(microsecond=0)
    query: Dict[str, Any] = {
        "view": args.view,
        "metrics": parse_metrics(args.metric),
        "dimensions": [{"field": d.strip()} for d in (args.by or "").split(",") if d.strip()],
        "filters": [parse_filter(expr) for expr in args.where or []],
        "fromTimestamp": args.from_ts or _iso(now - timedelta(hours=24)),
        "toTimestamp": args.to_ts or _iso(now),
        "config": {"row_limit": args.limit},
    }
    if args.granularity:
        query["timeDimension"] = {"granularity": args.granularity}
    if args.order_by:
        field, _, direction = args.order_by.partition(":")
        query["orderBy"] = [{"field": field, "direction": direction or "desc"}]
    return query


def _table(rows: List[Dict[str, Any]]) -> str:
    columns = list(dict.fromkeys(k for row in rows for k in row))
    cells = [[("-" if row.get(c) is None else str(row.get(c))) for c in columns] for row in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(columns)]
    lines = [columns, *cells]
    return "\n".join("  ".join(v.ljust(w) for v, w in zip(line, widths)).rstrip() for line in lines)


def handle_metrics(args: argparse.Namespace) -> int:
    try:
        query = build_query(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    rows = LangfuseClient(resolve_from_args(args)).metrics(query).get("data", [])
    if args.output == "json":
        print_json(args, rows)
    else:
        print(_table(rows) if rows else "No data in this time range.")
    return 0
