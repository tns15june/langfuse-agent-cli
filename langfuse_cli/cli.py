"""Main CLI entrypoint for Langfuse Agent CLI."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from langfuse_cli import __version__
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.commands.auth import handle_auth
from langfuse_cli.commands.dataset import handle_dataset
from langfuse_cli.commands.doctor import handle_doctor
from langfuse_cli.commands.help_map import handle_help_describe, handle_help_map
from langfuse_cli.commands.prompt import handle_prompt
from langfuse_cli.commands.score import handle_score
from langfuse_cli.commands.trace import handle_trace
from langfuse_cli.config import ConfigError
from langfuse_cli.formatters import clean

# Common options use argparse.SUPPRESS so a subcommand's default never overwrites a value given
# before the subcommand; these defaults are applied once after parsing instead.
COMMON_DEFAULTS = {
    "profile": None,
    "host": None,
    "public_key": None,
    "secret_key": None,
    "env_file": None,
    "output": "json",
    "compact": False,
    "agent_fields": None,
}


class _SafeStream:
    """Wraps stdout/stderr so nothing a command prints, server data included, can drive the terminal."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, text: str) -> int:
        return self._stream.write(clean(text))

    def __getattr__(self, name):
        return getattr(self._stream, name)


def create_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common = common_parser.add_argument
    unset = argparse.SUPPRESS  # defaults come from COMMON_DEFAULTS
    common("-p", "--profile", default=unset, help="Saved profile to use (see 'lf auth list')")
    common("--host", default=unset, help="Langfuse host, e.g. http://localhost:3000")
    common("--public-key", default=unset, help="Langfuse public key (pk-lf-...)")
    common("--secret-key", default=unset, help="Langfuse secret key (sk-lf-...); prefer env vars or a profile")
    common("--env-file", default=unset, help="Read LANGFUSE_* credentials from this .env file")
    common("-o", "--output", choices=["json", "text"], default=unset, help="Output format (default: json)")
    common("--compact", action="store_true", default=unset, help="Drop null and empty fields from JSON output")
    common("--agent-fields", default=unset, help="Comma-separated field paths to keep in JSON output")

    parser = argparse.ArgumentParser(
        prog="lf",
        description="Agent-oriented CLI for Langfuse traces, prompts, datasets and scores.",
        parents=[common_parser],
    )
    parser.add_argument("-v", "--version", action="version", version=f"lf {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available command families")

    # 1. Auth command
    p_auth = subparsers.add_parser("auth", parents=[common_parser], help="Manage authentication profiles")
    auth_sub = p_auth.add_subparsers(dest="auth_action", required=True)
    p_auth_login = auth_sub.add_parser("login", parents=[common_parser], help="Save a profile")
    p_auth_login.add_argument("--profile-name", help="Profile name (default: default)")
    p_auth_login.add_argument("--default", action="store_true", help="Set as default active profile")

    p_auth_switch = auth_sub.add_parser("switch", parents=[common_parser], help="Switch active profile")
    p_auth_switch.add_argument("target_profile", help="Profile name to activate")

    auth_sub.add_parser("list", parents=[common_parser], help="List configured profiles")
    auth_sub.add_parser("status", parents=[common_parser], help="Check current profile status and connectivity")

    # 2. Doctor command
    subparsers.add_parser("doctor", parents=[common_parser], help="Check credentials, server and the agent skill")

    # 3. Prompt command
    p_prompt = subparsers.add_parser("prompt", parents=[common_parser], help="Inspect and manage prompt versions")
    prompt_sub = p_prompt.add_subparsers(dest="prompt_action", required=True)

    p_prompt_list = prompt_sub.add_parser("list", parents=[common_parser], help="List registered prompts")
    p_prompt_list.add_argument("--tag", help="Filter prompts by tag")
    p_prompt_list.add_argument("--limit", type=int, default=20, help="Maximum prompts to return")

    p_prompt_get = prompt_sub.add_parser("get", parents=[common_parser], help="Fetch a prompt by name")
    p_prompt_get.add_argument("name", help="Prompt name in Langfuse")
    p_prompt_get.add_argument("--version", type=int, help="Prompt version number")
    p_prompt_get.add_argument("--label", help="Prompt label (e.g. production, staging)")
    p_prompt_get.add_argument("--vars", help="JSON dictionary of variables to compile into {{mustache}} template")

    p_prompt_push = prompt_sub.add_parser("push", parents=[common_parser], help="Publish a new prompt version")
    p_prompt_push.add_argument("name", help="Prompt name")
    p_prompt_push.add_argument("--file", help="Path to file containing prompt text or chat JSON")
    p_prompt_push.add_argument("--text", help="Raw prompt string")
    p_prompt_push.add_argument("--type", choices=["text", "chat"], default="text", help="Prompt format type")
    p_prompt_push.add_argument("--labels", help="Comma-separated labels (e.g. staging,v2)")
    p_prompt_push.add_argument("--tags", help="Comma-separated tags")

    # 4. Trace command
    p_trace = subparsers.add_parser("trace", parents=[common_parser], help="Observability and trace inspection")
    trace_sub = p_trace.add_subparsers(dest="trace_action", required=True)

    p_trace_list = trace_sub.add_parser("list", parents=[common_parser], help="List recent traces")
    p_trace_list.add_argument("--session-id", help="Filter by session ID")
    p_trace_list.add_argument("--user-id", help="Filter by user ID")
    p_trace_list.add_argument("--status", choices=["all", "error"], default="all", help="Filter traces (e.g. error)")
    p_trace_list.add_argument("--limit", type=int, default=20, help="Maximum traces to return")
    p_trace_list.add_argument("--from-ts", help="Start timestamp ISO8601")
    p_trace_list.add_argument("--to-ts", help="End timestamp ISO8601")

    p_trace_get = trace_sub.add_parser("get", parents=[common_parser], help="Get trace details")
    p_trace_get.add_argument("trace_id", help="Trace ID")
    p_trace_get.add_argument("--timeline", action="store_true", help="Display visual timeline tree")
    p_trace_get.add_argument("--io", action="store_true", help="Include observation inputs and outputs (large)")

    p_trace_session = trace_sub.add_parser("session", parents=[common_parser], help="Get traces for an entire session")
    p_trace_session.add_argument("session_id", help="Session ID")

    # 5. Dataset command
    p_dataset = subparsers.add_parser("dataset", parents=[common_parser], help="Manage datasets and test suites")
    dataset_sub = p_dataset.add_subparsers(dest="dataset_action", required=True)

    dataset_sub.add_parser("list", parents=[common_parser], help="List datasets")
    p_dataset_get = dataset_sub.add_parser("get", parents=[common_parser], help="Get dataset items")
    p_dataset_get.add_argument("name", help="Dataset name")


    # 6. Score command
    p_score = subparsers.add_parser("score", parents=[common_parser], help="Record evaluation scores")
    score_sub = p_score.add_subparsers(dest="score_action", required=True)
    p_score_create = score_sub.add_parser("create", parents=[common_parser], help="Create a score on a trace")
    p_score_create.add_argument("--trace-id", required=True, help="Target trace ID")
    p_score_create.add_argument("--name", required=True, help="Metric name (e.g. accuracy, relevance)")
    p_score_create.add_argument("--value", required=True, type=float, help="Numeric value (e.g. 1.0, 0.8)")
    p_score_create.add_argument("--comment", help="Optional comment explaining score")
    p_score_create.add_argument("--observation-id", help="Optional observation ID within the trace")

    # 7. Help map and progressive disclosure
    subparsers.add_parser("help-map", parents=[common_parser], help="Machine-readable command catalog for AI agents")
    p_help = subparsers.add_parser("help", parents=[common_parser], help="Describe command details")
    p_help.add_argument("target_command", nargs="+", help="Command to describe (e.g. 'prompt get')")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0
    for key, value in COMMON_DEFAULTS.items():
        vars(args).setdefault(key, value)

    handlers = {
        "auth": handle_auth,
        "doctor": handle_doctor,
        "prompt": handle_prompt,
        "trace": handle_trace,
        "dataset": handle_dataset,
        "score": handle_score,
        "help-map": handle_help_map,
        "help": handle_help_describe,
    }
    streams = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _SafeStream(sys.stdout), _SafeStream(sys.stderr)
    try:
        return handlers[args.command](args)
    except (LangfuseAPIError, ConfigError, OSError) as e:  # OSError: --file, the profiles file
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        sys.stdout, sys.stderr = streams


if __name__ == "__main__":
    sys.exit(main())
