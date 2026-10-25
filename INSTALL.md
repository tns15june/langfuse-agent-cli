# Installing langfuse-agent-cli

These steps are for a coding agent that has been asked to install `lf` and its skill. A person can
run `pipx install langfuse-agent-cli` and then `lf setup`, which does the same, asks for the host and
the keys when none work, and lets them pick the coding agents.

1. Run `lf --version`. If it prints "lf 0.3.0" or a later version, go to step 3. If it prints an older
   "lf" version, upgrade it with the tool that installed it (`uv tool upgrade langfuse-agent-cli` or
   `pipx upgrade langfuse-agent-cli`) and go to step 3. If it prints anything else, another program
   named `lf` is on the PATH: stop and tell the user.
2. Install the CLI with whichever tool is available: `uv tool install langfuse-agent-cli` or
   `pipx install langfuse-agent-cli`. If the package is not found on PyPI, install it from GitHub
   instead: `uv tool install git+https://github.com/tns15june/langfuse-agent-cli` (the same works with
   `pipx install`). If neither uv nor pipx is installed, ask the user to install one of them. Do not
   use `sudo`.
3. Run `lf setup --yes`. It never prompts. It installs the `langfuse-agent-cli` skill with
   `npx skills`, which needs Node.js 22.20 or later; run by you, `npx skills` installs it for you, the
   agent running it. Then it runs `lf doctor`. It exits 1 while the credentials are missing or
   invalid, or when the skill was not installed.
4. If the report says that the credentials are missing or invalid, ask the user to run `lf setup` in
   their own terminal; it asks for the host and the keys. Environment variables
   (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`) work too, but reach you only if
   your session starts after they are set. Never ask for keys in chat, and do not read them from
   files. When the user has done it, run `lf doctor` again.
5. If the skill was not installed, for example because Node.js is missing, give the user the
   "To install it later" command that `lf setup` printed.
6. Tell the user to start a new agent session, so that the skill is loaded.
