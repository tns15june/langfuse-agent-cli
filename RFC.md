# RFC: Agent-friendly output for `@langfuse/cli`: proposal and prototype

**Author**: Tarkeshwar Narayan (tns15june)
**Status**: Draft for discussion
**Prototype**: [tns15june/langfuse-agent-cli](https://github.com/tns15june/langfuse-agent-cli) 0.3.0

## Summary

Langfuse already has an official CLI and official agent skills. This RFC proposes three small,
separable features for `@langfuse/cli` that let coding agents control how much of a response reaches
their context, plus two rules for `langfuse/skills`. All three are prototyped in `langfuse-agent-cli`,
and proposals 1 and 2 are measured below.

## What exists today

- **`@langfuse/cli`** ([langfuse/langfuse-cli](https://github.com/langfuse/langfuse-cli)) is generated
  from the OpenAPI spec and covers every endpoint. It has schema discovery (`api schema --json`),
  `--all` pagination, API snapshots for older self-hosted servers (`--api-version`), documented exit
  codes, and conformance tests across Langfuse versions.
- **`langfuse/skills`** ships the `langfuse` skill, which uses the CLI and the documentation with
  use-case references, and installs with `npx skills add langfuse/skills` or as a plugin. An open PR
  adds hosted-skill install and push to the CLI (langfuse-cli#27).
- **The server already trims payloads**: `GET /api/public/v2/observations` returns only the field
  groups a request asks for.

What is missing for agents is control over the size of what gets printed: a list or a trace with its
inputs can run to hundreds of kilobytes, most of which the agent never reads.

## Measurements

Langfuse 4.70.0, synthetic data seeded with `scripts/seed_langfuse.py` from the prototype. Real
traffic has longer messages and more metadata, so the numbers will differ.

| Request | Size |
| --- | --- |
| One trace with 3 observations, all field groups | 12.9 KB |
| The same trace, `fields=core,basic,time,model,usage` | 2.9 KB (−78%) |
| The same trace, default `core,basic` | 1.65 KB (−87%) |
| `npx @langfuse/cli api observations list --level ERROR` (4 rows) | 3.0 KB |
| The same output, keeping 7 triage fields | 1.05 KB (−66%) |
| The same output, dropping null and empty-string fields | 2.4 KB (−21%) |
| `lf trace list --limit 100` (36 rows, from running the seed script three times) | 24.3 KB |
| The same, with `--output-summary` (the envelope) | 0.7 KB (−97%) |

## Proposals

### 1. Large-output envelope

**Problem.** One command can return more JSON than an agent can afford to read.

**Proposal.** `--output-summary auto`: when the JSON payload exceeds a threshold (for example
16 KB), write it to a file and print a short envelope instead, with the file path, byte size, row
count, the keys of the rows and, for a paged response, the next cursor. Below the threshold, print
the payload as today. See Prior art.

**Prototype.** `--output-summary` in `langfuse_cli/formatters/agent.py`, with a 16 KB threshold,
measured after field projection and pruning. The file goes to the system temp directory, readable
only by the user. The envelope has `"summary": true` and `outputFile`, so a caller can tell it from a
payload that is itself an object; on the 24.3 KB listing in the table above it is 0.7 KB. It has no
cursor: the prototype's trace commands follow cursors themselves, and its other commands return one
bounded page. The generated CLI returns one page unless given `--all`; for a `{data, meta}` page,
`rows` and `rowKeys` would describe `data`, and the envelope would carry `meta` as returned (a cursor
on the v2 observations API, page numbers on prompts and datasets).

### 2. Field projection and pruning

**Problem.** Rows carry fields an agent rarely needs for a given task (prices, flags, nulls).

**Proposal.** `--select a,b.c` keeps only the listed fields of each row, with dotted paths that reach
through lists; `--compact` drops null and empty values at every level; optional named presets per
resource, for example `--select @triage` on observations (id, traceId, name, level, statusMessage,
sessionId, startTime).

**Measured.** −66% for the 7-field triage projection and −21% for pruning alone, on the CLI's own
error output (table above).

**Prototype.** `--agent-fields` and `--compact` in `langfuse_cli/formatters/agent.py`. Both work on
any JSON response, so they need no per-endpoint code in a generated CLI.

### 3. Saved profiles and `doctor`

**Problem.** People and agents switch between local, staging and Cloud projects by juggling
environment variables or `.env` files. When a call fails, no single command says whether the keys,
the host or the server version is the cause.

**Proposal.** `langfuse auth login|switch|list|status` with named profiles stored in a file readable
only by the user, and `langfuse doctor`, which checks that the host is reachable, that the keys are
valid (`GET /api/public/projects`), that the server has the endpoints the CLI needs (for example
`/api/public/v2/observations`), and where each credential came from. Host and keys should always
come from the same source: a host from one place, such as a cloned repository's `.env`, should never
receive keys that came from another.

**Prototype.** `lf auth …` and `lf doctor`.

### For `langfuse/skills`

1. **Write safety.** Before a write (prompt create, score create, dataset item create), read the
   current state and tell the user what will change, unless they asked for the write.
2. **Setup guard.** The `langfuse` skill already tells agents not to ask for keys in chat. Extend
   that to commands that prompt for credentials: ask the user to run them.

A separate, small pull request adds field-selection and `--level ERROR` tips to
`skills/langfuse/references/cli.md`.

## Non-goals

- A second CLI. The prototype exists to test these ideas against real servers; once they land
  upstream it has done its job.
- Higher-level commands such as trace trees or error grouping in `@langfuse/cli`. They may fit the
  skill better, as recipes, unless the maintainers want them in the CLI.

## Questions for maintainers

1. Would pull requests for proposals 1–3 fit the generated design of `@langfuse/cli`, as global
   flags with no per-endpoint code?
2. What threshold and file location would suit the envelope?
3. Should credentials stay environment and `.env` only, or is there interest in profiles?

## Prior art

The command map (`help-map`), field projection and the summary envelope (`--output-summary`) come
from Atlassian's
[Teamwork Graph CLI](https://developer.atlassian.com/platform/teamwork-graph/twg-cli/getting-started/installation/).
There, projection is `--select`, and `--agent-fields` picks the fields of the summary envelope; the
prototype uses `--agent-fields` for projection. TWG's envelope is YAML and has several levels
(`none`, `stats`, `auto`, `inline`); the prototype's is JSON and has only the automatic behaviour.
