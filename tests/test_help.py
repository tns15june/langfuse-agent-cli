import argparse
import json

from langfuse_cli.cli import create_parser, main
from langfuse_cli.commands.help_map import COMMAND_CATALOG


def leaf_commands(parser: argparse.ArgumentParser, prefix: str = "") -> dict:
    """'trace get' -> its option strings, for every command that takes no further subcommand."""
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subparsers:
        return {prefix.strip(): {s for a in parser._actions for s in a.option_strings}}
    leaves = {}
    for name, sub in subparsers[0].choices.items():
        leaves.update(leaf_commands(sub, f"{prefix} {name}"))
    return leaves


def test_catalog_matches_parser():
    leaves = leaf_commands(create_parser())

    assert set(COMMAND_CATALOG) == set(leaves)
    for cmd, info in COMMAND_CATALOG.items():
        for opt in (o.split()[0] for o in info["opts"] if o.startswith("--")):
            assert opt in leaves[cmd], (cmd, opt)


def test_help_describe_alias_matches_plain_help(capsys):
    assert main(["help", "trace", "get"]) == 0
    plain = capsys.readouterr().out

    assert main(["help", "describe", "trace get"]) == 0
    assert capsys.readouterr().out == plain
    assert json.loads(plain)["cmd"] == "lf trace get"


def test_help_requires_an_exact_command(capsys):
    assert main(["help", "get"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "prompt get" in captured.err and "trace get" in captured.err
