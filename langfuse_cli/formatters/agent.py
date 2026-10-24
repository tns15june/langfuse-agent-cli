"""Token-efficient output formatters for AI coding assistants."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def extract_field_path(data: Any, path: str) -> Any:
    """Extract nested value like 'user.name' or 'status.category'."""
    parts = path.split(".")
    curr = data
    for p in parts:
        if isinstance(curr, dict):
            curr = curr.get(p)
        else:
            return None
    return curr


def filter_dict_fields(item: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields:
        val = extract_field_path(item, f)
        if val is not None:
            out[f] = val
    return out


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


def compact_prompt(prompt: Dict[str, Any]) -> Dict[str, Any]:
    """Produces a concise summary of a prompt."""
    return {
        "name": prompt.get("name"),
        "version": prompt.get("version"),
        "type": prompt.get("type", "text"),
        "labels": prompt.get("labels") or [],
        "tags": prompt.get("tags") or [],
        "updatedAt": prompt.get("updatedAt"),
        "prompt": prompt.get("prompt"),
        "config": prompt.get("config") or {},
    }


def format_agent_output(
    data: Any,
    output_format: str = "json",
    compact: bool = False,
    agent_fields: Optional[str] = None,
) -> str:
    """Formats data for agent ingestion."""
    if output_format == "json":
        if agent_fields and isinstance(data, list):
            fields_list = [f.strip() for f in agent_fields.split(",")]
            data = [filter_dict_fields(d, fields_list) for d in data if isinstance(d, dict)]
        elif compact:
            if isinstance(data, list):
                # Check what type of list
                if data and "timestamp" in data[0] and "id" in data[0]:
                    data = [compact_trace(d) for d in data]
                elif data and "prompt" in data[0]:
                    data = [compact_prompt(d) for d in data]
            elif isinstance(data, dict):
                if "timestamp" in data and "id" in data:
                    data = compact_trace(data)
                elif "prompt" in data and "name" in data:
                    data = compact_prompt(data)

        return json.dumps(data, indent=2, ensure_ascii=False)

    # Text fallback
    return str(data)
