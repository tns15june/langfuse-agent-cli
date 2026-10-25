# Querying traces

On Langfuse v4 a trace is the set of observations that share a `traceId`. `lf` reads them from
`GET /api/public/v2/observations`, the only trace read path on Langfuse v4 (and on Langfuse
Cloud after 2026-11-16).

| Command | What `lf` asks the API for |
| --- | --- |
| `lf trace list` | Root observations (`isRootObservation=true`): one row per trace, newest first |
| `lf trace list --status error` | Observations with `level=ERROR`, grouped by trace |
| `lf trace get <trace-id>` | Every observation of the trace, across all pages |
| `lf trace session <session-id>` | Root observations with that `sessionId` (the newest 1000), oldest first |

## Filters

```bash
lf trace list --session-id <session-id> --compact
lf trace list --user-id user-42 --limit 5
lf trace list --from-ts 2026-10-24T18:00:00Z --to-ts 2026-10-24T20:00:00Z
lf trace list --status error --from-ts 2026-10-24T00:00:00Z --limit 20 --compact
```

Timestamps are ISO 8601 and filter on the observation start time. `--limit` counts traces,
also with `--status error`, which scans at most 5000 error observations. A trace's `errors` list
can miss older errors; `lf trace get <trace-id>` shows all of them.

## Triage

1. `lf trace list --status error --limit 10 --compact` lists failing traces, each with the
   names and messages of its failed observations.
2. `lf trace get <trace-id> --timeline` shows where in the run the error happened.
3. `lf trace get <trace-id> --timeline --io` adds short inputs and outputs when you need them.
4. `lf trace session <session-id> --compact` shows the turns around it, when the error depends
   on earlier turns.

## Time windows

`--from-ts` and `--to-ts` take ISO-8601 timestamps. Turn the user's words into UTC first: "the last
hour" is now minus one hour, "today" starts at `T00:00:00Z` of today's date, "this week" starts on
Monday. Say in the answer which window you used.

## Metrics

`lf metrics` reads `GET /api/public/v2/metrics`: aggregates over a time range, grouped the way you ask.

| Option | Meaning |
| --- | --- |
| `--metric totalCost,latency:p95` | What to compute: measure, then an optional aggregation |
| `--by providedModelName,name` | Group by these dimensions |
| `--where level=ERROR` | Filter; repeat it for more |
| `--granularity hour` | Group by time: minute, hour, day, week, month or auto. Rows come in time order with empty buckets included; do not add `--order-by`, which drops the empty buckets |
| `--from-ts`, `--to-ts` | The window; the last 24 hours by default |
| `--order-by sum_totalCost` | Sort by a result key, largest first; add `:asc` for smallest first |
| `--limit 20` | Return at most this many rows (1 to 1000; default 100, or 1000 with `--granularity`). When the result fills the limit, lf says so on stderr and more rows may exist |
| `--view scores-numeric` | Aggregate scores instead of observations |

Observation measures: `count`, `latency`, `timeToFirstToken`, `streamingLatency`, `inputTokens`,
`outputTokens`, `totalTokens`, `inputCost`, `outputCost`, `totalCost`, `tokensPerSecond`,
`outputTokensPerSecond`, `countScores`. Aggregations: `sum`, `avg`, `count`, `max`, `min`, `p50`,
`p75`, `p90`, `p95`, `p99`. Without one, `count` counts, `value` and the latency and speed measures
average, and everything else sums.

Observation dimensions for `--by` and `--where`: `name`, `type`, `level`, `environment`,
`providedModelName`, `promptName`, `promptVersion`, `traceName`, `tags`, `release`, `version`,
`isRootObservation`. `userId`, `sessionId` and `traceId` work in `--where` only.

The score views (`scores-numeric`, `scores-boolean`, `scores-categorical`) group by `name`, `source`,
`dataType`, `traceName` and `observationName`, and measure `value` and `count`.

```bash
lf metrics --metric totalCost,totalTokens --by providedModelName --from-ts 2026-10-20T00:00:00Z
lf metrics --where level=ERROR --by name --order-by count_count --from-ts 2026-10-24T00:00:00Z
lf metrics --where level=ERROR --where name=search_tool_call --granularity hour --from-ts 2026-10-24T00:00:00Z
lf metrics --where userId=user-3 --metric count --by name
```

## Servers without the v2 observations API

If `lf doctor` reports that `/api/public/v2/observations` is missing, the server predates
Langfuse v4; the trace commands need an upgraded server. Prompt, dataset and score commands
still work.
