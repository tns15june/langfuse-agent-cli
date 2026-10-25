"""Prompt management commands for Langfuse."""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Dict, Any, Optional

from langfuse_cli.client import LangfuseClient, LangfuseAPIError
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
    prof = resolve_from_args(args)
    client = LangfuseClient(prof)
    action = getattr(args, "prompt_action", "list")
    out_format = getattr(args, "output", "json")
    compact = getattr(args, "compact", False)
    agent_fields = getattr(args, "agent_fields", None)

    try:
        if action == "list":
            tag = getattr(args, "tag", None)
            limit = getattr(args, "limit", 20)
            res = client.list_prompts(limit=limit, tag=tag)
            prompts = res.get("data", [])
            if out_format == "json":
                print(format_agent_output(prompts, output_format="json", compact=compact, agent_fields=agent_fields))
            else:
                if not prompts:
                    print("No prompts found.")
                    return 0
                print(f"Found {len(prompts)} prompts:")
                for p in prompts:
                    v = p.get("version", "?")
                    labels = ", ".join(p.get("labels", []))
                    labels_str = f" [labels: {labels}]" if labels else ""
                    print(f"  - {p.get('name')} (v{v}){labels_str} - type: {p.get('type', 'text')}")
            return 0

        elif action == "get":
            name = args.name
            version = getattr(args, "version", None)
            label = getattr(args, "label", None)
            prompt = client.get_prompt(name=name, version=version, label=label)

            # Check if variable compilation requested
            vars_json = getattr(args, "vars", None)
            if vars_json:
                try:
                    vars_dict = json.loads(vars_json)
                    compiled_content = compile_prompt(prompt.get("prompt"), vars_dict)
                    prompt["compiled_prompt"] = compiled_content
                    prompt["applied_vars"] = vars_dict
                except Exception as e:
                    print(f"Warning: Failed to parse --vars JSON: {e}", file=sys.stderr)

            if out_format == "json":
                print(format_agent_output(prompt, output_format="json", compact=compact, agent_fields=agent_fields))
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

        elif action == "push" or action == "create":
            name = args.name
            prompt_file = getattr(args, "file", None)
            raw_text = getattr(args, "text", None)

            if prompt_file:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    content = f.read()
                try:
                    prompt_content = json.loads(content)
                except Exception:
                    prompt_content = content
            elif raw_text:
                prompt_content = raw_text
            else:
                print("Error: Specify either --file <path> or --text '<prompt string>'", file=sys.stderr)
                return 1

            ptype = getattr(args, "type", "text")
            labels = [l.strip() for l in args.labels.split(",")] if getattr(args, "labels", None) else None
            tags = [t.strip() for t in args.tags.split(",")] if getattr(args, "tags", None) else None

            created = client.create_prompt(
                name=name,
                prompt_content=prompt_content,
                prompt_type=ptype,
                labels=labels,
                tags=tags,
            )
            print(f"✓ Prompt '{name}' (v{created.get('version', 'new')}) published successfully.")
            return 0

    except LangfuseAPIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        return 1

    return 0
