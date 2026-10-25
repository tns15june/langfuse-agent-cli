import io
import shutil
import subprocess

import pytest
from helpers import route_doctor

from langfuse_cli import __version__
from langfuse_cli.cli import main
from langfuse_cli.commands.doctor import SKILL_SOURCE
from langfuse_cli.config import ConfigManager

FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
LATER = f"To install it later: npx skills add {SKILL_SOURCE} -g"


class TTY(io.StringIO):
    def isatty(self):
        return True


class Runner:
    """Stands in for subprocess.run and records each call."""

    def __init__(self, returncode=0, exc=None):
        self.returncode, self.exc, self.calls = returncode, exc, []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self.exc:
            raise self.exc
        return subprocess.CompletedProcess(cmd, self.returncode)


@pytest.fixture
def npx(monkeypatch):
    runner = Runner()
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/npx" if name == "npx" else None)
    monkeypatch.setattr(subprocess, "run", runner)
    return runner


@pytest.fixture
def no_prompts(monkeypatch):
    def prompted(*_args):
        raise AssertionError("lf setup prompted")

    monkeypatch.setattr("builtins.input", prompted)
    monkeypatch.setattr("getpass.getpass", prompted)


def test_setup_yes_never_prompts_and_installs_the_pinned_skill(fake_api, monkeypatch, capsys, npx, no_prompts,
                                                               no_skill_dirs):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://lf.test")

    code = main(["setup", "--yes"])

    out = capsys.readouterr().out
    cmd, kwargs = npx.calls[0]
    assert code == 1  # doctor: no keys
    assert cmd == ["/usr/bin/npx", "--yes", "skills@1", "add", SKILL_SOURCE, "-g", "-y"]
    assert SKILL_SOURCE.endswith(f"/tree/v{__version__}/skills/langfuse-agent-cli")
    assert "lf auth login" in out
    assert not [name for name in kwargs["env"] if name.startswith("LANGFUSE_")]
    assert kwargs["timeout"] == 300


def test_setup_without_a_terminal_does_not_prompt(fake_api, monkeypatch, npx, no_prompts, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", io.StringIO())

    assert main(["setup"]) == 1
    assert "-y" in npx.calls[0][0]


def test_setup_keeps_working_credentials(fake_api, capsys, npx, no_prompts, no_skill_dirs):
    route_doctor(fake_api)

    code = main(["setup", "--yes", *FLAGS])

    assert code == 0
    assert "✓ Using flags credentials for http://lf.test" in capsys.readouterr().out


def test_setup_interactive_logs_in_and_can_skip_the_skill(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    answers = iter(["http://lf.test", "pk-lf-1", "n"])  # host, public key, install the skill?
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-lf-1")
    route_doctor(fake_api)

    code = main(["setup"])

    cfg = ConfigManager()
    assert code == 0
    assert cfg.list_profiles()["default"].host == "http://lf.test"
    assert cfg.get_current_profile_name() == "default"
    assert npx.calls == []
    assert LATER in capsys.readouterr().out


def test_setup_interactive_install_lets_the_user_pick_agents(fake_api, monkeypatch, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": "")  # Enter accepts the install
    route_doctor(fake_api)

    assert main(["setup", *FLAGS]) == 0

    cmd, kwargs = npx.calls[0]
    assert "-y" not in cmd  # the skills CLI asks which agents
    assert kwargs["timeout"] is None


@pytest.mark.parametrize("npx_path,runner", [
    (None, Runner()),
    ("/usr/bin/npx", Runner(returncode=1)),
    ("/usr/bin/npx", Runner(exc=subprocess.TimeoutExpired("npx", 300))),
], ids=["missing", "fails", "times-out"])
def test_setup_prints_the_command_when_npx_is_missing_or_fails(fake_api, monkeypatch, capsys, no_prompts,
                                                               no_skill_dirs, npx_path, runner):
    monkeypatch.setattr(shutil, "which", lambda name: npx_path)
    monkeypatch.setattr(subprocess, "run", runner)
    route_doctor(fake_api)

    assert main(["setup", "--yes", *FLAGS]) == 0

    out = capsys.readouterr().out
    assert LATER in out
    assert "System Diagnostics" in out  # doctor still ran


def test_doctor_hint_points_to_setup(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert "Run 'lf setup'" in capsys.readouterr().out
