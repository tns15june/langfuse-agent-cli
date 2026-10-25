"""Score and evaluation metric commands."""
from __future__ import annotations

import argparse
import json
import sys

from langfuse_cli.client import LangfuseClient, LangfuseAPIError
from langfuse_cli.config import resolve_from_args


def handle_score(args: argparse.Namespace) -> int:
    prof = resolve_from_args(args)
    client = LangfuseClient(prof)
    action = getattr(args, "score_action", "create")

    try:
        if action == "create":
            trace_id = args.trace_id
            name = args.name
            value = float(args.value)
            comment = getattr(args, "comment", None)
            obs_id = getattr(args, "observation_id", None)

            res = client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
                observation_id=obs_id,
            )
            print(f"✓ Score '{name}'={value} recorded for trace '{trace_id}'.")
            if getattr(args, "output", "json") == "json":
                print(json.dumps(res, indent=2))
            return 0
    except LangfuseAPIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        return 1

    return 0
