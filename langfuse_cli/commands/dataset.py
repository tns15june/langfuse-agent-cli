"""Dataset commands for Langfuse."""
from __future__ import annotations

import argparse

from langfuse_cli.client import LangfuseClient
from langfuse_cli.config import resolve_from_args
from langfuse_cli.formatters.agent import format_agent_output


def handle_dataset(args: argparse.Namespace) -> int:
    client = LangfuseClient(resolve_from_args(args))

    if args.dataset_action == "list":
        datasets = client.list_datasets().get("data", [])
        if args.output == "json":
            print(format_agent_output(datasets, compact=args.compact, agent_fields=args.agent_fields))
        elif not datasets:
            print("No datasets found.")
        else:
            print(f"Datasets ({len(datasets)}):")
            for d in datasets:
                print(f"  - {d.get('name')}: {d.get('description') or '(no description)'}")
        return 0

    # get: the v2 API serves a dataset and its items separately; show the first page of items
    dataset = client.get_dataset(args.name)
    dataset["items"] = client.list_dataset_items(args.name).get("data", [])
    if args.output == "json":
        print(format_agent_output(dataset, compact=args.compact, agent_fields=args.agent_fields))
    else:
        print(f"Dataset: {dataset.get('name')}")
        print(f"Description: {dataset.get('description')}")
        print(f"Items: {len(dataset['items'])} (first page)")
        for i, item in enumerate(dataset["items"][:5], 1):
            print(f"  Item {i}: input={item.get('input')} expected={item.get('expectedOutput')}")
    return 0
