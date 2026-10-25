# Installing langfuse-agent-cli

These steps are for a coding agent that has been asked to install `lf` and its skill. A person can
run `pipx install langfuse-agent-cli` and then `lf setup`, which does the same and also asks for the
Langfuse keys.

1. Run `lf --version`. If it prints a version, go to step 3.
2. Install the CLI with whichever tool is available: `uv tool install langfuse-agent-cli` or
   `pipx install langfuse-agent-cli`. If the package is not found on PyPI, install it from GitHub
   instead: `uv tool install git+https://github.com/tns15june/langfuse-agent-cli` (the same works with
   `pipx install`). If neither uv nor pipx is installed, ask the user to install one of them. Do not
   use `sudo`.
3. Run `lf setup --yes`. It never prompts. It installs the `langfuse-agent-cli` skill for the coding
   agents on this machine with `npx skills`, which needs Node.js 22.20 or later, and then runs
   `lf doctor`.
4. If the report says that the credentials are missing or invalid, ask the user to run `lf auth login`
   in their own terminal, or to set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and
   `LANGFUSE_BASE_URL`. Never ask for keys in chat, and do not read them from files. When the user
   has done it, run `lf doctor` again.
5. If the skill was not installed, for example because Node.js is missing, give the user the command
   that `lf setup` printed.
6. Tell the user to start a new agent session, so that the skill is loaded.
