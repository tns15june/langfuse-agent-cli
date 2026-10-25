"""One-step setup: credentials, the agent skill, then doctor."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from langfuse_cli.client import LangfuseAPIError, LangfuseClient
from langfuse_cli.commands.auth import login
from langfuse_cli.commands.doctor import SKILL_NAME, SKILL_SOURCE, handle_doctor
from langfuse_cli.config import ConfigManager, resolve_from_args


def _credentials(args: argparse.Namespace, interactive: bool) -> None:
    prof = resolve_from_args(args)
    if prof.is_complete():
        try:
            projects = LangfuseClient(prof).get_project().get("data") or []
            names = ", ".join(p.get("name", "?") for p in projects) or "(none)"
            print(f"  ✓ Using {prof.source} credentials for {prof.host} (project: {names})")
            return
        except LangfuseAPIError as e:
            print(f"  ✗ {e}")
    if not interactive:
        print("  – Login skipped: lf setup never asks for keys with --yes or without a terminal. "
              "Ask the user to run 'lf auth login' in their own terminal.")
        return
    host = input(f"  Langfuse host [{prof.host}]: ").strip() or prof.host
    login(ConfigManager(), prof.name if prof.source == "profile" else "default", host,
          args.public_key, args.secret_key, set_default=True)


def _install_skill(interactive: bool) -> None:
    npx = shutil.which("npx")
    later = f"  To install it later: npx skills add {SKILL_SOURCE} -g"
    if npx is None:
        print("  npx not found; the skills CLI needs Node.js 22.20 or later.")
        print(later)
        return
    if interactive and input(f"  Install the {SKILL_NAME} skill for your coding agents? [Y/n] ").strip().lower() in (
            "n", "no"):
        print(later)
        return
    # Without -y the skills CLI asks which agents to install for; with -y it picks the detected ones.
    cmd = [npx, "--yes", "skills@1", "add", SKILL_SOURCE, "-g"] + ([] if interactive else ["-y"])
    env = {k: v for k, v in os.environ.items() if not k.startswith("LANGFUSE_")}  # keys stay out of npm packages
    print(f"  Running: {' '.join(cmd[1:])}")
    sys.stdout.flush()
    try:
        failed = subprocess.run(cmd, env=env, timeout=None if interactive else 300).returncode != 0
    except subprocess.TimeoutExpired:
        failed = True
    if failed:
        print("  ✗ The skill was not installed.")
        print(later)


def handle_setup(args: argparse.Namespace) -> int:
    interactive = not args.yes and sys.stdin.isatty()
    print("\nLangfuse Agent CLI Setup")
    print("\n1. Credentials")
    _credentials(args, interactive)
    print("\n2. Agent Skill")
    _install_skill(interactive)
    print("\n3. Check")
    return handle_doctor(args)
