from pathlib import Path

import pytest
import requests
from helpers import load_fixture

from langfuse_cli.cli import main
from langfuse_cli.config import ConfigManager


def test_auth_login_prompts_without_crashing(fake_api, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "pk-lf-test")
    monkeypatch.setattr("getpass.getpass", lambda _: "sk-lf-test")
    fake_api.route("GET", "/api/public/projects", json=load_fixture("projects"))

    assert main(["auth", "login", "--profile-name", "local", "--host", "http://lf.test", "--default"]) == 0
    assert ConfigManager().list_profiles()["local"].secret_key == "sk-lf-test"
    assert fake_api.calls[-1][1] == "/api/public/projects"


@pytest.mark.parametrize("family", ["auth", "prompt", "trace", "dataset", "score"])
def test_family_without_subcommand_exits_2(family):
    with pytest.raises(SystemExit) as exc:
        main([family])
    assert exc.value.code == 2


def test_api_error_html_body_is_not_printed(fake_api, capsys):
    fake_api.route("GET", "/api/public/v2/prompts/missing", status=404,
                   text="<!DOCTYPE html><html><body>404</body></html>", content_type="text/html")

    flags = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
    assert main(["prompt", "get", "missing", *flags]) == 1
    err = capsys.readouterr().err
    assert "HTTP 404" in err
    assert "<html" not in err


FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]


def test_write_is_not_replayed_after_a_redirect(fake_api, capsys):
    # requests would turn a redirected POST into a GET: the write is lost while the command reports success.
    fake_api.route("POST", "/api/public/v2/prompts", status=301, text="", content_type="text/plain",
                   headers={"Location": "https://lf.test/api/public/v2/prompts"})

    assert main(["prompt", "push", "p", "--text", "hi", *FLAGS]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "redirected to https://lf.test/api/public/v2/prompts" in captured.err
    assert len(fake_api.calls) == 1


@pytest.mark.parametrize("argv", [["trace", "list"], ["trace", "get", "abc"]])
def test_non_json_success_body_is_an_error(fake_api, capsys, argv):
    # A login page or a wrong host answering 200 with HTML is not an empty result.
    fake_api.route("GET", "/api/public/v2/observations", text="<html>Sign in</html>", content_type="text/html")

    assert main([*argv, *FLAGS]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error: ") and "not JSON" in captured.err


@pytest.mark.parametrize("exc", [requests.exceptions.ConnectionError("refused"),
                                 requests.exceptions.ReadTimeout("slow"),
                                 requests.exceptions.ChunkedEncodingError("cut")])
def test_transport_errors_are_one_line(monkeypatch, capsys, exc):
    def fail(*args, **kwargs):
        raise exc
    monkeypatch.setattr(requests.Session, "request", fail)

    assert main(["trace", "list", *FLAGS]) == 1
    err = capsys.readouterr().err
    assert err.startswith("Error: ") and len(err.splitlines()) == 1


def test_host_without_scheme_is_a_clean_error(capsys):
    # requests rejects "localhost:3000/..." before opening a connection.
    assert main(["trace", "list", "--host", "localhost:3000", "--public-key", "pk", "--secret-key", "sk"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("Error: ") and "localhost:3000" in err


def test_prompt_push_missing_file_is_a_clean_error(fake_api, capsys):
    assert main(["prompt", "push", "p", "--file", "missing.txt", *FLAGS]) == 1
    captured = capsys.readouterr()
    assert (captured.out, fake_api.calls) == ("", [])
    assert captured.err.startswith("Error: ") and "missing.txt" in captured.err


def test_auth_switch_unknown_profile_reports_on_stderr(capsys):
    assert main(["auth", "switch", "nope"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "nope" in captured.err


@pytest.fixture
def two_profiles(fake_api):
    cfg = ConfigManager()  # the isolated profiles file from conftest
    cfg.save_profile("default", "http://default.test", "pk-lf-default-1111", "sk-lf-default-1111", set_default=True)
    cfg.save_profile("prod", "http://prod.test", "pk-lf-prod-2222", "sk-lf-prod-2222")
    Path("creds.env").write_text(  # the cwd is tmp_path (conftest)
        "LANGFUSE_PUBLIC_KEY=pk-lf-file-3333\nLANGFUSE_SECRET_KEY=sk-lf-file-3333\nLANGFUSE_HOST=http://file.test\n")
    fake_api.route("GET", "/api/public/projects", json=load_fixture("projects"))


@pytest.mark.parametrize("argv,env,host,key_end", [
    (["auth", "status"], {}, "http://default.test", "1111"),  # the saved current profile
    (["auth", "status", "--profile", "prod"], {}, "http://prod.test", "2222"),
    (["--profile", "prod", "auth", "status"], {}, "http://prod.test", "2222"),  # option before the subcommand
    (["auth", "status"], {"LANGFUSE_PROFILE": "prod"}, "http://prod.test", "2222"),
    (["auth", "status", "--profile", "prod", "--env-file", "creds.env"], {}, "http://file.test", "3333"),
])
def test_credential_source_reaches_the_command(two_profiles, monkeypatch, capsys, argv, env, host, key_end):
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    assert main(argv) == 0
    lines = capsys.readouterr().out.splitlines()
    assert f"Host: {host}" in lines
    assert f"Public Key: pk-lf-...{key_end}" in lines  # host and keys come from the same source


def test_unknown_profile_is_a_one_line_error(capsys):
    assert main(["trace", "list", "--profile", "nope"]) == 1
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "Error: profile 'nope' not found; see 'lf auth list'\n")
