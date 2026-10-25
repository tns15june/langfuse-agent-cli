"""Every `lf ...` command shown in the docs must be accepted by the real parser."""
import re
import shlex
from pathlib import Path

import pytest

from langfuse_cli.cli import create_parser

ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = sorted((ROOT / "skills").rglob("*.md")) + [ROOT / "README.md", ROOT / "INSTALL.md"]
INLINE_COMMAND = re.compile(r"`(lf [^`]+)`")


def doc_commands(path: Path) -> list:
    """`lf ...` lines in fenced code blocks plus inline `lf ...` code spans, as argv lists."""
    commands, in_fence = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            stripped = stripped.removeprefix("$ ")
            if stripped.startswith("lf "):
                commands.append(shlex.split(stripped.split("  #")[0]))
        else:
            commands.extend(shlex.split(m) for m in INLINE_COMMAND.findall(line))
    return commands


DOC_COMMANDS = [(p.relative_to(ROOT).as_posix(), argv) for p in DOC_FILES for argv in doc_commands(p)]


def test_docs_contain_commands():
    assert len(DOC_COMMANDS) >= 10


@pytest.mark.parametrize("source,argv", DOC_COMMANDS, ids=lambda v: v if isinstance(v, str) else " ".join(v)[:60])
def test_documented_commands_parse(source, argv):
    try:
        create_parser().parse_args(argv[1:])
    except SystemExit as exc:
        if exc.code not in (0, None):  # --version and --help exit 0 on purpose
            pytest.fail(f"{source}: documented command does not parse: {' '.join(argv)}")


def test_hosted_agent_guide_matches_install_md():
    """docs/AGENTS.md is the TWG-style URL agents are given; it must be the same text as INSTALL.md."""
    hosted = (ROOT / "docs" / "AGENTS.md").read_text(encoding="utf-8")
    assert hosted == (ROOT / "INSTALL.md").read_text(encoding="utf-8")
