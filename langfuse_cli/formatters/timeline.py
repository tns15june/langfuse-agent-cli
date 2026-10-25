"""Terminal visualizer and timeline renderer for Langfuse traces."""
from __future__ import annotations

from typing import Any, Dict, List

MARKS = {"ERROR": "✗ [ERROR]", "WARNING": "⚠ [WARN]"}


def format_duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def render_trace_timeline(trace_id: str, observations: List[Dict[str, Any]]) -> str:
    """One trace as an observation tree: children under their parent, siblings by start time."""
    ids = {o.get("id") for o in observations}
    children: Dict[Any, List[Dict[str, Any]]] = {}
    roots = []
    for obs in sorted(observations, key=lambda o: o.get("startTime") or ""):
        parent = obs.get("parentObservationId")
        if parent in ids:
            children.setdefault(parent, []).append(obs)
        else:
            roots.append(obs)  # no parent, or the parent is not part of this response

    errors = sum(1 for o in observations if o.get("level") == "ERROR")
    lines = [f"Trace {trace_id}: {len(observations)} observations, {errors} error{'' if errors == 1 else 's'}"]

    def walk(obs: Dict[str, Any], depth: int) -> None:
        indent = "  " * depth
        level = obs.get("level") or "DEFAULT"
        line = f"{indent}{MARKS.get(level, '✓')} {obs.get('type') or 'SPAN'} {obs.get('name') or 'unnamed'}"
        if obs.get("latency") is not None:
            line += f" [{format_duration(float(obs['latency']))}]"
        if obs.get("model"):
            line += f" (model: {obs['model']})"
        lines.append(line)
        if level in MARKS and obs.get("statusMessage"):
            lines.append(f"{indent}    Message: {obs['statusMessage']}")
        for key in ("input", "output"):
            value = obs.get(key)
            if isinstance(value, str) and value.strip() and len(value) < 120:
                lines.append(f"{indent}    {key.capitalize()}: {value.strip()}")
        for child in children.get(obs.get("id"), []):
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)
    return "\n".join(lines)
