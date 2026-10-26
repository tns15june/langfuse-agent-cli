"""lf upgrade and lf uninstall: change lf itself, its agent skill and its saved profiles."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from langfuse_cli import __version__, install_info
from langfuse_cli.commands import doctor
from langfuse_cli.commands.auth import ask
from langfuse_cli.config import ConfigManager

PACKAGE = install_info.PACKAGE
# Both refresh the package index: its cached copy can hide a release made minutes ago.
UPGRADE = {"uv": ["uv", "tool", "upgrade", "--no-cache", PACKAGE],
           "pipx": ["pipx", "upgrade", "--pip-args=--no-cache-dir", PACKAGE]}
UNINSTALL = {"uv": ["uv", "tool", "uninstall", PACKAGE], "pipx": ["pipx", "uninstall", PACKAGE]}
SKILL_REMOVE = ["npx", "--yes", "skills@1", "remove", "-g", "-y", install_info.SKILL_NAME]


def _run(cmd: List[str], exe: Optional[str] = None) -> int:
    """Run an installer command, shown to the user first; a missing or refused program counts as a failure."""
    if exe is None:
        exe, why_not = install_info.find_tool(cmd[0])
        if exe is None:
            print(f"  ✗ {why_not}")
            return 127
    print(f"  Running: {' '.join(cmd)}", flush=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("LANGFUSE_")}  # keys stay out of installers
    try:
        return subprocess.run([exe, *cmd[1:]], env=env).returncode
    except OSError as e:
        print(f"  ✗ {e}")
        return 1


def handle_upgrade(args: argparse.Namespace) -> int:
    method = install_info.install_method()
    if method not in UPGRADE:
        print(f"lf was not installed with uv or pipx. Upgrade it the way it was installed (with pip: "
              f"pip install --upgrade {PACKAGE}), then run lf setup.", file=sys.stderr)
        return 1
    print(f"Upgrading lf {__version__}, installed with {method}")
    code = _run(UPGRADE[method])
    if code:
        print(f"✗ The upgrade failed (exit code {code}); lf {__version__} is unchanged.")
        return 1
    launcher = install_info.lf_location()
    try:
        now = subprocess.run([launcher, "--version"], capture_output=True, text=True).stdout.split()[-1]
    except (OSError, IndexError):
        now = __version__
    if now == __version__:
        latest = install_info.latest_version()
        if latest and install_info.is_newer(latest):
            print(f"✗ lf is still {__version__}, but PyPI lists {latest}. Package indexes cache for a few minutes; "
                  "run lf upgrade again shortly.")
            return 1
        print(f"✓ lf {__version__} is already the latest version.")
    else:
        print(f"✓ lf {__version__} → {now}")
    # The same launcher now runs the upgraded lf, which installs the skill of its own version.
    return subprocess.run([launcher, "setup", *(["--yes"] if args.yes else [])]).returncode


def _skill_paths() -> List[Path]:
    """Where the skill still exists: the shared copy and every agent folder doctor knows, links included."""
    dirs = [install_info.AGENTS_DIR / "skills", *(d for _, d in doctor.KNOWN_SKILL_TARGETS)]
    paths: List[Path] = []
    for path in (d / install_info.SKILL_NAME for d in dirs):
        if (path.is_symlink() or path.exists()) and path not in paths:
            paths.append(path)
    return paths


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
        if (ask("Remove all of these? [y/N] ") or "").lower() not in ("y", "yes"):
            print("Nothing was removed.")
            return 0

    failed = False
    if not _skill_paths():
        print("  ✓ The skill is not installed.")
    else:
        npx, why_not = install_info.find_npx()
        if npx:
            _run(SKILL_REMOVE, exe=npx)  # the skills CLI exits 0 even when it could not remove; the disk decides
        else:
            print(f"  ✗ {why_not}")
        left = _skill_paths()
        if left:
            print("  ✗ The skill is still at: " + ", ".join(str(p) for p in left))
            print(f"    Remove it with: npx skills remove -g {install_info.SKILL_NAME}, or delete those folders.")
            failed = True
        else:
            print("  ✓ Skill removed.")
    if profiles.exists():
        try:
            profiles.unlink()
            print(f"  ✓ Removed {profiles}")
        except OSError as e:
            print(f"  ✗ Could not remove {profiles}: {e.strerror or e}. Delete it yourself; it holds your keys.")
            failed = True
    lf_removed = False
    if method in UNINSTALL:
        lf_removed = _run(UNINSTALL[method]) == 0
        failed |= not lf_removed
    else:
        print(f"  Remove lf itself with: pip uninstall {PACKAGE}")
    if failed:
        print("✗ Some steps failed; see above.")
    elif lf_removed:
        print("✓ lf is uninstalled.")
    else:
        print(f"✓ The skill and the saved profiles are removed; lf itself stays until you run: pip uninstall {PACKAGE}")
    return 1 if failed else 0
