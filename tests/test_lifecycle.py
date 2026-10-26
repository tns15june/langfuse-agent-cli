import io
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import TTY, install_skill, link_skill

from langfuse_cli import install_info
from langfuse_cli.cli import main
from langfuse_cli.config import ConfigManager

LF = "/home/me/.local/bin/lf"
SKILL_REMOVE = ["/usr/bin/npx", "--yes", "skills@1", "remove", "-g", "-y", "langfuse-agent-cli"]


class Runner:
    """Stands in for subprocess.run: records each command and returns the queued exit codes."""

    def __init__(self, *codes):
        self.codes, self.calls, self.kwargs = list(codes), [], []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        self.kwargs.append(kwargs)
        return subprocess.CompletedProcess(cmd, self.codes.pop(0) if self.codes else 0)


class RemovingRunner(Runner):
    """Like Runner, but a skills `remove` command deletes the skill folders, as the real one does."""

    def __call__(self, cmd, **kwargs):
        if "remove" in cmd:
            for path in _skill_paths():
                path.unlink() if path.is_symlink() else shutil.rmtree(path)
        return super().__call__(cmd, **kwargs)


def _skill_paths():
    from langfuse_cli.commands import doctor
    dirs = [install_info.AGENTS_DIR / "skills", *(d for _, d in doctor.KNOWN_SKILL_TARGETS)]
    return [p for p in (d / install_info.SKILL_NAME for d in dirs) if p.is_symlink() or p.exists()]


@pytest.fixture
def tools(monkeypatch):
    """uv, pipx and npx on PATH under /usr/bin, the running lf under ~/.local/bin; subprocess.run recorded."""
    runner = Runner()
    paths = {"uv": "/usr/bin/uv", "pipx": "/usr/bin/pipx", "npx": "/usr/bin/npx"}
    monkeypatch.setattr(shutil, "which", lambda name, path=None: paths.get(name))
    monkeypatch.setattr(install_info, "lf_location", lambda: LF)
    monkeypatch.setattr(subprocess, "run", runner)
    return runner


@pytest.fixture
def installed_skill(no_skill_dirs, tmp_path):
    """The shared skill plus its link in the Claude Code folder that no_skill_dirs points doctor at."""
    install_skill()
    return link_skill(tmp_path / "skills")


def method(monkeypatch, name):
    monkeypatch.setattr(install_info, "install_method", lambda prefix=None: name)


def saved_profile():
    ConfigManager().save_profile("default", "http://lf.test", "pk-lf-1", "sk-lf-1")
    return ConfigManager().config_path


# --- upgrade ---------------------------------------------------------------------------------------------

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

    err = capsys.readouterr().err
    assert tools.calls == []
    assert "pip install --upgrade langfuse-agent-cli" in err
    assert "not installed with uv or pipx" in err  # install_method cannot tell pip from conda or a project venv


def test_upgrade_keeps_keys_from_the_installer_but_not_from_the_follow_up_setup(monkeypatch, tools):
    method(monkeypatch, "uv")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-1")

    main(["upgrade", "--yes"])

    installer, setup = tools.kwargs
    assert not [k for k in installer["env"] if k.startswith("LANGFUSE_")]
    assert "env" not in setup  # lf setup reads the credentials from the environment


def test_uninstall_keeps_keys_from_npx_and_the_installer(monkeypatch, tools, installed_skill):
    method(monkeypatch, "uv")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-1")

    main(["uninstall", "--yes"])

    assert tools.kwargs and all(not [k for k in kw["env"] if k.startswith("LANGFUSE_")] for kw in tools.kwargs)


def test_failed_upgrade_does_not_run_setup(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    tools.codes = [2]

    assert main(["upgrade", "--yes"]) == 1

    assert len(tools.calls) == 1
    assert "upgrade failed" in capsys.readouterr().out


def test_upgrade_never_runs_an_installer_from_the_current_folder(monkeypatch, capsys, tools, tmp_path):
    method(monkeypatch, "uv")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: str(tmp_path / f"{name}.exe"))  # tmp_path is the cwd

    assert main(["upgrade", "--yes"]) == 1

    assert tools.calls == []
    assert "current folder" in capsys.readouterr().out


def test_upgrade_runs_setup_with_the_lf_it_was_started_from(monkeypatch, tools):
    method(monkeypatch, "uv")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: {"uv": "/usr/bin/uv", "lf": "/opt/other/lf"}.get(name))

    main(["upgrade", "--yes"])

    assert tools.calls[-1] == [LF, "setup", "--yes"]


# --- uninstall -------------------------------------------------------------------------------------------

