# Querying traces

On Langfuse v4 a trace is the set of observations that share a `traceId`. `lf` reads them from
`GET /api/public/v2/observations`, the only trace read path on Langfuse v4 (and on Langfuse
Cloud after 2026-11-16).

| Command | What `lf` asks the API for |
| --- | --- |
| `lf trace list` | Root observations (`isRootObservation=true`): one row per trace, newest first |
| `lf trace list --status error` | Observations with `level=ERROR`, grouped by trace |
| `lf trace get <trace-id>` | Every observation of the trace, across all pages |
| `lf trace session <session-id>` | Root observations with that `sessionId`, oldest first |

## Filters

```bash
lf trace list --session-id <session-id> --compact
lf trace list --user-id user-42 --limit 5
lf trace list --from-ts 2026-10-24T18:00:00Z --to-ts 2026-10-24T20:00:00Z
lf trace list --status error --from-ts 2026-10-24T00:00:00Z --limit 20 --compact
```

Timestamps are ISO 8601 and filter on the observation start time. `--limit` counts traces,
also with `--status error`.

## Triage

1. `lf trace list --status error --limit 10 --compact` lists failing traces, each with the
   names and messages of its failed observations.
2. `lf trace get <trace-id> --timeline` shows where in the run the error happened.
3. `lf trace get <trace-id> --timeline --io` adds short inputs and outputs when you need them.
4. `lf trace session <session-id> --compact` shows the turns around it, when the error depends
   on earlier turns.

## Servers without the v2 observations API

If `lf doctor` reports that `/api/public/v2/observations` is missing, the server predates
Langfuse v4; the trace commands need an upgraded server. Prompt, dataset and score commands
still work.
