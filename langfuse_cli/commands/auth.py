"""Authentication and profile management commands."""
from __future__ import annotations

import argparse
import getpass
import sys

from langfuse_cli.config import ConfigManager, resolve_from_args
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
            secret_key = getpass.getpass("Enter Langfuse Secret Key (sk-lf-...): ").strip()

        cfg.save_profile(
            name=profile_name,
            host=host,
            public_key=public_key,
            secret_key=secret_key,
            set_default=args.default,
        )
        print(f"✓ Profile '{profile_name}' saved successfully ({host}).")

        client = LangfuseClient(cfg.resolve_profile(name=profile_name))
        try:
            projects = client.get_project().get("data") or []
        except LangfuseAPIError as e:
            print(f"⚠ Profile saved, but the keys could not be verified: {e}", file=sys.stderr)
            return 1
        print(f"✓ Keys verified for project: {', '.join(p.get('name', '?') for p in projects) or '(none)'}")
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
    prof = resolve_from_args(args)
    print(f"Source: {prof.source}" + (f" ({prof.name})" if prof.source == "profile" else ""))
    print(f"Host: {prof.host}")
    print(f"Public Key: {prof.masked_public_key()}")
    print(f"Secret Key: {prof.masked_secret_key()}")

    if not prof.is_complete():
        print("⚠ Incomplete credentials. Configure with 'lf auth login'.")
        return 1

    try:
        projects = LangfuseClient(prof).get_project().get("data") or []
    except LangfuseAPIError as e:
        print(f"✗ {e}")
        return 1
    print(f"✓ Keys valid for project: {', '.join(p.get('name', '?') for p in projects) or '(none)'}")
    return 0
