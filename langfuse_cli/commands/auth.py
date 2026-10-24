"""Authentication and profile management commands."""
from __future__ import annotations

import argparse
import sys
from typing import List

from langfuse_cli.config import ConfigManager
from langfuse_cli.client import LangfuseClient, LangfuseAPIError


def handle_auth(args: argparse.Namespace) -> int:
    cfg = ConfigManager()
    subaction = getattr(args, "auth_action", None)

    if subaction == "login":
        profile_name = args.profile_name or "default"
        host = args.host or "https://cloud.langfuse.com"
        public_key = args.public_key
        secret_key = args.secret_key

        if not public_key:
            public_key = input("Enter Langfuse Public Key (pk-lf-...): ").strip()
        if not secret_key:
            secret_key = input("Enter Langfuse Secret Key (sk-lf-...): ").strip()

        cfg.save_profile(
            name=profile_name,
            host=host,
            public_key=public_key,
            secret_key=secret_key,
            set_default=args.default,
        )
        print(f"✓ Profile '{profile_name}' saved successfully ({host}).")

        # Test connectivity
        prof = cfg.resolve_profile(name=profile_name)
        client = LangfuseClient(prof)
        try:
            h = client.health()
            print(f"✓ Verified connectivity: Langfuse server status {h.get('status', 'OK')} (v{h.get('version', 'unknown')})")
        except Exception as e:
            print(f"⚠ Warning: Could not verify connectivity immediately: {e}")
        return 0

    elif subaction == "switch":
        target = args.target_profile
        profiles = cfg.list_profiles()
        if target not in profiles:
            print(f"Error: Profile '{target}' not found. Available profiles: {list(profiles.keys())}")
            return 1
        cfg.set_current_profile(target)
        print(f"✓ Active profile switched to '{target}'.")
        return 0

    elif subaction == "list":
        current = cfg.get_current_profile_name()
        profiles = cfg.list_profiles()
        if not profiles:
            print("No profiles configured yet. Run 'lf auth login' to add one.")
            return 0
        print("Configured Profiles:")
        for name, p in profiles.items():
            active_marker = "* " if name == current else "  "
            print(f"{active_marker}{name}:")
            print(f"    Host: {p.host}")
            print(f"    Public Key: {p.masked_public_key()}")
            print(f"    Secret Key: {p.masked_secret_key()}")
        return 0

    # Default: status
    prof = cfg.resolve_profile(name=getattr(args, "profile", None))
    print(f"Current Profile: {prof.name}")
    print(f"Host: {prof.host}")
    print(f"Public Key: {prof.masked_public_key()}")
    print(f"Secret Key: {prof.masked_secret_key()}")

    if not prof.is_complete():
        print("⚠ Incomplete credentials. Configure with 'lf auth login'.")
        return 1

    client = LangfuseClient(prof)
    try:
        h = client.health()
        print(f"✓ Connectivity: OK (status: {h.get('status')}, version: {h.get('version')})")
        return 0
    except LangfuseAPIError as e:
        print(f"✗ Connection error: {e}")
        return 1
