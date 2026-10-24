"""Progressive disclosure and machine-readable command schemas for AI agents."""
from __future__ import annotations

import argparse
import json
from typing import Dict, Any, List

COMMAND_CATALOG: Dict[str, Dict[str, Any]] = {
    "auth login": {
        "desc": "Save a new Langfuse connection profile",
        "write": True,
        "opts": ["--host <url>", "--public-key <pk>", "--secret-key <sk>", "--profile-name <name>", "--default"],
        "rules": ["Stores credentials securely in ~/.config/langfuse/profiles.json (mode 0600)."],
    },
    "auth list": {
        "desc": "List all configured Langfuse profiles and masked keys",
        "write": False,
        "opts": [],
        "rules": ["Never reveals full secret keys."],
    },
    "doctor": {
        "desc": "Perform end-to-end diagnostics on auth, connectivity, and agent skills installation",
        "write": False,
        "opts": ["--profile <name>", "--env-file <path>"],
        "rules": ["Probes /api/public/health and /api/public/traces."],
    },
    "prompt list": {
        "desc": "List all registered prompts with their latest versions, types, and tags",
        "write": False,
        "opts": ["--tag <tag>", "--limit <n>", "--output <json|text>", "--compact"],
        "rules": ["Supports compact token-saving view for agents."],
    },
    "prompt get": {
        "desc": "Fetch a prompt by name, optionally compiling mustache variables",
        "write": False,
        "opts": ["<name>", "--version <n>", "--label <label>", "--vars '<json>'", "--output <json|text>"],
        "rules": ["Use --vars '{\"var\": \"val\"}' to preview compiled templates."],
    },
    "prompt push": {
        "desc": "Create or update a prompt version in Langfuse",
        "write": True,
        "opts": ["<name>", "--file <path.json>", "--text '<prompt>'", "--type <text|chat>", "--labels <list>"],
        "rules": ["Read current prompt first with 'prompt get' to avoid accidental regressions."],
    },
    "trace list": {
        "desc": "Query traces with filters (session, user, errors, time windows)",
        "write": False,
        "opts": ["--session-id <id>", "--user-id <id>", "--status <all|error>", "--limit <n>", "--compact"],
        "rules": ["Use --compact to reduce response size by 80%."],
    },
    "trace get": {
        "desc": "Fetch full trace details including observations, spans, durations, and errors",
        "write": False,
        "opts": ["<trace_id>", "--timeline", "--full", "--output <json|text>"],
        "rules": ["Use --timeline for ASCII turn-by-turn breakdown."],
    },
    "session get": {
        "desc": "Retrieve session summary and timeline of traces for a single user interaction",
        "write": False,
        "opts": ["<session_id>", "--compact"],
        "rules": ["Combines session metadata with chronological trace entries."],
    },
    "dataset list": {
        "desc": "List evaluation datasets",
        "write": False,
        "opts": ["--output <json|text>"],
        "rules": [],
    },
    "dataset get": {
        "desc": "Fetch dataset items and ground-truth inputs/outputs",
        "write": False,
        "opts": ["<name>"],
        "rules": [],
    },
    "dataset run": {
        "desc": "Register an evaluation run against a dataset",
        "write": True,
        "opts": ["--dataset <name>", "--run-name <name>", "--description <text>"],
        "rules": [],
    },
    "score create": {
        "desc": "Record an evaluation score or metric against a trace or observation",
        "write": True,
        "opts": ["--trace-id <id>", "--name <name>", "--value <float>", "--comment <text>"],
        "rules": ["Value must be a float."],
    },
    "skills install": {
        "desc": "Install Langfuse companion skills to AI agent directories",
        "write": True,
        "opts": ["--target <all|claude|gemini|cursor|agents>", "--symlink"],
        "rules": ["Installs to ~/.claude, ~/.gemini/config, ~/.agents, ~/.cursor, ~/.config/opencode."],
    },
    "skills list": {
        "desc": "List available skills and their installation status across platforms",
        "write": False,
        "opts": [],
        "rules": [],
    },
}


def handle_help_map(args: argparse.Namespace) -> int:
    print("Langfuse Agent CLI Command Map (* indicates state mutation):")
    for cmd, info in sorted(COMMAND_CATALOG.items()):
        write_flag = "* " if info["write"] else "  "
        print(f"{write_flag}lf {cmd:<18} — {info['desc']}")
    return 0


def handle_help_describe(args: argparse.Namespace) -> int:
    target = getattr(args, "target_command", None) or getattr(args, "command", [])
    query = " ".join(target).strip()
    match = None
    for cmd, info in COMMAND_CATALOG.items():
        if query == cmd or query in cmd:
            match = (cmd, info)
            break

    if not match:
        print(f"Unknown command: '{query}'. Run 'lf help-map' to view all commands.")
        return 1

    cmd, info = match
    desc_payload = {
        "cmd": f"lf {cmd}",
        "desc": info["desc"],
        "write": info["write"],
        "opts": info["opts"],
        "rules": info["rules"],
    }
    if getattr(args, "output", "json") == "json":
        print(json.dumps(desc_payload, indent=2))
    else:
        print(f"Command: lf {cmd}")
        print(f"Description: {info['desc']} (Mutation: {info['write']})")
        print("Options:")
        for opt in info["opts"]:
            print(f"  {opt}")
        if info["rules"]:
            print("Rules:")
            for r in info["rules"]:
                print(f"  • {r}")
    return 0
