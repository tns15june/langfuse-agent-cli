"""Token-efficient output formatters for AI coding assistants."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def extract_field_path(data: Any, path: str) -> Any:
    """Value at a dotted path like 'usageDetails.input'; a list on the way maps the rest over its items."""
    if isinstance(data, list):
        return [extract_field_path(item, path) for item in data]
    if not isinstance(data, dict):
        return None
    head, _, rest = path.partition(".")
    value = data.get(head)
    return extract_field_path(value, rest) if rest else value


def filter_dict_fields(item: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields:
        val = extract_field_path(item, f)
        if val is not None:
            out[f] = val
    return out


def prune(data: Any) -> Any:
    """Drop None, "", [] and {} values at every level; this is what --compact does."""
    empty = (None, "", [], {})
    if isinstance(data, dict):
        pruned = {k: prune(v) for k, v in data.items()}
        return {k: v for k, v in pruned.items() if v not in empty}
    if isinstance(data, list):
        return [v for v in map(prune, data) if v not in empty]
    return data


def compact_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    """Produces a minimal, high-signal summary of a Langfuse trace."""
    latency = None
    if trace.get("latency") is not None:
        latency = round(float(trace["latency"]), 3)
    elif trace.get("duration") is not None:
        latency = round(float(trace["duration"]), 3)

    cost = None
    if trace.get("totalCost") is not None:
        cost = round(float(trace["totalCost"]), 5)

    res: Dict[str, Any] = {
        "id": trace.get("id"),
        "name": trace.get("name"),
        "timestamp": trace.get("timestamp"),
        "latency_sec": latency,
        "cost_usd": cost,
        "sessionId": trace.get("sessionId"),
        "userId": trace.get("userId"),
        "tags": trace.get("tags") or [],
    }

    # Inspect observations for errors or key model details
    observations = trace.get("observations") or []
    errors = []
    models_used = set()
    for obs in observations:
        if isinstance(obs, dict):
            if obs.get("level") == "ERROR" or obs.get("statusMessage"):
                err_text = obs.get("statusMessage") or obs.get("name")
                if err_text:
                    errors.append(f"{obs.get('name')}: {err_text}")
            if obs.get("model"):
                models_used.add(obs["model"])

    if errors:
        res["errors"] = errors
    if models_used:
        res["models"] = list(models_used)

    return {k: v for k, v in res.items() if v is not None}


def format_agent_output(
    data: Any,
    compact: bool = False,
    agent_fields: Optional[str] = None,
) -> str:
    """JSON for agents: optional field projection (applied to each list item), then optional pruning."""
    if agent_fields:
        fields = [f.strip() for f in agent_fields.split(",") if f.strip()]
        if isinstance(data, list):
            data = [filter_dict_fields(d, fields) for d in data if isinstance(d, dict)]
        elif isinstance(data, dict):
            data = filter_dict_fields(data, fields)
    if compact:
        data = prune(data)
    return json.dumps(data, indent=2, ensure_ascii=False)
