"""Trace commands, read through the observations v2 API (the only trace read path on Langfuse v4)."""
from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, Iterable, List

from langfuse_cli.client import LangfuseClient
from langfuse_cli.config import resolve_from_args
from langfuse_cli.formatters.agent import format_agent_output
from langfuse_cli.formatters.timeline import render_trace_timeline

# Field groups of GET /api/public/v2/observations. "metrics" carries latency; the spec puts it there.
ROOT_FIELDS = "core,basic,metrics"  # a trace is listed as its root observation
TREE_FIELDS = "core,basic,time,model,usage,metrics"  # leaves out io (--io adds it), metadata, prompt, trace_context


def group_errors(observations: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """ERROR observations grouped by trace in first-seen order, at most `limit` traces."""
    groups: Dict[Any, Dict[str, Any]] = {}
    for obs in observations:
        trace_id = obs.get("traceId")
        if trace_id not in groups:
            if len(groups) == limit:
                break  # stops the lazy page iterator too
            groups[trace_id] = {"traceId": trace_id, "sessionId": obs.get("sessionId"),
                                "userId": obs.get("userId"), "errors": []}
        groups[trace_id]["errors"].append({k: obs.get(k) for k in ("id", "name", "type", "statusMessage", "startTime")})
    return list(groups.values())


def _trace_line(row: Dict[str, Any]) -> str:
    latency = f" ({float(row['latency']):.2f}s)" if row.get("latency") is not None else ""
    return f"  - [{row.get('traceId')}] {row.get('name') or 'unnamed'}{latency} @ {row.get('startTime')}"


def _emit(args: argparse.Namespace, rows: List[Dict[str, Any]], lines: List[str], empty: str) -> int:
    if args.output == "json":
        print(format_agent_output(rows, compact=args.compact, agent_fields=args.agent_fields))
    else:
        print("\n".join(lines) if lines else empty)
    return 0


def _by_start(obs: Dict[str, Any]) -> str:
    return obs.get("startTime") or ""


def handle_trace(args: argparse.Namespace) -> int:
    client = LangfuseClient(resolve_from_args(args))

    if args.trace_action == "list":
        filters = {"sessionId": args.session_id, "userId": args.user_id,
                   "fromStartTime": args.from_ts, "toStartTime": args.to_ts}
        if args.status == "error":
            # shortcut: scans at most 5000 error rows; raise the cap if busy projects need longer windows
            errors = client.iter_observations({**filters, "level": "ERROR", "fields": ROOT_FIELDS}, max_items=5000)
            rows = group_errors(errors, args.limit)
            lines = [f"  - [{g['traceId']}] {len(g['errors'])} error(s): "
                     + "; ".join(f"{e['name']}: {e['statusMessage']}" for e in g["errors"]) for g in rows]
            return _emit(args, rows, lines, "No traces with errors found.")
        rows = client.list_observations(**filters, isRootObservation=True, fields=ROOT_FIELDS, limit=args.limit)
        rows = rows.get("data", [])
        return _emit(args, rows, [_trace_line(r) for r in rows], "No traces found.")

    if args.trace_action == "get":
        fields = TREE_FIELDS + (",io" if args.io else "")
        observations = sorted(client.iter_observations({"traceId": args.trace_id, "fields": fields}), key=_by_start)
        if not observations:
            print(f"Error: trace {args.trace_id} not found", file=sys.stderr)
            return 1
        if args.timeline or args.output == "text":
            print(render_trace_timeline(args.trace_id, observations))
        else:
            print(format_agent_output(observations, compact=args.compact, agent_fields=args.agent_fields))
        return 0

    # session: its traces, oldest first, so a conversation reads top to bottom
    params = {"sessionId": args.session_id, "isRootObservation": True, "fields": ROOT_FIELDS}
    rows = sorted(client.iter_observations(params, max_items=1000), key=_by_start)
    return _emit(args, rows, [_trace_line(r) for r in rows], f"No traces in session {args.session_id}.")
