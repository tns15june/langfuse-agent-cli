"""One-step setup: credentials, the agent skill, then doctor."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from langfuse_cli import __version__, install_info
from langfuse_cli.client import LangfuseAPIError, LangfuseClient
from langfuse_cli.commands import doctor
from langfuse_cli.commands.auth import ask, login
from langfuse_cli.commands.doctor import SKILL_NAME, SKILL_SOURCE, handle_doctor
from langfuse_cli.config import ConfigError, ConfigManager, resolve_from_args

INSTALL_LATER = f"  To install it later: npx skills@1 add {SKILL_SOURCE} -g"
TRY_IT = ("Why did my LLM app fail in the last hour?", "What did we spend on each model this week?",
          "Which step of my agent is the slowest today?")
SOURCE_NAMES = {"env": "the LANGFUSE_* environment variables", "env-file": "the --env-file file",
                "flags": "--public-key and --secret-key"}


def _credentials(args: argparse.Namespace, interactive: bool) -> bool:
    """False when --profile-name names a profile that does not exist and cannot be created here."""
    name = args.profile_name
    if name and name not in ConfigManager().list_profiles():  # a new profile: nothing to check yet
        if not interactive:
            print(f"  – Login skipped: there is no profile '{name}' yet, and lf setup never asks for keys with --yes "
                  f"or without a terminal. Ask the user to run 'lf setup --profile-name {name}' in their own terminal.")
            return False
        default_host = args.host or "https://cloud.langfuse.com"
        host = ask(f"  Langfuse host [{default_host}]: ") or default_host
        login(ConfigManager(), name, host, None, None, set_default=True)
        args.profile = name  # doctor checks the profile just saved
        return True
    if name:
        args.profile = name
    try:
        prof = resolve_from_args(args)
    except ConfigError as e:  # doctor reports it again; the skill step still runs
        print(f"  ✗ {e}")
        return True
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
            return True
    if not rejected:  # new keys would not help; asking for them invites overwriting good ones
        print("  – Login skipped: the keys were not rejected; check the host and that the server is up.")
    elif prof.source != "profile":  # these sources outrank saved profiles, so a login here would change nothing
        print(f"  – Login skipped: these keys come from {SOURCE_NAMES[prof.source]}, which take precedence over "
              "saved profiles. Fix or unset them, then run lf setup again.")
    elif not interactive:
        print("  – Login skipped: lf setup never asks for keys with --yes or without a terminal. "
              "Ask the user to run 'lf setup' in their own terminal.")
    else:
        host = ask(f"  Langfuse host [{prof.host}]: ") or prof.host
        login(ConfigManager(), prof.name, host, None, None, set_default=True)  # keys that failed are asked for again
    return True


def _linked_into_an_agent() -> bool:
    """True when some agent folder, not only the shared ~/.agents copy, has the skill."""
    shared = install_info.AGENTS_DIR / "skills"
    return any((d / SKILL_NAME).exists() for _, d in doctor.KNOWN_SKILL_TARGETS if d != shared)


def _install_skill(interactive: bool) -> str:
    """Install the skill with the skills CLI: 'installed', 'current', 'declined' or 'failed'."""
    # A removed agent link or a newly installed agent needs the (idempotent) install again.
    if install_info.installed_skill_ref() == f"v{__version__}" and _linked_into_an_agent():
        print(f"  ✓ Skill v{__version__} is already installed.")
        return "current"
    npx, why_not = install_info.find_npx()
    if npx is None:
        print(f"  ✗ {why_not}")
        print(INSTALL_LATER)
        return "failed"
    if interactive:
        answer = ask(f"  Install the {SKILL_NAME} skill for your coding agents? [Y/n] ")
        if answer is None or answer.lower() in ("n", "no"):  # end of input means no
            print(INSTALL_LATER)
            return "declined"
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
        return "failed"
    return "installed"


def handle_setup(args: argparse.Namespace) -> int:
    interactive = not args.yes and sys.stdin is not None and sys.stdin.isatty()
    print("\nLangfuse Agent CLI Setup")
    print("\n1. Credentials")
    created = _credentials(args, interactive)
    print("\n2. Agent Skill")
    skill = _install_skill(interactive)
    print("\n3. Check")
    code = handle_doctor(args)
    if skill == "failed":
        print("  ✗ lf setup did not install the skill (see step 2); any copy listed above is from an earlier install.")
        return 1
    if not created:
        print(f"  ✗ lf setup did not create the profile '{args.profile_name}' (see step 1).")
        return 1
    if code == 0 and skill in ("installed", "current"):
        print("\nTry it: start a new session of your coding agent and ask, for example:")
        for question in TRY_IT:
            print(f'  "{question}"')
    return code
