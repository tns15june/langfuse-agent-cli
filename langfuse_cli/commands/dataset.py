"""Dataset and evaluation commands for Langfuse."""
from __future__ import annotations

import argparse
import json
import sys

from langfuse_cli.client import LangfuseClient, LangfuseAPIError
from langfuse_cli.config import ConfigManager
from langfuse_cli.formatters.agent import format_agent_output


def handle_dataset(args: argparse.Namespace) -> int:
    cfg = ConfigManager()
    prof = cfg.resolve_profile(
        name=getattr(args, "profile", None),
        host_override=getattr(args, "host", None),
        pk_override=getattr(args, "public_key", None),
        sk_override=getattr(args, "secret_key", None),
        env_file=getattr(args, "env_file", None),
    )
    client = LangfuseClient(prof)
    action = getattr(args, "dataset_action", "list")
    out_format = getattr(args, "output", "json")

    try:
        if action == "list":
            res = client.list_datasets()
            datasets = res.get("data", [])
            if out_format == "json":
                print(json.dumps(datasets, indent=2))
            else:
                if not datasets:
                    print("No datasets found.")
                    return 0
                print(f"Datasets ({len(datasets)}):")
                for d in datasets:
                    print(f"  - {d.get('name')}: {d.get('description', '(no description)')}")
            return 0

        elif action == "get":
            name = args.name
            dataset = client.get_dataset(name)
            if out_format == "json":
                print(json.dumps(dataset, indent=2))
            else:
                print(f"Dataset: {dataset.get('name')}")
                print(f"Description: {dataset.get('description')}")
                items = dataset.get("items") or []
                print(f"Items count: {len(items)}")
                for i, itm in enumerate(items[:5], 1):
                    print(f"  Item {i}: input={itm.get('input')} expected={itm.get('expectedOutput')}")
            return 0

        elif action == "run":
            dataset_name = args.dataset
            run_name = args.run_name
            desc = getattr(args, "description", None)
            res = client.create_dataset_run(dataset_name=dataset_name, run_name=run_name, description=desc)
            print(f"✓ Dataset run '{run_name}' created on dataset '{dataset_name}'.")
            if out_format == "json":
                print(json.dumps(res, indent=2))
            return 0

    except LangfuseAPIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        return 1

    return 0
