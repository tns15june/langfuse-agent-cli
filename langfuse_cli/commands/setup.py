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
from langfuse_cli.config import ConfigError, ConfigManager, resolve_from_args

INSTALL_LATER = f"  To install it later: npx skills@1 add {SKILL_SOURCE} -g"
SOURCE_NAMES = {"env": "the LANGFUSE_* environment variables", "env-file": "the --env-file file",
                "flags": "--public-key and --secret-key"}


def _credentials(args: argparse.Namespace, interactive: bool) -> None:
    try:
        prof = resolve_from_args(args)
    except ConfigError as e:  # doctor reports it again; the skill step still runs
        print(f"  ✗ {e}")
        return
    rejected = True  # missing keys count as rejected
    if prof.is_complete():
        try:
            projects = LangfuseClient(prof).get_project().get("data") or []
        except LangfuseAPIError as e:
            print(f"  ✗ {e}")
            rejected = e.status_code in (401, 403)
        else:
            names = ", ".join(p.get("name", "?") for p in projects) or "(none)"
            print(f"  ✓ Using {prof.source} credentials for {prof.host} (project: {names})")
            return
    if not rejected:  # new keys would not help; asking for them invites overwriting good ones
        print("  – Login skipped: the keys were not rejected; check the host and that the server is up.")
    elif prof.source != "profile":  # these sources outrank saved profiles, so a login here would change nothing
        print(f"  – Login skipped: these keys come from {SOURCE_NAMES[prof.source]}, which take precedence over "
              "saved profiles. Fix or unset them, then run lf setup again.")
    elif not interactive:
        print("  – Login skipped: lf setup never asks for keys with --yes or without a terminal. "
              "Ask the user to run 'lf setup' in their own terminal.")
    else:
        host = input(f"  Langfuse host [{prof.host}]: ").strip() or prof.host
        login(ConfigManager(), prof.name, host, None, None, set_default=True)  # keys that failed are asked for again


def _install_skill(interactive: bool) -> bool:
    """Install the skill with the skills CLI; False when it could not be installed (declining is not a failure)."""
    npx = shutil.which("npx")
    if npx is None:
        print("  ✗ npx not found; the skills CLI needs Node.js 22.20 or later.")
        print(INSTALL_LATER)
        return False
    # On Windows, which() searches the current folder first; never run an npx that a project folder supplies.
    if os.path.normcase(os.path.realpath(os.path.dirname(npx))) == os.path.normcase(os.path.realpath(os.getcwd())):
        print(f"  ✗ Not running {npx}: it is in the current folder. Run lf setup from another folder.")
        print(INSTALL_LATER)
        return False
    if interactive and input(f"  Install the {SKILL_NAME} skill for your coding agents? [Y/n] ").strip().lower() in (
            "n", "no"):
        print(INSTALL_LATER)
        return True
    # npx --yes skips npm's install prompt. The skills CLI's own -y skips its questions: without it, it asks which
    # agents to use when it finds several; with it, it takes the agents it finds, or every agent it supports when it
    # finds none. Run from inside a coding agent, it targets that agent either way.
    cmd = [npx, "--yes", "skills@1", "add", SKILL_SOURCE, "-g"]
    if not interactive:
        cmd.append("-y")
    # No LANGFUSE_* keys for npx and the install scripts it runs; git must fail rather than wait for a password.
    env = {k: v for k, v in os.environ.items() if not k.startswith("LANGFUSE_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    print(f"  Running: npx {' '.join(cmd[1:])}", flush=True)
    try:
        # Unattended runs get no stdin and 90 s, so they end inside an agent's usual 2-minute command limit.
        result = subprocess.run(cmd, env=env, stdin=None if interactive else subprocess.DEVNULL,
                                timeout=None if interactive else 90)
        reason = f"npx exited with code {result.returncode}" if result.returncode else ""
    except (subprocess.TimeoutExpired, OSError) as e:  # OSError: npx was found but could not be started
        reason = str(e)
    if reason:
        print(f"  ✗ The skill was not installed: {reason}")
        print(INSTALL_LATER)
    return not reason


def handle_setup(args: argparse.Namespace) -> int:
    interactive = not args.yes and sys.stdin is not None and sys.stdin.isatty()
    print("\nLangfuse Agent CLI Setup")
    print("\n1. Credentials")
    _credentials(args, interactive)
    print("\n2. Agent Skill")
    installed = _install_skill(interactive)
    print("\n3. Check")
    code = handle_doctor(args)
    if not installed:
        print("  ✗ lf setup did not install the skill (see step 2); any copy listed above is from an earlier install.")
        return 1
    return code
