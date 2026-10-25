import pytest
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
