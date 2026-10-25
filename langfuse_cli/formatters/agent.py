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
        # Prune inside each row but keep the rows: dropping emptied rows would print [] for real results.
        data = [prune(row) for row in data] if isinstance(data, list) else prune(data)
    return json.dumps(data, indent=2, ensure_ascii=False)
