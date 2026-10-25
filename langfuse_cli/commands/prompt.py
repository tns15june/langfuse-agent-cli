"""Prompt management commands for Langfuse."""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict

from langfuse_cli.client import LangfuseClient
from langfuse_cli.config import resolve_from_args
from langfuse_cli.formatters.agent import format_agent_output


def compile_mustache(template: str, vars_dict: Dict[str, Any]) -> str:
    """Basic mustache variable substitution for {{var}}."""
    result = template
    for key, val in vars_dict.items():
        pattern = r"\{\{\s*" + re.escape(key) + r"\s*\}\}"
        result = re.sub(pattern, str(val), result)
    return result


def compile_prompt(prompt_data: Any, vars_dict: Dict[str, Any]) -> Any:
    if isinstance(prompt_data, str):
        return compile_mustache(prompt_data, vars_dict)
    elif isinstance(prompt_data, list):
        # Chat messages: [{"role": "user", "content": "..."}]
        out = []
        for msg in prompt_data:
            if isinstance(msg, dict) and "content" in msg and isinstance(msg["content"], str):
                c = dict(msg)
                c["content"] = compile_mustache(msg["content"], vars_dict)
                out.append(c)
            else:
                out.append(msg)
        return out
    return prompt_data


def handle_prompt(args: argparse.Namespace) -> int:
    client = LangfuseClient(resolve_from_args(args))
    compact, agent_fields = args.compact, args.agent_fields

    if args.prompt_action == "list":
        prompts = client.list_prompts(limit=args.limit, tag=args.tag).get("data", [])
        if args.output == "json":
            print(format_agent_output(prompts, compact=compact, agent_fields=agent_fields))
        elif not prompts:
            print("No prompts found.")
        else:
            print(f"Found {len(prompts)} prompts:")
            for p in prompts:
                versions = p.get("versions") or []
                latest = max(versions) if versions else "?"
                labels = ", ".join(p.get("labels", []))
                labels_str = f" [labels: {labels}]" if labels else ""
                print(f"  - {p.get('name')} (v{latest}){labels_str} - type: {p.get('type', 'text')}")
        return 0

    if args.prompt_action == "get":
        prompt = client.get_prompt(name=args.name, version=args.version, label=args.label)
        if args.vars:
            try:
                vars_dict = json.loads(args.vars)
                prompt["compiled_prompt"] = compile_prompt(prompt.get("prompt"), vars_dict)
                prompt["applied_vars"] = vars_dict
            except Exception as e:
                print(f"Warning: Failed to parse --vars JSON: {e}", file=sys.stderr)

        if args.output == "json":
            print(format_agent_output(prompt, compact=compact, agent_fields=agent_fields))
        else:
            print(f"Prompt: {prompt.get('name')} (v{prompt.get('version')})")
            print(f"Type: {prompt.get('type', 'text')}")
            if prompt.get("labels"):
                print(f"Labels: {', '.join(prompt['labels'])}")
            if prompt.get("tags"):
                print(f"Tags: {', '.join(prompt['tags'])}")
            print("-" * 40)
            display_content = prompt.get("compiled_prompt") or prompt.get("prompt")
            if isinstance(display_content, (dict, list)):
                print(json.dumps(display_content, indent=2))
            else:
                print(display_content)
        return 0

    # push
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        try:
            prompt_content = json.loads(content)
        except Exception:
            prompt_content = content
    elif args.text:
        prompt_content = args.text
    else:
        print("Error: Specify either --file <path> or --text '<prompt string>'", file=sys.stderr)
        return 1

    created = client.create_prompt(
        name=args.name,
        prompt_content=prompt_content,
        prompt_type=args.type,
        labels=[label.strip() for label in args.labels.split(",")] if args.labels else None,
        tags=[tag.strip() for tag in args.tags.split(",")] if args.tags else None,
    )
    if args.output == "json":
        print(format_agent_output(created, compact=compact, agent_fields=agent_fields))
    else:
        print(f"✓ Prompt '{args.name}' (v{created.get('version', 'new')}) published successfully.")
    return 0
