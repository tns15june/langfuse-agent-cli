"""Progressive disclosure and machine-readable command schemas for AI agents."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

# One entry per leaf command of the parser; tests/test_help.py fails when the two drift apart.
COMMAND_CATALOG: Dict[str, Dict[str, Any]] = {
    "auth login": {
        "desc": "Save a connection profile and verify its keys",
        "write": True,
        "opts": ["--profile-name <name>", "--host <url>", "--public-key <pk>", "--secret-key <sk>", "--default"],
        "rules": [
            "Prompts for missing keys (the secret is read hidden); ask the user to run it.",
            "Stores ~/.config/langfuse/profiles.json with mode 0600.",
        ],
    },
    "auth switch": {
        "desc": "Make a saved profile the current one",
        "write": True,
        "opts": ["<profile>"],
        "rules": [],
    },
    "auth list": {
        "desc": "List saved profiles with masked keys",
        "write": False,
        "opts": [],
        "rules": ["Never prints full secret keys."],
    },
    "auth status": {
        "desc": "Show where credentials come from and check the keys",
        "write": False,
        "opts": ["--profile <name>", "--env-file <path>"],
        "rules": [],
    },
    "doctor": {
        "desc": "Check credentials, server version, the v2 observations API and the agent skill",
        "write": False,
        "opts": ["--profile <name>", "--env-file <path>"],
        "rules": ["Exit code 1 means an authentication or server problem."],
    },
    "prompt list": {
        "desc": "List prompts with their versions, labels and tags",
        "write": False,
        "opts": ["--tag <tag>", "--limit <n>", "--output <json|text>", "--compact"],
        "rules": [],
    },
    "prompt get": {
        "desc": "Fetch a prompt, optionally filling its {{variables}}",
        "write": False,
        "opts": ["<name>", "--version <n>", "--label <label>", "--vars '<json>'", "--output <json|text>"],
        "rules": [
            "Without --version or --label the server returns the 'production' label.",
            "Folder names like 'support/greeter' work as-is.",
        ],
    },
    "prompt push": {
        "desc": "Create a new prompt version",
        "write": True,
        "opts": ["<name>", "--text '<prompt>'", "--file <path>", "--type <text|chat>", "--labels <a,b>", "--tags <a,b>"],
        "rules": ["Read the current version with 'prompt get' first and tell the user what will change."],
    },
    "trace list": {
        "desc": "List traces newest first; --status error lists failing traces with their errors",
        "write": False,
        "opts": ["--status <all|error>", "--session-id <id>", "--user-id <id>", "--from-ts <iso>", "--to-ts <iso>",
                 "--limit <n>", "--compact", "--agent-fields <paths>"],
        "rules": ["--limit counts traces, also with --status error."],
    },
    "trace get": {
        "desc": "All observations of one trace; --timeline renders them as a tree",
        "write": False,
        "opts": ["<trace_id>", "--timeline", "--io", "--compact", "--agent-fields <paths>"],
        "rules": ["Inputs and outputs are left out unless --io is given; they are often large."],
    },
    "trace session": {
        "desc": "Traces of one session, oldest first",
        "write": False,
        "opts": ["<session_id>", "--compact", "--agent-fields <paths>"],
        "rules": [],
    },
    "dataset list": {
        "desc": "List datasets",
        "write": False,
        "opts": ["--output <json|text>"],
        "rules": [],
    },
    "dataset get": {
        "desc": "A dataset with the first page of its items",
        "write": False,
        "opts": ["<name>", "--compact"],
        "rules": [],
    },
    "score create": {
        "desc": "Record a numeric score on a trace or one of its observations",
        "write": True,
        "opts": ["--trace-id <id>", "--name <name>", "--value <number>", "--comment <text>", "--observation-id <id>"],
        "rules": [],
    },
    "help-map": {
        "desc": "This command map (* marks commands that write)",
        "write": False,
        "opts": [],
        "rules": [],
    },
    "help": {
        "desc": "Describe one command as JSON: options and rules",
        "write": False,
        "opts": ["<command...>"],
        "rules": ["Give the exact command, e.g. lf help \"trace get\"."],
    },
}


def handle_help_map(args: argparse.Namespace) -> int:
    print("Langfuse Agent CLI Command Map (* indicates state mutation):")
    for cmd, info in sorted(COMMAND_CATALOG.items()):
        write_flag = "* " if info["write"] else "  "
        print(f"{write_flag}lf {cmd:<18} — {info['desc']}")
    return 0


def handle_help_describe(args: argparse.Namespace) -> int:
    words = list(args.target_command)
    if words[:1] == ["describe"]:  # accept the `help describe "<cmd>"` spelling too
        words = words[1:]
    query = " ".join(words).strip()
    info = COMMAND_CATALOG.get(query)
    if info is None:
        suggestions = [cmd for cmd in COMMAND_CATALOG if query and query in cmd]
        hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        print(f"Unknown command: '{query}'.{hint} Run 'lf help-map' to view all commands.", file=sys.stderr)
        return 1

    payload = {"cmd": f"lf {query}", "desc": info["desc"], "write": info["write"], "opts": info["opts"],
               "rules": info["rules"]}
    if args.output == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"Command: lf {query}")
        print(f"Description: {info['desc']} (Mutation: {info['write']})")
        print("Options:")
        for opt in info["opts"]:
            print(f"  {opt}")
        if info["rules"]:
            print("Rules:")
            for r in info["rules"]:
                print(f"  • {r}")
    return 0
