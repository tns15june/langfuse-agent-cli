---
name: langfuse-agent-cli
description: >
  Inspect Langfuse from the terminal with the `lf` CLI: failing traces and their error
  messages, one trace as an observation tree, the traces of a session, prompts with their
  variables filled in, datasets, and scores, as JSON. Use when debugging an LLM
  application's runs or prompts and `lf` is installed, or the user asks for it. For
  instrumenting code, Langfuse documentation, or API endpoints `lf` does not cover, use the
  official `langfuse` skill and `npx @langfuse/cli`.
---

# langfuse-agent-cli

`lf` reads Langfuse through its public API (Langfuse v4, self-hosted or Cloud). Data commands print
JSON by default and short text with `-o text`; `doctor`, `setup`, `auth` and `help-map` print text.

## Fast path

| Need | Command |
| --- | --- |
| Check credentials and server | `lf doctor` |
| Failing traces with their error messages | `lf trace list --status error --limit 10 --compact` |
| One trace as a tree | `lf trace get <trace-id> --timeline` |
| The same, with short inputs and outputs | `lf trace get <trace-id> --timeline --io` |
| Full inputs and outputs, over 16 KB saved to a file | `lf trace get <trace-id> --io --output-summary` |
| A few fields of each observation | `lf trace get <trace-id> --agent-fields name,type,level,statusMessage` |
| The traces of one conversation (the newest 1000) | `lf trace session <session-id> --compact` |
| A prompt with its variables filled in | `lf prompt get <name> --label production --vars '{"user_name": "Alice"}' -o text` |
| Record a score | `lf score create --trace-id <trace-id> --name accuracy --value 1` |

## Rules

1. Keep output small: add `--compact` to lists, and `--agent-fields` when you need only some
   fields. Add `--io` only when you need inputs or outputs; they are often large. When output may be
   large, add `--output-summary`: JSON over 16 KB is then written to a file, and the command prints
   `"summary": true` with the file path, its size and its keys. Read only the parts you need from the
   file, for example with `jq`.
2. When unsure about a command or flag, run `lf help-map` (`*` marks commands that write),
   then describe one command, for example `lf help "trace get"`.
3. Before a write (`prompt push`, `score create`), read the current state, for example
   `lf prompt get <name>`, and tell the user what will change, unless they asked you to run it.
4. Do not run `auth login`, or `setup` without `--yes`: they prompt for keys. Ask the user to run
   them, or to set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL`. Never ask for
   keys in chat.
5. A non-zero exit code means the command failed. The reason is on stderr, except for `lf doctor`,
   `lf setup --yes` and `lf auth status`, which print their report on stdout. Run `lf doctor` when
   the reason mentions credentials, HTTP 401, or a missing `/api/public/v2/observations`.

## Credentials

`lf` takes the host and both keys from one source; the first match wins:

1. `--env-file <path>`
2. `--profile <name>` or `LANGFUSE_PROFILE`
3. `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` (either one selects this source), with the
   host from `LANGFUSE_BASE_URL`, then `LANGFUSE_HOST`
4. The saved current profile (see `lf auth list`)

`--host`, `--public-key` and `--secret-key` override single values. `lf` reads a `.env` file
only when it is passed with `--env-file`.

## If `lf` is not installed

Tell the user how to install it: `pipx install langfuse-agent-cli` (or
`uv tool install langfuse-agent-cli`), then `lf setup`. If they ask you to install it, follow
https://raw.githubusercontent.com/tns15june/langfuse-agent-cli/main/INSTALL.md.

## References

- `references/QUERYING.md`: filters, failing traces, sessions, time windows, and how traces map
  to observations.
- `references/OUTPUT.md`: output formats, `--compact`, `--agent-fields`, `--output-summary`, the
  timeline format, and payload sizes.
