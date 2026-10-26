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
shellcheck docs/install.sh   # CI runs this too; needed when you change the installer
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

- Every change lands through a pull request; `main` rejects direct pushes.
- Write the test first and watch it fail, then make it pass. A behaviour change without a test is not
  finished.
- Keep output safe for agents: data commands print exactly one JSON document on stdout, errors go to
  stderr, and nothing ever prints a key.
- The skill (`skills/langfuse-agent-cli/`) documents the commands; when a command or option changes,
  change the skill, `README.md` and the help catalog in `langfuse_cli/commands/help_map.py` in the same
  pull request. `tests/test_help.py` fails when the catalog and the parser disagree.
- `INSTALL.md` and `docs/AGENTS.md` must stay identical; a test checks it.

## Releasing (maintainers)

Bump `__version__` in `langfuse_cli/__init__.py` in a pull request and merge it. Then tag the merge
commit, push the tag, and publish the release notes on GitHub:

```bash
git fetch origin && git tag v0.5.0 origin/main && git push origin v0.5.0
gh release create v0.5.0 --title "lf 0.5.0" --notes-file release-notes.md
```

The Publish workflow tests, builds and uploads to PyPI through trusted publishing. `lf setup` installs
the skill from the tag that matches the installed version, so tag as soon as the version bump is merged.
