import io
import shutil
import subprocess

import pytest
import requests
from helpers import TTY, install_skill, link_skill, route_doctor

from langfuse_cli import __version__
from langfuse_cli.cli import main
from langfuse_cli.commands.doctor import SKILL_SOURCE
from langfuse_cli.config import ConfigManager

FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
LATER = f"To install it later: npx skills@1 add {SKILL_SOURCE} -g"


class Runner:
    """Stands in for subprocess.run and records each call."""

    def __init__(self, returncode=0, exc=None):
        self.returncode, self.exc, self.calls = returncode, exc, []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self.exc:
            raise self.exc
        return subprocess.CompletedProcess(cmd, self.returncode)


def fail(*_args):
    raise AssertionError("lf setup prompted")


def refused(*_args, **_kwargs):
    raise requests.exceptions.ConnectionError("Connection refused")


def sections(out):
    """setup's output split into its three steps."""
    credentials, rest = out.split("1. Credentials", 1)[1].split("2. Agent Skill", 1)
    skill, check = rest.split("3. Check", 1)
    return credentials, skill, check


@pytest.fixture
def npx(monkeypatch):
    runner = Runner()
    monkeypatch.setattr(shutil, "which", lambda name, path=None: "/usr/bin/npx" if name == "npx" else None)
    monkeypatch.setattr(subprocess, "run", runner)
    return runner


@pytest.fixture
def no_prompts(monkeypatch):
    monkeypatch.setattr("builtins.input", fail)
    monkeypatch.setattr("getpass.getpass", fail)


def test_setup_yes_never_prompts_and_installs_the_pinned_skill(fake_api, monkeypatch, capsys, npx, no_prompts,
                                                               no_skill_dirs):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://lf.test")

    code = main(["setup", "--yes"])

    credentials, skill, _ = sections(capsys.readouterr().out)
    cmd, kwargs = npx.calls[0]
    assert code == 1  # doctor: no keys
    assert cmd == ["/usr/bin/npx", "--yes", "skills@1", "add", SKILL_SOURCE, "-g", "-y"]
    assert SKILL_SOURCE.endswith(f"/tree/v{__version__}/skills/langfuse-agent-cli")
    assert f"Running: npx --yes skills@1 add {SKILL_SOURCE} -g -y" in skill
    assert "To install it later" not in skill
    assert "Ask the user to run 'lf setup'" in credentials
    assert not [name for name in kwargs["env"] if name.startswith("LANGFUSE_")]
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["timeout"] == 90


def test_setup_yes_never_prompts_in_a_terminal(fake_api, monkeypatch, capsys, npx, no_prompts, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())  # agent harnesses that run commands in a pseudo-terminal

    assert main(["setup", "--yes"]) == 1

    assert npx.calls[0][0][-1] == "-y"
    assert "Login skipped" in sections(capsys.readouterr().out)[0]


@pytest.mark.parametrize("stdin", [io.StringIO(), None], ids=["not-a-terminal", "closed"])
def test_setup_without_a_terminal_does_not_prompt(fake_api, monkeypatch, npx, no_prompts, no_skill_dirs, stdin):
    monkeypatch.setattr("sys.stdin", stdin)

    assert main(["setup"]) == 1
    assert "-y" in npx.calls[0][0]


def test_setup_keeps_working_credentials(fake_api, capsys, npx, no_prompts, no_skill_dirs):
    route_doctor(fake_api)

    code = main(["setup", "--yes", *FLAGS])

    credentials = sections(capsys.readouterr().out)[0]
    assert code == 0
    assert "✓ Using flags credentials for http://lf.test" in credentials
    assert "Login skipped" not in credentials


@pytest.mark.parametrize("failure,expected", [
    ("rejected", "Ask the user to run 'lf setup'"),
    ("unreachable", "the keys were not rejected"),
])
def test_setup_yes_with_failing_credentials_still_installs_and_checks(fake_api, monkeypatch, capsys, npx, no_prompts,
                                                                      no_skill_dirs, failure, expected):
    ConfigManager().save_profile("default", "http://lf.test", "pk", "sk")
    if failure == "rejected":
        route_doctor(fake_api, projects_status=401)
    else:
        monkeypatch.setattr(requests.Session, "request", refused)

    assert main(["setup", "--yes"]) == 1

    credentials, _, check = sections(capsys.readouterr().out)
    assert "✗" in credentials and expected in credentials
    assert npx.calls
    assert "System Diagnostics" in check


