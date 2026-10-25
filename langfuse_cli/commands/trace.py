"""Trace and observability commands for Langfuse."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Dict, Any, Optional

from langfuse_cli.client import LangfuseClient, LangfuseAPIError
from langfuse_cli.config import resolve_from_args
from langfuse_cli.formatters.agent import format_agent_output, compact_trace
from langfuse_cli.formatters.timeline import render_trace_timeline


def handle_trace(args: argparse.Namespace) -> int:
    prof = resolve_from_args(args)
    client = LangfuseClient(prof)
    action = getattr(args, "trace_action", "list")
    out_format = getattr(args, "output", "json")
    compact = getattr(args, "compact", False)
    agent_fields = getattr(args, "agent_fields", None)

    try:
        if action == "list":
            limit = getattr(args, "limit", 20)
            session_id = getattr(args, "session_id", None)
            user_id = getattr(args, "user_id", None)
            from_ts = getattr(args, "from_ts", None)
            to_ts = getattr(args, "to_ts", None)

            res = client.list_traces(
                limit=limit,
                session_id=session_id,
                user_id=user_id,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            traces = res.get("data", [])

            # Filter by status if requested (e.g. error)
            status_filter = getattr(args, "status", None)
            if status_filter == "error":
                filtered = []
                for t in traces:
                    ct = compact_trace(t)
                    if ct.get("errors"):
                        filtered.append(t)
                traces = filtered

            if out_format == "json":
                print(format_agent_output(traces, compact=compact, agent_fields=agent_fields))
            else:
                if not traces:
                    print("No traces found matching criteria.")
                    return 0
                print(f"Traces ({len(traces)}):")
                for t in traces:
                    tid = t.get("id")
                    tname = t.get("name", "unnamed")
                    ts = t.get("timestamp", "N/A")
                    lat = t.get("latency") or t.get("duration")
                    lat_str = f" ({float(lat):.2f}s)" if lat else ""
                    print(f"  - [{tid}] {tname}{lat_str} @ {ts}")
            return 0

        elif action == "get":
            trace_id = args.trace_id
            trace = client.get_trace(trace_id=trace_id)

            if getattr(args, "timeline", False) or out_format == "text":
                print(render_trace_timeline(trace))
            else:
                print(format_agent_output(trace, compact=compact, agent_fields=agent_fields))
            return 0

        elif action == "session":
            session_id = args.session_id
            # Fetch session metadata and associated traces
            session_meta = {}
            try:
                session_meta = client.get_session(session_id)
            except Exception:
                pass
            traces_res = client.list_traces(session_id=session_id, limit=50)
            traces = traces_res.get("data", [])

            payload = {
                "sessionId": session_id,
                "session": session_meta,
                "traces_count": len(traces),
                "traces": [compact_trace(t) for t in traces] if compact else traces,
            }

            if out_format == "json":
                print(json.dumps(payload, indent=2))
            else:
                print(f"Session: {session_id} ({len(traces)} traces recorded)")
                for t in traces:
                    print(f"  - [{t.get('id')}] {t.get('name')} @ {t.get('timestamp')}")
            return 0

    except LangfuseAPIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        return 1

    return 0
