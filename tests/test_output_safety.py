"""Server data (trace names, error messages, prompts) can contain terminal escape sequences."""
import json

import pytest
from helpers import load_fixture

from langfuse_cli.cli import main
from langfuse_cli.formatters import clean

FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]


def test_clean_escapes_terminal_controls_but_keeps_newline_and_tab():
    assert clean("ok\x1b[2J\x07\r\nnext\t\x9b") == "ok\\u001b[2J\\u0007\\u000d\nnext\t\\u009b"


def test_text_output_escapes_control_characters(fake_api, capsys):
    prompts = load_fixture("prompts_list")
    prompts["data"][0]["name"] = "evil\x1b]0;pwned\x07"
    fake_api.route("GET", "/api/public/v2/prompts", json=prompts)

    assert main(["prompt", "list", "-o", "text", *FLAGS]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out and "\x07" not in out
    assert "evil\\u001b]0;pwned\\u0007" in out


def test_error_messages_escape_control_characters(fake_api, capsys):
    fake_api.route("GET", "/api/public/v2/prompts/p", status=400, json={"message": "bad\x1b[2Jinput"})

    assert main(["prompt", "get", "p", *FLAGS]) == 1
    err = capsys.readouterr().err
    assert "\x1b" not in err
    assert "bad\\u001b[2Jinput" in err


@pytest.mark.parametrize("char", ["\x1b", "\x7f", "\x85", "\x9b"])
def test_json_output_stays_one_valid_document(fake_api, capsys, char):
    # DEL and C1 pass through json.dumps(ensure_ascii=False) raw, so the escaping must keep JSON valid.
    prompts = load_fixture("prompts_list")
    prompts["data"][0]["name"] = f"evil{char}name"
    fake_api.route("GET", "/api/public/v2/prompts", json=prompts)

    assert main(["prompt", "list", *FLAGS]) == 0
    out = capsys.readouterr().out
    assert char not in out
    assert json.loads(out)[0]["name"] == f"evil{char}name"