def test_uninstall_dry_run_lists_everything_and_removes_nothing(monkeypatch, capsys, tools, installed_skill):
    method(monkeypatch, "uv")
    profiles = saved_profile()

    assert main(["uninstall", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert tools.calls == []
    assert profiles.exists() and installed_skill.is_symlink()
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


@pytest.mark.parametrize("answer", ["", "n", "No"])
def test_uninstall_asks_in_a_terminal_and_no_keeps_everything(monkeypatch, capsys, tools, answer):
    method(monkeypatch, "uv")
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)  # Enter means no
    profiles = saved_profile()

    assert main(["uninstall"]) == 0

    assert tools.calls == []
    assert profiles.exists()
    assert "Nothing was removed" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["y", "Y", "yes"])
def test_uninstall_accepts_yes_answers(monkeypatch, tools, answer):
    method(monkeypatch, "uv")
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    profiles = saved_profile()

    main(["uninstall"])

    assert not profiles.exists()


def test_uninstall_treats_end_of_input_at_the_prompt_as_no(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    monkeypatch.setattr("sys.stdin", TTY())

    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    profiles = saved_profile()

    assert main(["uninstall"]) == 0

    assert tools.calls == [] and profiles.exists()
    assert "Nothing was removed" in capsys.readouterr().out


def test_ctrl_c_at_a_prompt_ends_quietly_with_exit_130(monkeypatch, capsys, tools):
    method(monkeypatch, "uv")
    monkeypatch.setattr("sys.stdin", TTY())

    def interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    profiles = saved_profile()

    assert main(["uninstall"]) == 130

    assert tools.calls == [] and profiles.exists()
    assert "Interrupted" in capsys.readouterr().err


def test_uninstall_yes_removes_skill_then_profiles_then_lf(monkeypatch, capsys, tools, installed_skill):
    method(monkeypatch, "uv")
    runner = RemovingRunner()
    monkeypatch.setattr(subprocess, "run", runner)
    profiles = saved_profile()

    assert main(["uninstall", "--yes"]) == 0

    assert runner.calls == [SKILL_REMOVE, ["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"]]
    assert not profiles.exists() and not installed_skill.is_symlink()
    assert "✓ lf is uninstalled." in capsys.readouterr().out


def test_uninstall_checks_the_disk_not_npx_exit_code(monkeypatch, capsys, tools, installed_skill):
    method(monkeypatch, "uv")  # the skills CLI exits 0 even when it could not remove the files

    assert main(["uninstall", "--yes"]) == 1

    out = capsys.readouterr().out
    assert installed_skill.is_symlink()
    assert "still" in out and str(installed_skill) in out
    assert tools.calls[-1] == ["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"]  # kept going


def test_uninstall_without_npx_fails_only_when_the_skill_is_on_disk(monkeypatch, capsys, tools, installed_skill):
    method(monkeypatch, "uv")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: {"uv": "/usr/bin/uv"}.get(name))

    assert main(["uninstall", "--yes"]) == 1

    out = capsys.readouterr().out
    assert "npx skills remove -g langfuse-agent-cli" in out
    assert tools.calls == [["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"]]


def test_uninstall_with_no_skill_installed_skips_npx(monkeypatch, capsys, tools, no_skill_dirs):
    method(monkeypatch, "uv")
    monkeypatch.setattr(shutil, "which", lambda name, path=None: {"uv": "/usr/bin/uv"}.get(name))  # no Node either

    assert main(["uninstall", "--yes"]) == 0

    assert "not installed" in capsys.readouterr().out.lower()
    assert tools.calls == [["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"]]


def test_uninstall_reports_a_profiles_file_it_cannot_delete_and_keeps_going(monkeypatch, capsys, tools,
                                                                           no_skill_dirs):
    method(monkeypatch, "uv")
    saved_profile()

    def denied(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "unlink", denied)

    assert main(["uninstall", "--yes"]) == 1

    out = capsys.readouterr().out
    assert "Could not remove" in out and "holds your keys" in out
    assert tools.calls[-1] == ["/usr/bin/uv", "tool", "uninstall", "langfuse-agent-cli"]


def test_uninstall_of_a_pip_install_is_honest_about_what_remains(monkeypatch, capsys, tools, no_skill_dirs):
    method(monkeypatch, "pip")
    profiles = saved_profile()

    assert main(["uninstall", "--yes"]) == 0

    out = capsys.readouterr().out
    assert not profiles.exists()
    assert "pip uninstall langfuse-agent-cli" in out
    assert "lf is uninstalled" not in out
    assert "lf itself stays" in out
    assert all("uninstall" not in " ".join(call) for call in tools.calls)
