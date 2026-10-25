"""Token-efficient output formatters for AI coding assistants."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from langfuse_cli.formatters import clean

SUMMARY_THRESHOLD_BYTES = 16 * 1024
SUMMARY_HINT = ("The JSON output is larger than 16 KB, so it was written to outputFile. Read only the parts you need, "
                "for example with jq, or narrow the command with --agent-fields.")


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
    summary: bool = False,
) -> str:
    """JSON for agents: optional field projection (applied to each list item), then optional pruning.

    With `summary`, output over SUMMARY_THRESHOLD_BYTES goes to a file and a short envelope is returned instead.
    """
    if agent_fields:
        fields = [f.strip() for f in agent_fields.split(",") if f.strip()]
        if isinstance(data, list):
            data = [filter_dict_fields(d, fields) for d in data if isinstance(d, dict)]
        elif isinstance(data, dict):
            data = filter_dict_fields(data, fields)
    if compact:
        # Prune inside each row but keep the rows: dropping emptied rows would print [] for real results.
        data = [prune(row) for row in data] if isinstance(data, list) else prune(data)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if summary and len(text.encode("utf-8", "surrogatepass")) > SUMMARY_THRESHOLD_BYTES:
        return json.dumps(_write_summary(data, text), indent=2)
    return text


def _write_summary(data: Any, text: str) -> Dict[str, Any]:
    """Write `text` to a new private file and describe it."""
    content = (clean(text) + "\n").encode("utf-8")  # the file gets the same escaping as the terminal
    fd, path = tempfile.mkstemp(prefix="lf-", suffix=".json")  # mode 0600; kept, the caller reads it after lf exits
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
    except BaseException:
        os.unlink(path)  # no half-written file left behind
        raise
    envelope: Dict[str, Any] = {"summary": True, "outputFile": path, "bytes": len(content)}
    if isinstance(data, list):
        envelope["rows"] = len(data)
        envelope["rowKeys"] = list(dict.fromkeys(k for row in data if isinstance(row, dict) for k in row))
    elif isinstance(data, dict):
        envelope["keys"] = list(data)
    envelope["hint"] = SUMMARY_HINT
    return envelope


def print_json(args: argparse.Namespace, data: Any) -> None:
    """Print a data command's JSON result, honouring --agent-fields, --compact and --output-summary."""
    print(format_agent_output(data, compact=args.compact, agent_fields=args.agent_fields, summary=args.output_summary))
