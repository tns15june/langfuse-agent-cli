import io
import shutil
import subprocess

import pytest

from langfuse_cli import install_info
from langfuse_cli.cli import main
from langfuse_cli.config import ConfigManager

LF = "/home/me/.local/bin/lf"


class TTY(io.StringIO):
    def isatty(self):
        return True


class Runner:
    """Stands in for subprocess.run: records each command and returns the queued exit codes."""

    def __init__(self, *codes):
        self.codes, self.calls = list(codes), []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.codes.pop(0) if self.codes else 0)


@pytest.fixture
def tools(monkeypatch):
    """uv, pipx, npx and lf all on PATH under /usr/bin (lf under ~/.local/bin); subprocess.run recorded."""
    runner = Runner()
    paths = {"uv": "/usr/bin/uv", "pipx": "/usr/bin/pipx", "npx": "/usr/bin/npx", "lf": LF}
    monkeypatch.setattr(shutil, "which", lambda name: paths.get(name))
    monkeypatch.setattr(subprocess, "run", runner)
    return runner


def method(monkeypatch, name):
    monkeypatch.setattr(install_info, "install_method", lambda prefix=None: name)


@pytest.mark.parametrize("installer,upgrade", [
    ("uv", ["/usr/bin/uv", "tool", "upgrade", "langfuse-agent-cli"]),
    ("pipx", ["/usr/bin/pipx", "upgrade", "langfuse-agent-cli"]),
])
def test_upgrade_uses_the_installer_then_runs_the_new_setup(monkeypatch, tools, installer, upgrade):
    method(monkeypatch, installer)

    assert main(["upgrade", "--yes"]) == 0

    assert tools.calls == [upgrade, [LF, "setup", "--yes"]]


def test_upgrade_in_a_terminal_lets_setup_ask(monkeypatch, tools):
    method(monkeypatch, "uv")

    main(["upgrade"])

    assert tools.calls[-1] == [LF, "setup"]


def test_upgrade_of_a_pip_install_explains_and_runs_nothing(monkeypatch, capsys, tools):
    method(monkeypatch, "pip")

    assert main(["upgrade", "--yes"]) == 1

    assert tools.calls == []
    assert "pip install --upgrade langfuse-agent-cli" in capsys.readouterr().err


def test_failed_upgrade_does_not_run_setup(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    tools.codes = [2]

    assert main(["upgrade", "--yes"]) == 1

    assert len(tools.calls) == 1
    assert "upgrade failed" in capsys.readouterr().out


def saved_profile():
    ConfigManager().save_profile("default", "http://lf.test", "pk-lf-1", "sk-lf-1")
    return ConfigManager().config_path


def test_uninstall_dry_run_lists_everything_and_removes_nothing(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    profiles = saved_profile()

    assert main(["uninstall", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert tools.calls == []
    assert profiles.exists()
    assert "skill" in out and str(profiles) in out and "uv tool uninstall langfuse-agent-cli" in out
    assert "nothing was removed" in out.lower()


def test_uninstall_without_yes_and_without_a_terminal_refuses(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    monkeypatch.setattr("sys.stdin", io.StringIO())
    profiles = saved_profile()

    assert main(["uninstall"]) == 1

    assert tools.calls == []
    assert profiles.exists()
    assert "--yes" in capsys.readouterr().err


def test_uninstall_asks_in_a_terminal_and_no_keeps_everything(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": "")  # Enter means no
    profiles = saved_profile()

    assert main(["uninstall"]) == 0

    assert tools.calls == []
    assert profiles.exists()


def test_uninstall_yes_removes_skill_then_profiles_then_lf(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    profiles = saved_profile()

    assert main(["uninstall", "--yes"]) == 0

    assert tools.calls == [
        ["/usr/bin/npx", "--yes", "skills@1", "remove", "-g", "-y", "langfuse-agent-cli"],
        ["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"],
    ]
    assert not profiles.exists()


def test_uninstall_keeps_going_and_exits_1_when_a_step_fails(monkeypatch, capsys, tools):
    method(monkeypatch, "pipx")
    tools.codes = [1, 0]  # skill removal fails, lf removal works
    profiles = saved_profile()

    assert main(["uninstall", "--yes"]) == 1

    assert tools.calls[-1] == ["/usr/bin/pipx", "uninstall", "langfuse-agent-cli"]
    assert not profiles.exists()


def test_uninstall_without_npx_says_how_to_remove_the_skill(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    monkeypatch.setattr(shutil, "which", lambda name: {"uv": "/usr/bin/uv"}.get(name))

    assert main(["uninstall", "--yes"]) == 1

    assert "langfuse-agent-cli" in capsys.readouterr().out
    assert tools.calls == [["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"]]


def test_uninstall_of_a_pip_install_says_how_to_remove_lf(monkeypatch, capsys, tools):
    method(monkeypatch, "pip")

    main(["uninstall", "--yes"])

    assert "pip uninstall langfuse-agent-cli" in capsys.readouterr().out
    assert all("uninstall" not in " ".join(call) for call in tools.calls)