def test_setup_keeps_saved_keys_when_the_server_is_down(monkeypatch, npx, no_skill_dirs):
    ConfigManager().save_profile("default", "http://localhost:3000", "pk-lf-good", "sk-lf-good")
    monkeypatch.setattr(requests.Session, "request", refused)
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": "")  # Enter at every prompt
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "")

    assert main(["setup"]) == 1

    saved = ConfigManager().list_profiles()["default"]
    assert (saved.public_key, saved.secret_key) == ("pk-lf-good", "sk-lf-good")


def test_setup_does_not_save_rejected_flag_keys_over_a_profile(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    ConfigManager().save_profile("default", "http://lf.test", "pk-lf-good", "sk-lf-good")
    route_doctor(fake_api, projects_status=401)
    monkeypatch.setattr("sys.stdin", TTY())
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt="": asked.append(prompt) or "n")
    monkeypatch.setattr("getpass.getpass", fail)

    assert main(["setup", "--public-key", "pk-bad", "--secret-key", "sk-bad"]) == 1

    saved = ConfigManager().list_profiles()["default"]
    assert (saved.public_key, saved.secret_key) == ("pk-lf-good", "sk-lf-good")
    assert len(asked) == 1 and "Install the" in asked[0]  # no host or key prompt
    assert "--public-key and --secret-key" in sections(capsys.readouterr().out)[0]


def test_setup_does_not_log_in_over_env_credentials(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-stale")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-stale")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://lf.test")
    route_doctor(fake_api, projects_status=401)
    monkeypatch.setattr("sys.stdin", TTY())
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt="": asked.append(prompt) or "n")
    monkeypatch.setattr("getpass.getpass", fail)

    assert main(["setup"]) == 1

    assert len(asked) == 1 and "Install the" in asked[0]
    assert ConfigManager().list_profiles() == {}
    assert "LANGFUSE_* environment variables" in sections(capsys.readouterr().out)[0]


