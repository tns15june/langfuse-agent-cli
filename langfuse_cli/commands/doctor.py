"""Diagnostic command for Langfuse CLI, auth, and skills."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langfuse_cli import __version__
from langfuse_cli.client import LangfuseAPIError, LangfuseClient
from langfuse_cli.config import ConfigManager, resolve_from_args

SKILL_NAME = "langfuse-agent-cli"
KNOWN_SKILL_TARGETS = [
    ("Claude Code", Path.home() / ".claude" / "skills"),
    ("Antigravity", Path.home() / ".gemini" / "config" / "skills"),
    ("Universal Agents", Path.home() / ".agents" / "skills"),
    ("Cursor", Path.home() / ".cursor" / "skills"),
    ("OpenCode", Path.home() / ".config" / "opencode" / "skills"),
]


def _check_server(client: LangfuseClient) -> bool:
    try:
        health = client.health()
        print(f"  ✓ Connectivity: OK (server version {health.get('version', 'unknown')})")
        projects = client.get_project().get("data") or []
        print(f"  ✓ API Authorization: Valid (project: {', '.join(p.get('name', '?') for p in projects)})")
    except LangfuseAPIError as e:
        hint = {401: " (verify public/secret keys)", 403: " (check project access)"}.get(e.status_code or 0, "")
        print(f"  ✗ {e}{hint}")
        return False
    try:
        client.list_observations(limit=1, fields="core")
        print("  ✓ Observations API v2: available")
    except LangfuseAPIError as e:
        if e.status_code == 404:
            print("  ✗ This server has no /api/public/v2/observations; trace commands need Langfuse v4")
        else:
            print(f"  ✗ Observations API v2: {e}")
        return False
    return True


def handle_doctor(args: argparse.Namespace) -> int:
    cfg = ConfigManager()
    prof = resolve_from_args(args)

    print("\nLangfuse Agent CLI System Diagnostics")
    print("=" * 45)

    print("\n1. Build & Runtime")
    print(f"  CLI Version: {__version__}")
    print(f"  Python Version: {sys.version.split()[0]}")
    print(f"  Config File: {cfg.config_path} ({'exists' if cfg.config_path.exists() else 'not created yet'})")

    print("\n2. Resolved Authentication")
    print(f"  Source: {prof.source}" + (f" ({prof.name})" if prof.source == "profile" else ""))
    print(f"  Host Endpoint: {prof.host}")
    print(f"  Public Key: {prof.masked_public_key()}")
    print(f"  Secret Key: {prof.masked_secret_key()}")
    if not prof.is_complete():
        print("  ✗ Incomplete credentials. Run 'lf auth login' or set LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY.")
        auth_ok = False
    else:
        auth_ok = _check_server(LangfuseClient(prof))

    print("\n3. Agent Skill")
    skills_found = 0
    for name, target_dir in KNOWN_SKILL_TARGETS:
        skill_path = target_dir / SKILL_NAME
        if skill_path.exists():
            skills_found += 1
            print(f"  ✓ {name:<18} Installed at {skill_path}")
        else:
            print(f"  – {name:<18} Not found in {target_dir}")

    print("\nSummary:")
    if not auth_ok:
        print("  ⚠ Fix the authentication or server problem above.")
        return 1
    if skills_found:
        print("  ✓ All checks passed.")
    else:
        print("  ℹ Skill not installed. Install it with: npx skills add tns15june/langfuse-agent-cli")
    return 0
