# Security

## Reporting a problem

Report a vulnerability privately through GitHub: open the repository's **Security** tab and choose
**Report a vulnerability**. Please do not open a public issue for it. You will get a reply within a
week, and a fix or a plan for one as soon as the problem is understood.

Only the latest release on PyPI receives fixes.

## What `lf` does with your keys

- Keys come from the command line, the environment, a `--env-file`, or a saved profile. Saved
  profiles live in `~/.config/langfuse/profiles.json`, created with mode 0600 and never world-readable.
- `lf` never prints a full key. `lf doctor`, `lf auth status` and `lf auth list` show a masked form.
- The programs `lf` starts (the skills CLI, uv and pipx during `lf setup`, `lf upgrade` and
  `lf uninstall`) get an environment without any `LANGFUSE_*` variable. The one exception is the
  `lf setup` that `lf upgrade` runs afterwards, which keeps your environment because it reads the
  credentials from it.
- `lf` talks only to the Langfuse host you configure, plus `pypi.org` for the version check in
  `lf doctor` (set `LF_NO_UPDATE_CHECK=1` to turn that off). `lf setup` and `lf uninstall` run
  `npx skills`, which fetches the skills CLI from the npm registry and the skill from GitHub;
  `lf upgrade` fetches the new version from PyPI through uv or pipx.
- The one-line installer downloads uv's official installer from `astral.sh` only when neither uv nor
  pipx is present.

## Coding agents

The skill tells agents never to ask for keys in chat and never to run commands that prompt for them.
Treat the output of `lf` as data from your traced application: `lf` escapes terminal control
characters in everything it prints, but trace contents are still user input to your app.