def test_setup_interactive_logs_in_and_can_skip_the_skill(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    answers = iter(["http://lf.test", "pk-lf-1", "n"])  # host, public key, install the skill?
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-lf-1")
    route_doctor(fake_api)

    code = main(["setup"])

    cfg = ConfigManager()
    assert code == 0  # declining the skill is not a failure
    assert cfg.list_profiles()["default"].host == "http://lf.test"
    assert cfg.get_current_profile_name() == "default"
    assert npx.calls == []
    assert LATER in capsys.readouterr().out


def test_setup_relogin_updates_the_failing_profile(fake_api, monkeypatch, npx, no_skill_dirs):
    ConfigManager().save_profile("work", "http://lf.test", "pk-old", "sk-old")
    fake_api.route("GET", "/api/public/projects", json={"message": "Invalid credentials"}, status=401)
    route_doctor(fake_api)  # the login's check and doctor then succeed
    monkeypatch.setattr("sys.stdin", TTY())
    answers = iter(["", "pk-new", "n"])  # Enter keeps the host
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-new")

    assert main(["setup"]) == 0

    profiles = ConfigManager().list_profiles()
    assert set(profiles) == {"work"}
    assert (profiles["work"].host, profiles["work"].public_key) == ("http://lf.test", "pk-new")


def test_setup_continues_when_login_cannot_verify_the_keys(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    answers = iter(["http://lf.test", "pk-lf-1", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-lf-1")
    route_doctor(fake_api, projects_status=401)

    assert main(["setup"]) == 1
    assert npx.calls and "System Diagnostics" in capsys.readouterr().out


def test_setup_interactive_install_lets_the_user_pick_agents(fake_api, monkeypatch, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt="": asked.append(prompt) or "")  # Enter accepts the install
    route_doctor(fake_api)

    assert main(["setup", *FLAGS]) == 0

    cmd, kwargs = npx.calls[0]
    assert "-y" not in cmd  # the skills CLI may ask which agents
    assert kwargs["timeout"] is None and kwargs["stdin"] is None
    assert len(asked) == 1 and "Install the" in asked[0]  # working keys: no host or key prompt
    assert ConfigManager().list_profiles() == {}


@pytest.mark.parametrize("answer,installs", [("", True), ("y", True), ("N", False), ("no", False), (" No ", False)])
def test_setup_skill_question_answers(fake_api, monkeypatch, npx, no_skill_dirs, answer, installs):
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    route_doctor(fake_api)

    assert main(["setup", *FLAGS]) == 0
    assert bool(npx.calls) is installs


@pytest.mark.parametrize("npx_path,runner", [
    (None, Runner()),
    ("/usr/bin/npx", Runner(returncode=1)),
    ("/usr/bin/npx", Runner(exc=subprocess.TimeoutExpired("npx", 90))),
    ("/usr/bin/npx", Runner(exc=OSError(8, "Exec format error"))),
], ids=["missing", "fails", "times-out", "cannot-start"])
def test_setup_exits_1_when_the_skill_cannot_be_installed(fake_api, monkeypatch, capsys, no_prompts, no_skill_dirs,
                                                          tmp_path, npx_path, runner):
    (tmp_path / "skills" / "langfuse-agent-cli").mkdir(parents=True)  # an older copy satisfies doctor
    monkeypatch.setattr(shutil, "which", lambda name, path=None: npx_path)
    monkeypatch.setattr(subprocess, "run", runner)
    route_doctor(fake_api)

    assert main(["setup", "--yes", *FLAGS]) == 1

    _, skill, check = sections(capsys.readouterr().out)
    assert LATER in skill
    assert "All checks passed" in check
    assert "did not install the skill" in check.rstrip().splitlines()[-1]


def test_setup_ignores_an_npx_in_the_current_folder(fake_api, monkeypatch, capsys, npx, no_prompts, no_skill_dirs,
                                                    tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name, path=None: str(tmp_path / "npx.cmd"))  # tmp_path is the cwd
    route_doctor(fake_api)

    assert main(["setup", "--yes", *FLAGS]) == 1

    assert npx.calls == []
    assert "current folder" in sections(capsys.readouterr().out)[1]


def test_setup_reports_a_config_error_and_still_installs_the_skill(monkeypatch, capsys, npx, no_prompts,
                                                                   no_skill_dirs):
    monkeypatch.setenv("LANGFUSE_PROFILE", "nope")

    assert main(["setup", "--yes"]) == 1

    captured = capsys.readouterr()
    assert "profile 'nope' not found" in sections(captured.out)[0]
    assert npx.calls
    assert "profile 'nope' not found" in captured.err  # doctor reports it again


def test_doctor_hint_points_to_setup(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api)

    assert main(["doctor", *FLAGS]) == 0
    assert f"Run 'lf setup', or: npx skills@1 add {SKILL_SOURCE} -g" in capsys.readouterr().out


def test_setup_skips_the_skill_when_this_version_is_installed(fake_api, capsys, npx, no_prompts, no_skill_dirs,
                                                             tmp_path):
    install_skill()
    link_skill(tmp_path / "skills")  # the Claude Code folder no_skill_dirs points doctor at
    route_doctor(fake_api)

    assert main(["setup", "--yes", *FLAGS]) == 0

    assert npx.calls == []
    assert f"Skill v{__version__} is already installed" in sections(capsys.readouterr().out)[1]


def test_setup_replaces_an_older_skill(fake_api, npx, no_prompts, no_skill_dirs):
    install_skill("v0.2.0")
    route_doctor(fake_api)

    main(["setup", "--yes", *FLAGS])

    assert npx.calls


def test_setup_ends_with_plain_english_prompts_when_everything_works(fake_api, capsys, npx, no_prompts,
                                                                     no_skill_dirs):
    route_doctor(fake_api)

    assert main(["setup", "--yes", *FLAGS]) == 0

    check = sections(capsys.readouterr().out)[2]
    assert "Try it" in check
    assert '"Why did my LLM app fail in the last hour?"' in check


def test_setup_shows_no_prompts_when_the_check_fails(fake_api, capsys, npx, no_prompts, no_skill_dirs):
    route_doctor(fake_api, projects_status=401)

    assert main(["setup", "--yes", *FLAGS]) == 1
    assert "Try it" not in capsys.readouterr().out


def test_setup_profile_name_creates_that_profile(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    answers = iter(["", "pk-lf-1", "n"])  # Enter keeps the --host value; public key; skip the skill
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-lf-1")
    route_doctor(fake_api)

    assert main(["setup", "--profile-name", "staging", "--host", "http://lf.test"]) == 0

    cfg = ConfigManager()
    assert cfg.list_profiles()["staging"].host == "http://lf.test"
    assert cfg.get_current_profile_name() == "staging"
    assert "Source: profile (staging)" in capsys.readouterr().out


def test_setup_profile_name_checks_an_existing_profile(fake_api, capsys, npx, no_prompts, no_skill_dirs):
    cfg = ConfigManager()
    cfg.save_profile("default", "http://other.test", "pk-x", "sk-x")
    cfg.save_profile("work", "http://lf.test", "pk", "sk")
    route_doctor(fake_api)

    assert main(["setup", "--yes", "--profile-name", "work"]) == 0
    assert "✓ Using profile credentials for http://lf.test" in capsys.readouterr().out


def test_setup_profile_name_without_a_terminal_says_how_to_create_it(fake_api, capsys, npx, no_prompts,
                                                                    no_skill_dirs):
    assert main(["setup", "--yes", "--profile-name", "staging"]) == 1
    assert "lf setup --profile-name staging" in sections(capsys.readouterr().out)[0]


def test_setup_reinstalls_when_no_agent_folder_has_the_skill(fake_api, npx, no_prompts, no_skill_dirs):
    install_skill()  # the shared copy and the lock say "current", but the agent link is gone
    route_doctor(fake_api)

    main(["setup", "--yes", *FLAGS])

    assert npx.calls


def test_setup_yes_with_a_new_profile_name_does_not_claim_success(fake_api, capsys, npx, no_prompts, no_skill_dirs):
    ConfigManager().save_profile("default", "http://lf.test", "pk", "sk")
    route_doctor(fake_api)

    code = main(["setup", "--yes", "--profile-name", "staging", "--host", "http://lf.test"])

    out = capsys.readouterr().out
    assert code == 1
    assert "Try it" not in out
    assert "did not create the profile 'staging'" in out.rstrip().splitlines()[-1]
    assert "staging" not in ConfigManager().list_profiles()


def test_setup_shows_the_prompts_again_when_the_skill_is_already_current(fake_api, capsys, npx, no_prompts,
                                                                         no_skill_dirs, tmp_path):
    install_skill()
    link_skill(tmp_path / "skills")
    route_doctor(fake_api)

    assert main(["setup", "--yes", *FLAGS]) == 0
    assert "Try it" in sections(capsys.readouterr().out)[2]


def test_setup_shows_no_prompts_when_the_skill_was_declined(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    route_doctor(fake_api)

    assert main(["setup", *FLAGS]) == 0
    assert "Try it" not in capsys.readouterr().out


def test_setup_profile_name_with_rejected_keys_exits_1_without_prompts(fake_api, capsys, npx, no_prompts,
                                                                       no_skill_dirs):
    ConfigManager().save_profile("work", "http://lf.test", "pk-old", "sk-old")
    route_doctor(fake_api, projects_status=401)

    assert main(["setup", "--yes", "--profile-name", "work"]) == 1
    assert "Try it" not in capsys.readouterr().out


def test_setup_treats_end_of_input_at_the_skill_question_as_no(fake_api, monkeypatch, capsys, npx, no_skill_dirs):
    monkeypatch.setattr("sys.stdin", TTY())

    def eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    route_doctor(fake_api)

    assert main(["setup", *FLAGS]) == 0
    assert npx.calls == []
    assert LATER in capsys.readouterr().out
