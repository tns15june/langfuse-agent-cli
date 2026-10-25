---
name: langfuse-agent-cli
description: >
  Answer plain-English questions about an LLM application's Langfuse data with the `lf` CLI: why
  runs or agent turns failed and what the errors say, which tool or step fails or is slow, what
  happened in one trace, in a conversation (session) or for one user, what the app spent on models
  and tokens, how errors or usage changed over time, which prompt version is live and how it
  renders, dataset items, and evaluation scores. Also use it to check or repair the Langfuse
  connection. For instrumenting code, Langfuse documentation, or API endpoints `lf` does not cover,
  use the official `langfuse` skill and `npx @langfuse/cli`.
---

# langfuse-agent-cli

People ask in plain English; you answer with `lf`, which reads Langfuse through its public API
(Langfuse v4, self-hosted or Cloud). Data commands print JSON; `-o text` prints a short human view.

## Words people use

- **Trace**: one run of the app, such as one agent turn. Its steps are **observations**: AGENT,
  GENERATION (a model call), TOOL, SPAN, CHAIN or EVENT. A trace is listed as its root observation.
- **Session**: the traces of one conversation (`sessionId`). **User**: the `userId` on traces.
- **Failed**: observations with level ERROR (WARNING is a warning); `statusMessage` holds the error.
- **Latency**: seconds in trace rows, milliseconds in `lf metrics`.
- **Cost and tokens**: recorded per model call; `lf metrics` adds them up.

## Fast path

| The user asks | Run |
| --- | --- |
| "What is failing?" "Why did my app fail?" | `lf trace list --status error --limit 10 --compact`, then `lf trace get <trace-id> --timeline` |
| "What happened in this trace?" | `lf trace get <trace-id> --timeline` (add `--io` for inputs and outputs) |
| "Walk me through this conversation" | `lf trace session <session-id> --compact` |
| "What did this user run into?" | `lf trace list --user-id <user-id> --status error --limit 10 --compact` |
| "What did we spend?" "Cost by model" | `lf metrics --metric totalCost,totalTokens --by providedModelName --from-ts <start>` |
| "Which step or tool is slowest?" | `lf metrics --metric latency:p95 --by name --order-by p95_latency --from-ts <start>` |
| "Which tool fails most?" | `lf metrics --where level=ERROR --by name --order-by count_count --from-ts <start>` |
| "When did the errors start?" | `lf metrics --where level=ERROR --granularity hour --from-ts <start>` |
| "How many tokens per day?" | `lf metrics --metric totalTokens --granularity day --from-ts <start>` |
| "Which prompt version is live?" | `lf prompt get <name> --label production -o text` |
| "Show the prompt with these values" | `lf prompt get <name> --label production --vars '{"user_name": "Alice"}' -o text` |
| "How are our eval scores?" | `lf metrics --view scores-numeric --metric value --by name --from-ts <start>` |
| "Is lf set up?" "Langfuse errors" | `lf doctor` |

Go straight to the command; run `lf doctor` only when a command fails. `lf metrics` counts by
default and covers the last 24 hours unless you pass `--from-ts`. Turn
"today", "this week" or "since Monday" into ISO timestamps in UTC, such as `2026-10-20T00:00:00Z`.
More worked examples: `references/EXAMPLES.md`.

## Plan first

For anything the fast path does not cover:

1. Run `lf help-map` (`*` marks commands that write), then `lf help "<command>"` for its options.
2. Pick the fewest, smallest reads that answer the question.
3. Run independent reads in one shell call, separated by `;`.

## Gathering evidence

- Start from what the user named: a trace id, session, user, tool, prompt or time. Keep names exact.
- Go from broad and small to narrow: counts from `lf metrics` or the error list first, then one
  trace's timeline, and inputs and outputs (`--io`) only for the traces you need to read.
- When output may be large, add `--output-summary`: JSON over 16 KB goes to a file and you get its
  path, size and keys. Read only the parts you need, for example with `jq`.
- Never guess ids; take them from a list. If the same error repeats, stop and report it.

## Answering

- Lead with the answer: what failed or changed, where, since when, and how often.
- Quote trace ids and exact error messages; give times in UTC and counts with their time range.
- Say what you did not check, such as inputs you did not read or a time range you left out.
- Offer the next step: a command to run, or the likely fix.

## Writes

`prompt push` and `score create` change Langfuse. Run them only when the user asks; read the
current state first (for example `lf prompt get <name>`) and tell the user what will change.

## Setup guard

- Do not run `lf auth login`, or `lf setup` without `--yes`: they ask for keys. Run `lf upgrade` and
  `lf uninstall` only after the user agrees.
- If credentials are missing, ask the user to run `lf setup` in their own terminal, or to set
  `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL`. Never ask for keys in chat.
- If `lf` is not installed and the user asks you to install it, follow
  https://tns15june.github.io/langfuse-agent-cli/AGENTS.md. Otherwise tell them: on macOS or Linux,
  `curl -fsSL https://tns15june.github.io/langfuse-agent-cli/install.sh | sh`; or
  `uv tool install langfuse-agent-cli` (or `pipx install langfuse-agent-cli`), then `lf setup`.

## Errors

- A non-zero exit code means the command failed and the reason is on stderr; `lf doctor`,
  `lf setup --yes` and `lf auth status` print their report on stdout instead.
- Run `lf doctor` when the reason mentions credentials, HTTP 401, a login page, or a missing
  `/api/public/v2/observations`.
- In a sandbox without network access, a connection error says nothing about the keys; tell the
  user what was blocked.

## Credentials

`lf` takes the host and both keys from one source; the first match wins:

1. `--env-file <path>`
2. `--profile <name>` or `LANGFUSE_PROFILE`
3. `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` (either one selects this source), with the
   host from `LANGFUSE_BASE_URL`, then `LANGFUSE_HOST`
4. The saved current profile (see `lf auth list`)

`--host`, `--public-key` and `--secret-key` override single values. `lf` reads a `.env` file
only when it is passed with `--env-file`.

## References

- `references/EXAMPLES.md`: questions people ask and the commands that answer them.
- `references/QUERYING.md`: trace filters, sessions, time windows, and metrics views and fields.
- `references/OUTPUT.md`: output formats, `--compact`, `--agent-fields`, `--output-summary`, metrics
  keys, and the timeline format.
