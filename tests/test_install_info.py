import os
import shutil
import stat

import pytest
from helpers import install_skill, route_doctor

from langfuse_cli import __version__, install_info
from langfuse_cli.cli import main

FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
PYPI = "/pypi/langfuse-agent-cli/json"


@pytest.mark.parametrize("prefix,method", [
    ("/Users/me/.local/share/uv/tools/langfuse-agent-cli", "uv"),
    ("/home/me/.local/pipx/venvs/langfuse-agent-cli", "pipx"),
    ("/home/me/.local/share/pipx/venvs/langfuse-agent-cli", "pipx"),
    (r"C:\Users\me\AppData\Roaming\uv\tools\langfuse-agent-cli", "uv"),
    ("/usr/local", "pip"),
])
def test_install_method_from_the_environment_path(prefix, method):
    assert install_info.install_method(prefix) == method


@pytest.mark.parametrize("candidate,current,newer", [
    ("0.4.1", "0.4.0", True), ("0.4.0", "0.4.0", False), ("0.10.0", "0.9.9", True), ("0.3.9", "0.4.0", False),
    ("0.4.0rc1", "0.4.0", False), ("0.4.1", "0.4.0rc1", True), ("1.0", "0.9.9", True),
])
def test_is_newer(candidate, current, newer):
    assert install_info.is_newer(candidate, current) is newer


def test_installed_skill_ref_reads_the_global_lock():
    assert install_info.installed_skill_ref() is None
    install_skill("v0.3.0")
    assert install_info.installed_skill_ref() == "v0.3.0"


def test_lock_entry_without_the_skill_folder_counts_as_not_installed():
    install_skill("v0.3.0")
    (install_info.AGENTS_DIR / "skills" / "langfuse-agent-cli" / "SKILL.md").unlink()
    assert install_info.installed_skill_ref() is None


def test_doctor_shows_where_lf_is_installed(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert "Installed at:" in capsys.readouterr().out


@pytest.mark.parametrize("pypi,expected", [
    ({"info": {"version": "9.9.9"}}, "Version 9.9.9 is available: run 'lf upgrade'"),
    ({"info": {"version": __version__}}, "✓ Latest version"),
])
def test_doctor_checks_pypi_for_a_newer_version(fake_api, monkeypatch, capsys, no_skill_dirs, pypi, expected):
    monkeypatch.delenv("LF_NO_UPDATE_CHECK")
    route_doctor(fake_api)
    fake_api.route("GET", PYPI, json=pypi)

    assert main(["doctor", *FLAGS]) == 0
    assert expected in capsys.readouterr().out


def test_doctor_stays_quiet_when_the_update_check_fails(fake_api, monkeypatch, capsys, no_skill_dirs):
    monkeypatch.delenv("LF_NO_UPDATE_CHECK")
    route_doctor(fake_api)
    fake_api.route("GET", PYPI, status=503, text="unavailable", content_type="text/plain")

    assert main(["doctor", *FLAGS]) == 0
    out = capsys.readouterr().out
    assert "Latest version" not in out and "is available" not in out
    assert "Could not reach pypi.org" in out


def test_doctor_warns_when_the_skill_is_older_than_lf(fake_api, capsys, no_skill_dirs):
    install_skill("v0.2.0")
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert f"The installed skill is v0.2.0; run 'lf setup' to install v{__version__}" in capsys.readouterr().out


@pytest.mark.parametrize("lock", [
    None, "{not json", '{"skills": {}}', '{"skills": {"langfuse-agent-cli": {"ref": 3}}}',
    '{"skills": {"langfuse-agent-cli": "v0.3.0"}}',
], ids=["no-lock", "bad-json", "missing-entry", "ref-not-a-string", "entry-not-a-dict"])
def test_skill_folder_without_a_readable_lock_counts_as_unknown(lock):
    install_skill("v0.3.0")
    path = install_info.AGENTS_DIR / ".skill-lock.json"
    if lock is None:
        path.unlink()
    else:
        path.write_text(lock)
    assert install_info.installed_skill_ref() is None


def test_skill_lock_follows_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    install_skill("v0.3.0", lock_path=tmp_path / "state" / "skills" / ".skill-lock.json")

    assert install_info.installed_skill_ref() == "v0.3.0"


def test_find_tool_also_looks_next_to_the_lf_launcher(monkeypatch, tmp_path):
    bin_dir = tmp_path / "home" / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("uv", "lf"):
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\n")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(install_info, "lf_location", lambda: str(bin_dir / "lf"))
    monkeypatch.chdir(tmp_path)  # not the folder the tools live in

    assert install_info.find_tool("uv") == (str(bin_dir / "uv"), "")
    assert shutil.which("uv", path=os.environ["PATH"]) is None  # PATH alone would not have found it


def test_doctor_does_not_warn_when_the_skill_matches_lf(fake_api, capsys, no_skill_dirs):
    install_skill()
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert "The installed skill is" not in capsys.readouterr().out


def test_doctor_says_when_the_update_check_is_off(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert "Update check off (LF_NO_UPDATE_CHECK is set)" in capsys.readouterr().out
