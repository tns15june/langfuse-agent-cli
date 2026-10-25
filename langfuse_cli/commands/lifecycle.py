"""lf upgrade and lf uninstall: change lf itself, its agent skill and its saved profiles."""
from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Optional

from langfuse_cli import __version__, install_info
from langfuse_cli.config import ConfigManager

PACKAGE = install_info.PACKAGE
UPGRADE = {"uv": ["uv", "tool", "upgrade", PACKAGE], "pipx": ["pipx", "upgrade", PACKAGE]}
UNINSTALL = {"uv": ["uv", "tool", "uninstall", PACKAGE], "pipx": ["pipx", "uninstall", PACKAGE]}
SKILL_REMOVE = ["--yes", "skills@1", "remove", "-g", "-y", install_info.SKILL_NAME]


def _run(cmd: List[str], exe: Optional[str] = None) -> int:
    """Run an installer command, shown to the user first; a missing or refused program counts as a failure."""
    if exe is None:
        exe, why_not = install_info.find_tool(cmd[0])
        if exe is None:
            print(f"  ✗ {why_not}")
            return 127
    print(f"  Running: {' '.join(cmd)}", flush=True)
    try:
        return subprocess.run([exe, *cmd[1:]]).returncode
    except OSError as e:
        print(f"  ✗ {e}")
        return 1


def handle_upgrade(args: argparse.Namespace) -> int:
    method = install_info.install_method()
    if method not in UPGRADE:
        print(f"lf was installed with pip. Upgrade it with: pip install --upgrade {PACKAGE}, then run lf setup.",
              file=sys.stderr)
        return 1
    print(f"Upgrading lf {__version__}, installed with {method}")
    code = _run(UPGRADE[method])
    if code:
        print(f"✗ The upgrade failed (exit code {code}); lf {__version__} is unchanged.")
        return 1
    # The same launcher now runs the upgraded lf, which installs the skill of its own version.
    return subprocess.run([install_info.lf_location(), "setup", *(["--yes"] if args.yes else [])]).returncode


def handle_uninstall(args: argparse.Namespace) -> int:
    method = install_info.install_method()
    profiles = ConfigManager().config_path
    print("lf uninstall removes:")
    print(f"  1. The {install_info.SKILL_NAME} skill from your coding agents (npx skills remove -g)")
    print(f"  2. Saved profiles and their keys: {profiles}" + ("" if profiles.exists() else " (none saved)"))
    lf_step = " ".join(UNINSTALL[method]) if method in UNINSTALL else f"pip uninstall {PACKAGE}, which you run"
    print(f"  3. lf itself: {lf_step}")
    if args.dry_run:
        print("Dry run: nothing was removed.")
        return 0
    if not args.yes:
        if sys.stdin is None or not sys.stdin.isatty():
            print("Error: lf uninstall deletes files. Run it in a terminal to confirm, or pass --yes.", file=sys.stderr)
            return 1
        if input("Remove all of these? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing was removed.")
            return 0

    failed = False
    npx, why_not = install_info.find_npx()
    if npx:
        failed |= _run(["npx", *SKILL_REMOVE], exe=npx) != 0
    else:
        print(f"  ✗ {why_not} Remove the skill yourself: npx skills remove -g {install_info.SKILL_NAME}")
        failed = True
    if profiles.exists():
        profiles.unlink()
        print(f"  ✓ Removed {profiles}")
    if method in UNINSTALL:
        failed |= _run(UNINSTALL[method]) != 0
    else:
        print(f"  Remove lf itself with: pip uninstall {PACKAGE}")
    print("✗ Some steps failed; see above." if failed else "✓ lf is uninstalled.")
    return 1 if failed else 0
