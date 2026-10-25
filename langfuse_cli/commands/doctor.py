"""Diagnostic command for Langfuse CLI, auth, and skills."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langfuse_cli import __version__
from langfuse_cli.config import ConfigManager, resolve_from_args
from langfuse_cli.client import LangfuseClient, LangfuseAPIError


KNOWN_SKILL_TARGETS = [
    ("Claude Code", Path.home() / ".claude" / "skills"),
    ("Antigravity", Path.home() / ".gemini" / "config" / "skills"),
    ("Universal Agents", Path.home() / ".agents" / "skills"),
    ("Cursor", Path.home() / ".cursor" / "skills"),
    ("OpenCode", Path.home() / ".config" / "opencode" / "skills"),
]


def handle_doctor(args: argparse.Namespace) -> int:
    cfg = ConfigManager()
    prof = resolve_from_args(args)

    print("\nLangfuse Agent CLI System Diagnostics")
    print("=" * 45)

    # 1. Build and runtime
    print("\n1. Build & Runtime")
    print(f"  CLI Version: {__version__}")
    print(f"  Python Version: {sys.version.split()[0]}")
    print(f"  Config File: {cfg.config_path} ({'exists' if cfg.config_path.exists() else 'not created yet'})")

    # 2. Resolved Auth Profile
    print("\n2. Resolved Authentication")
    print(f"  Profile Name: {prof.name}")
    print(f"  Host Endpoint: {prof.host}")
    print(f"  Public Key: {prof.masked_public_key()}")
    print(f"  Secret Key: {prof.masked_secret_key()}")

    auth_ok = False
    if not prof.is_complete():
        print("  ✗ Status: Incomplete credentials. Set via 'lf auth login' or LANGFUSE_* env vars.")
    else:
        client = LangfuseClient(prof)
        try:
            h = client.health()
            print(f"  ✓ Connectivity: OK (server status: {h.get('status')}, version: {h.get('version', 'N/A')})")

            # Test API auth with traces query
            try:
                res = client.list_traces(limit=1)
                trace_count = len(res.get("data", []))
                print(f"  ✓ API Authorization: Valid (trace probe returned {trace_count} items)")
                auth_ok = True
            except LangfuseAPIError as ae:
                if ae.status_code == 401:
                    print("  ✗ API Authorization: Failed (HTTP 401 Unauthorized - verify public/secret keys)")
                elif ae.status_code == 403:
                    print("  ✗ API Authorization: Forbidden (HTTP 403 - check project access permissions)")
                else:
                    print(f"  ✗ API Authorization Probe Error: {ae}")
        except LangfuseAPIError as e:
            print(f"  ✗ Host Connectivity Failed: {e}")

    # 3. Companion Skills Inspection
    print("\n3. Agent Skills Ecosystem")
    skills_found = 0
    for name, target_dir in KNOWN_SKILL_TARGETS:
        skill_path = target_dir / "langfuse"
        if skill_path.exists():
            skills_found += 1
            print(f"  ✓ {name:<18} Installed at {skill_path}")
        else:
            print(f"  – {name:<18} Not installed ({target_dir})")

    print("\nSummary:")
    if auth_ok and skills_found > 0:
        print("  ✓ All systems operational. Both CLI and Agent Skills are ready.")
        return 0
    elif not auth_ok:
        print("  ⚠ Auth setup needed: Run 'lf auth login' to configure valid credentials.")
        return 1
    else:
        print("  ℹ Skills not installed: Run 'lf skills install' to register skills with your AI coding agents.")
        return 0
