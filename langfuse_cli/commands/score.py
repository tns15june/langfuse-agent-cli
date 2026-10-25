"""Score and evaluation metric commands."""
from __future__ import annotations

import argparse

from langfuse_cli.client import LangfuseClient
from langfuse_cli.config import resolve_from_args
from langfuse_cli.formatters.agent import print_json


def handle_score(args: argparse.Namespace) -> int:
    client = LangfuseClient(resolve_from_args(args))
    res = client.create_score(
        trace_id=args.trace_id,
        name=args.name,
        value=args.value,
        comment=args.comment,
        observation_id=args.observation_id,
    )
    if args.output == "json":
        print_json(args, res)
    else:
        print(f"✓ Score '{args.name}'={args.value} recorded for trace '{args.trace_id}'.")
    return 0
