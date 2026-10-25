# Contributing

Thank you for helping. Bug reports and ideas go to
[GitHub issues](https://github.com/tns15june/langfuse-agent-cli/issues); small pull requests are welcome.

## Set up

```bash
git clone https://github.com/tns15june/langfuse-agent-cli
cd langfuse-agent-cli
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Check your change

```bash
ruff check .
pytest -q
```

The unit tests replay responses recorded from Langfuse 4.70.0 (synthetic data) and never touch the
network, your profiles file or your home folder. `tests/test_docs.py` parses every `lf ...` command in
the README, INSTALL.md and the skill, so a documented command that does not parse fails the suite.

To run the live tests against a real Langfuse (a throwaway project; the seed script writes to it):

```bash
export LANGFUSE_BASE_URL=http://localhost:3000 LANGFUSE_PUBLIC_KEY=pk-lf-... LANGFUSE_SECRET_KEY=sk-lf-...
pip install langfuse
python scripts/seed_langfuse.py
LF_LIVE=1 pytest tests/test_live.py -v
```

## How changes are made here

- Write the test first and watch it fail, then make it pass. A behaviour change without a test is not
  finished.
- Keep output safe for agents: data commands print exactly one JSON document on stdout, errors go to
  stderr, and nothing ever prints a key.
- The skill (`skills/langfuse-agent-cli/`) documents the commands; when a command or option changes,
  change the skill, `README.md` and the help catalog in `langfuse_cli/commands/help_map.py` in the same
  pull request. `tests/test_help.py` fails when the catalog and the parser disagree.
- `INSTALL.md` and `docs/AGENTS.md` must stay identical; a test checks it.

## Releasing (maintainers)

Bump `__version__` in `langfuse_cli/__init__.py`, commit, then push the commit and its tag together:

```bash
git tag v0.5.0 && git push --atomic origin main v0.5.0
```

The Publish workflow tests, builds and uploads to PyPI through trusted publishing. `lf setup` installs
the skill from the tag that matches the installed version, so `main` must never carry a version
without its tag.
