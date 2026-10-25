import json

import pytest
from helpers import route_doctor

from langfuse_cli import __version__, install_info
from langfuse_cli.cli import main

FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
PYPI = "/pypi/langfuse-agent-cli/json"


def install_skill(ref):
    """What `npx skills add ... -g` leaves behind: the skill folder and its entry in the global lock."""
    skill = install_info.AGENTS_DIR / "skills" / "langfuse-agent-cli"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: langfuse-agent-cli\n---\n")
    lock = {"version": 3, "skills": {"langfuse-agent-cli": {"source": "tns15june/langfuse-agent-cli", "ref": ref}}}
    (install_info.AGENTS_DIR / ".skill-lock.json").write_text(json.dumps(lock))


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


def test_doctor_warns_when_the_skill_is_older_than_lf(fake_api, capsys, no_skill_dirs):
    install_skill("v0.2.0")
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert f"The installed skill is v0.2.0; run 'lf setup' to install v{__version__}" in capsys.readouterr().out
