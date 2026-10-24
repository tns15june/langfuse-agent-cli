"""Terminal visualizer and timeline renderer for Langfuse traces."""
from __future__ import annotations

from typing import Dict, Any, List


def format_duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def render_trace_timeline(trace: Dict[str, Any]) -> str:
    lines = []
    trace_id = trace.get("id", "unknown")
    name = trace.get("name", "unnamed")
    latency = trace.get("latency") or trace.get("duration")
    dur_str = f" ({format_duration(float(latency))})" if latency else ""
    cost = trace.get("totalCost")
    cost_str = f" [${float(cost):.4f}]" if cost else ""

    lines.append(f"Trace: {name} ({trace_id}){dur_str}{cost_str}")
    lines.append(f"Timestamp: {trace.get('timestamp', 'N/A')} | Session: {trace.get('sessionId', 'N/A')} | User: {trace.get('userId', 'N/A')}")
    if trace.get("tags"):
        lines.append(f"Tags: {', '.join(trace['tags'])}")

    observations: List[Dict[str, Any]] = trace.get("observations") or []
    if not observations:
        lines.append("  (No observations recorded in this trace)")
        return "\n".join(lines)

    lines.append("\nObservations Timeline:")
    # Sort observations by startTime if available
    sorted_obs = sorted(observations, key=lambda x: x.get("startTime") or "")

    for i, obs in enumerate(sorted_obs, 1):
        obs_type = obs.get("type", "SPAN")
        obs_name = obs.get("name", "unnamed")
        obs_dur = obs.get("latency") or obs.get("duration")
        obs_dur_str = f" [{format_duration(float(obs_dur))}]" if obs_dur else ""
        level = obs.get("level", "DEFAULT")

        status_prefix = "  ✓"
        if level == "ERROR":
            status_prefix = "  ✗ [ERROR]"
        elif level == "WARNING":
            status_prefix = "  ⚠ [WARN]"

        model_info = f" (model: {obs.get('model')})" if obs.get("model") else ""
        lines.append(f"{status_prefix} {i}. {obs_type.upper()}: {obs_name}{obs_dur_str}{model_info}")

        if level == "ERROR" and obs.get("statusMessage"):
            lines.append(f"      Message: {obs['statusMessage']}")

        # Show input/output excerpts if small
        inp = obs.get("input")
        out = obs.get("output")
        if inp and isinstance(inp, str) and len(inp) < 120:
            lines.append(f"      Input: {inp.strip()}")
        if out and isinstance(out, str) and len(out) < 120:
            lines.append(f"      Output: {out.strip()}")

    return "\n".join(lines)
