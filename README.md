# langfuse-agent-cli (`lf`)

Command-line access to [Langfuse](https://langfuse.com) traces, prompts, datasets and scores, shaped
for AI coding agents: compact JSON by default, failing traces with their error messages in one
command, a trace as a tree, and an agent skill that teaches the commands.

> **Status: prototype.** Langfuse ships an official CLI,
> [`@langfuse/cli`](https://github.com/langfuse/langfuse-cli), which covers the whole API, and official
> agent skills, [`langfuse/skills`](https://github.com/langfuse/skills). This project tries out
> agent-oriented features on the same API. [RFC.md](./RFC.md) describes which of them it proposes
> upstream.

## Requirements

- Python 3.10 or newer
- Langfuse v4, self-hosted or Cloud. The trace commands read `/api/public/v2/observations`;
  `lf doctor` reports if a server does not have it.

## Install

```bash
pipx install git+https://github.com/tns15june/langfuse-agent-cli
# or
uv tool install git+https://github.com/tns15june/langfuse-agent-cli
```

The agent skill (`langfuse-agent-cli`) installs with the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add tns15june/langfuse-agent-cli
```

## Credentials

`lf` takes the host and both keys from one source; the first match wins:

1. `--env-file <path>`
2. `--profile <name>` or `LANGFUSE_PROFILE`
3. `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`, with the host from `LANGFUSE_BASE_URL`, then
   `LANGFUSE_HOST` (default `https://cloud.langfuse.com`)
4. The saved current profile

`--host`, `--public-key` and `--secret-key` override single values; prefer environment variables or a
profile over passing keys on the command line, where they end up in shell history. `lf` reads a
`.env` file only when it is passed with `--env-file`.

To save a profile (the keys are prompted for, and the secret is not echoed):

```bash
lf auth login --profile-name local --host http://localhost:3000 --default
lf doctor
```

Profiles live in `~/.config/langfuse/profiles.json`, readable only by you (mode 0600).

## Commands

Output is JSON by default; `-o text` prints short lines instead. `--compact` drops null and empty
fields, and `--agent-fields name,level` keeps only the listed fields of each row.

```bash
# Failing traces, one entry per trace, with each error message
lf trace list --status error --limit 10 --compact

# One trace as a tree; add --io for short inputs and outputs
lf trace get <trace-id> --timeline

# All traces of a session, oldest first
lf trace session <session-id> --compact

# Recent traces, filtered
lf trace list --user-id user-42 --from-ts 2026-10-24T00:00:00Z --limit 20

# Prompts
lf prompt list -o text
lf prompt get support/greeter
lf prompt get welcome-bot --vars '{"user_name": "Alice", "plan": "pro"}' -o text
lf prompt push welcome-bot --text 'Hello {{user_name}}!' --labels staging

# Datasets and scores
lf dataset list
lf dataset get intent-classification-evals
lf score create --trace-id <trace-id> --name accuracy --value 1

# Discover commands and options
lf help-map
lf help "trace get"
```

A timeline, from synthetic data:

```text
Trace 487b674e9a38e8d85cd683d2f022bf1d: 3 observations, 1 error
✓ AGENT support-agent-turn [1ms]
  ✓ GENERATION plan-step [0ms] (model: gpt-4o-mini)
  ✗ [ERROR] TOOL search_tool_call [0ms]
      Message: 503 Service Unavailable
```

Exit codes: `0` success, `1` API or configuration error (the message is on stderr), `2` invalid command.

## API endpoints used

| Command | Endpoint |
| --- | --- |
| `trace list` | `GET /api/public/v2/observations?isRootObservation=true` |
| `trace list --status error` | `GET /api/public/v2/observations?level=ERROR`, grouped by trace |
| `trace get` | `GET /api/public/v2/observations?traceId=…`, all pages |
| `trace session` | `GET /api/public/v2/observations?sessionId=…&isRootObservation=true` |
| `prompt list`, `prompt get`, `prompt push` | `/api/public/v2/prompts` |
| `dataset list`, `dataset get` | `/api/public/v2/datasets`, `/api/public/dataset-items` |
| `score create` | `POST /api/public/scores` |
| `doctor`, `auth status` | `/api/public/health`, `/api/public/projects` |

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

The unit tests replay responses recorded from Langfuse 4.70.0 (synthetic data). The live tests run
every command against a real instance, for example one started from Langfuse's official
`docker-compose.yml`:

```bash
export LANGFUSE_BASE_URL=http://localhost:3000 LANGFUSE_PUBLIC_KEY=pk-lf-... LANGFUSE_SECRET_KEY=sk-lf-...
pip install langfuse
python scripts/seed_langfuse.py   # synthetic prompts, a dataset and traces: use a throwaway project
LF_LIVE=1 pytest tests/test_live.py -v
```

CI runs the unit tests on Python 3.10 to 3.13 and the live tests against the latest Langfuse release,
on every push and weekly.

## Prior art

The command map (`lf help-map`) and the `--agent-fields` option follow Atlassian's
[Teamwork Graph CLI](https://developer.atlassian.com/platform/teamwork-graph/twg-cli/getting-started/installation/).

## License

MIT
