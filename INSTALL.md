# Install langfuse-agent-cli: instructions for coding agents

Use these steps when a user asks you to install, set up, repair, upgrade or remove `lf`, the
langfuse-agent-cli command, and its agent skill.

## Rules

- **`lf setup` is the setup command.** It is safe to run again: it keeps working credentials and skips
  a skill that is already installed for this version.
- **Never ask for, repeat, log or summarize a Langfuse key, and never pass one as a command-line
  flag.** The user types keys into lf's own hidden prompt in their terminal, or sets them as
  environment variables themselves.
- **Run `lf setup --yes`.** Your shell usually has no terminal, so lf could not show its prompts to the
  user. With `--yes` it never prompts: it installs the skill, checks the connection, and says when the
  user needs to log in.
- **Ask before anything that removes, replaces or upgrades.** `lf uninstall`, replacing saved keys and
  `lf upgrade` change the user's machine; do them only after the user agrees.

## Find lf before installing

1. Run `lf --version`.
2. If the shell says `lf` is not found, try `~/.local/bin/lf --version`; uv and pipx put `lf` there. If
   that works, use that path for every command below, and tell the user to add `~/.local/bin` to their
   PATH (`uv tool update-shell` or `pipx ensurepath`).
3. If it prints "lf 0.4.0" or a later version, go to "Run setup". If it prints an older version, ask the
   user, then upgrade it with the tool that installed it, `uv tool upgrade langfuse-agent-cli` or
   `pipx upgrade langfuse-agent-cli` (versions before 0.4.0 have no `lf upgrade`), and go to "Run setup".
   If it prints anything else, another program named `lf` is installed: stop and tell the user.

## Install

Only when neither `lf` nor `~/.local/bin/lf` works:

```bash
curl -fsSL https://tns15june.github.io/langfuse-agent-cli/install.sh | sh -s -- --yes
```

The installer uses uv or pipx, installs uv into the user's home folder when neither exists, installs
`lf`, and runs `lf setup --yes`. To use a package manager directly instead, run
`uv tool install langfuse-agent-cli` or `pipx install langfuse-agent-cli`, then go to "Run setup". Do
not use `sudo`.

## Run setup

```bash
lf setup --yes
```

It checks the credentials it finds, installs the skill with `npx skills` (Node.js 22.20 or later), and
runs `lf doctor`. It exits 1 while the credentials are missing or rejected, or when the skill could not
be installed.

If the credentials are missing or rejected, ask the user to run `lf setup` in their own terminal; it
asks for the Langfuse host and keys. Environment variables (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_BASE_URL`) also work, but reach you only if your session starts after they are set. For a
second Langfuse instance, the user runs `lf setup --profile-name <name> --host <url>`; the new profile
becomes the current one, and `lf auth switch <name>` changes it later.

## Verify

Run `lf doctor` and report to the user:

- where lf is installed, its version, and whether a newer version is available;
- whether the skill is installed, and where;
- the Langfuse host and project name;
- the result: all checks passed, or what to fix.

Never include key values, not even the masked ones doctor prints.

## Repair, upgrade, remove

- **Repair:** run `lf setup --yes` again. If the credentials are the problem, ask the user to run
  `lf setup` in their own terminal.
- **Upgrade:** after the user agrees, run `lf upgrade --yes`. It upgrades lf with the tool that
  installed it, then installs the matching skill.
- **Remove:** run `lf uninstall --dry-run`, show the user the list, and only after they agree run
  `lf uninstall --yes`.

## Then

Tell the user to start a new session of their coding agent so the skill loads, and suggest a first
question, such as "Why did my LLM app fail in the last hour?". More questions to try:
https://github.com/tns15june/langfuse-agent-cli/blob/main/skills/langfuse-agent-cli/references/EXAMPLES.md
