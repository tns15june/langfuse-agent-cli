"""Where lf is installed, which skill version is installed, and whether PyPI has a newer lf."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple

import requests

from langfuse_cli import __version__

PACKAGE = "langfuse-agent-cli"
SKILL_NAME = "langfuse-agent-cli"
# `npx skills add -g` keeps the skill and its lock file here, whatever agents it links the skill into.
AGENTS_DIR = Path.home() / ".agents"


def install_method(prefix: str = sys.prefix) -> str:
    """'uv' or 'pipx' when lf runs from one of their tool environments, else 'pip'."""
    path = prefix.replace("\\", "/") + "/"
    if "/uv/tools/" in path:
        return "uv"
    if "/pipx/venvs/" in path:
        return "pipx"
    return "pip"


def find_npx() -> Tuple[Optional[str], str]:
    """The npx to run, or (None, why not)."""
    npx = shutil.which("npx")
    if npx is None:
        return None, "npx not found; the skills CLI needs Node.js 22.20 or later."
    # On Windows, which() searches the current folder first; never run an npx that a project folder supplies.
    if os.path.normcase(os.path.realpath(os.path.dirname(npx))) == os.path.normcase(os.path.realpath(os.getcwd())):
        return None, f"Not running {npx}: it is in the current folder. Run lf from another folder."
    return npx, ""


def lf_location() -> str:
    return os.path.abspath(sys.argv[0])


def installed_skill_ref() -> Optional[str]:
    """The ref (e.g. 'v0.4.0') the global skill was installed from, or None when it is not installed."""
    if not (AGENTS_DIR / "skills" / SKILL_NAME / "SKILL.md").exists():
        return None
    try:
        ref = json.loads((AGENTS_DIR / ".skill-lock.json").read_text(encoding="utf-8"))["skills"][SKILL_NAME]["ref"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return ref if isinstance(ref, str) else None


def latest_version(timeout: float = 3.0) -> Optional[str]:
    """The newest version on PyPI, or None when the check is off (LF_NO_UPDATE_CHECK) or fails."""
    if os.environ.get("LF_NO_UPDATE_CHECK"):
        return None
    try:
        resp = requests.get(f"https://pypi.org/pypi/{PACKAGE}/json", timeout=timeout)
        resp.raise_for_status()
        version = resp.json()["info"]["version"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
    return version if isinstance(version, str) else None


def is_newer(candidate: str, current: str = __version__) -> bool:
    def key(version: str) -> tuple:
        return tuple(int(part) if part.isdigit() else 0 for part in version.split(".")[:3])
    return key(candidate) > key(current)
