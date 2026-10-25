# langfuse-agent-cli (`lf`)

Command-line access to [Langfuse](https://langfuse.com) traces, prompts, datasets and scores, shaped
for AI coding agents: JSON by default (`--compact` trims it), failing traces with their error messages
in one command, a trace as a tree, and an agent skill that teaches the commands.

> **Status: prototype.** Langfuse ships an official CLI,
> [`@langfuse/cli`](https://github.com/langfuse/langfuse-cli), which covers the whole API, and official
> agent skills, [`langfuse/skills`](https://github.com/langfuse/skills). This project tries out
> agent-oriented features on the same API.
> [RFC.md](https://github.com/tns15june/langfuse-agent-cli/blob/main/RFC.md) describes which of them it
> proposes upstream.

## Requirements

- Python 3.10 or newer
- Langfuse v4, self-hosted or Cloud. The trace commands read `/api/public/v2/observations`;
  `lf doctor` reports if a server does not have it.
- Node.js 22.20 or newer, only for installing the agent skill

## Install

```bash
pipx install langfuse-agent-cli   # or: uv tool install langfuse-agent-cli
lf setup
```

`lf setup` takes three steps and is safe to run again:

1. **Credentials.** It keeps working credentials that it finds. When no profile is saved, or the
   saved profile's keys are rejected, it asks for the host and the keys (the secret is not echoed)
   and saves them. It never replaces saved keys when the server is merely unreachable, and keys from
   `LANGFUSE_*` variables, `--env-file` or key flags, which take precedence over profiles, are left for
   you to fix.
2. **Agent skill.** It installs the `langfuse-agent-cli` skill with the
   [skills CLI](https://github.com/vercel-labs/skills), which asks which coding agents to install it
   for when it finds more than one. The skill comes from the release tag that matches your `lf`
   version.
3. **Check.** It runs `lf doctor`.

To have a coding agent install it, give the agent this prompt:

```text
Install langfuse-agent-cli by following https://raw.githubusercontent.com/tns15june/langfuse-agent-cli/main/INSTALL.md
```

The agent installs the CLI and runs `lf setup --yes`, which never prompts and installs the skill for
that agent. If no working credentials are configured, the agent asks you to run `lf setup` yourself,
which asks for the host and the keys.

To install the latest code from GitHub instead of PyPI:
`pipx install git+https://github.com/tns15june/langfuse-agent-cli`.

### Upgrade and uninstall

```bash
pipx upgrade langfuse-agent-cli && lf setup   # lf setup also installs the matching skill
npx skills remove --global langfuse-agent-cli
pipx uninstall langfuse-agent-cli
```

With uv, use `uv tool upgrade langfuse-agent-cli` and `uv tool uninstall langfuse-agent-cli`. Saved
profiles stay in `~/.config/langfuse/profiles.json` until you delete that file.

## Credentials

`lf` takes the host and both keys from one source; the first match wins:

1. `--env-file <path>`
2. `--profile <name>` or `LANGFUSE_PROFILE`
3. `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` (either one selects this source), with the host from
   `LANGFUSE_BASE_URL`, then `LANGFUSE_HOST` (default `https://cloud.langfuse.com`)
4. The saved current profile

`--host`, `--public-key` and `--secret-key` override single values; prefer environment variables or a
profile over passing keys on the command line, where they end up in shell history. `lf` reads a
`.env` file only when it is passed with `--env-file`.

To save another profile (the keys are prompted for, and the secret is not echoed):

```bash
lf auth login --profile-name local --host http://localhost:3000 --default
lf doctor
```

Profiles live in `~/.config/langfuse/profiles.json`, readable only by you (mode 0600).

## Commands

Data commands print JSON by default and short lines with `-o text`; `doctor`, `setup`, `auth` and
`help-map` print text. Three options keep JSON small:

- `--compact` drops null and empty fields.
- `--agent-fields name,level` keeps only the listed fields of each row.
- `--output-summary` writes JSON output over 16 KB to a file and prints the file's path, size and keys
  instead.

```bash
# Failing traces, one entry per trace, with each error message
lf trace list --status error --limit 10 --compact

# One trace as a tree; add --io for short inputs and outputs
lf trace get <trace-id> --timeline

# A trace with its inputs and outputs; over 16 KB it goes to a file
lf trace get <trace-id> --io --output-summary

# The traces of a session, oldest first (the newest 1000)
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
Trace 33579e8e8ec602e878f0744ad53ac1fe: 3 observations, 1 error
✓ AGENT support-agent-turn
  ✓ GENERATION plan-step (model: gpt-4o-mini)
  ✗ [ERROR] TOOL search_tool_call
      Message: 503 Service Unavailable
```

Observations with a measured duration show it in brackets, such as `[1.24s]`. Langfuse 4.70 reports
no duration for observations of zero length, like these synthetic ones.

Exit codes: `0` success, `1` API or configuration error, `2` invalid command. The reason for a failure is
on stderr, except that `doctor`, `setup --yes` and `auth status` print their whole report, failures
included, on stdout. `setup` also exits `1` when the skill was not installed.

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
| `doctor` | `/api/public/health`, `/api/public/projects`, `/api/public/v2/observations?limit=1` |
| `auth login`, `auth status` | `/api/public/projects` |
| `setup` | `/api/public/projects`, then the `doctor` requests |

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

### Releasing

The Publish workflow uploads to PyPI with trusted publishing, so no token is stored; the PyPI project
lists `publish.yml` and the GitHub environment `pypi` as its trusted publisher. Bump `__version__` in
`langfuse_cli/__init__.py`, commit, then push that commit and its tag together:

```bash
git tag v0.3.0 && git push --atomic origin main v0.3.0
```

The workflow checks that the tag matches the version, runs the tests, builds and checks the
distributions, installs the wheel, and uploads the wheel and the source archive. `main` should never
carry a version without its tag, because `lf setup` and `lf doctor` point at the skill under that tag.

## Prior art

The command map (`lf help-map`), the `--output-summary` option, `lf setup` and the agent install prompt
follow Atlassian's
[Teamwork Graph CLI](https://developer.atlassian.com/platform/teamwork-graph/twg-cli/getting-started/installation/),
whose `--select` option does what `lf`'s `--agent-fields` does.

## License

MIT
