# Output

## Formats

- JSON (default): exactly one JSON document on stdout, safe to pipe into `jq`.
- Text (`-o text`): short lines for people. `lf trace get <trace-id> -o text` prints the timeline.
- Errors go to stderr and the exit code is non-zero.

Terminal control characters found in server data (trace names, inputs, error messages) are
printed escaped, for example `\x1b`.

## Smaller output

`--compact` removes fields that are null, empty strings, empty lists or empty objects, at every
level, for any command.

`--agent-fields` keeps only the listed fields of each row. Dotted paths reach into nested
objects and through lists:

```bash
lf trace get <trace-id> --agent-fields name,type,level,statusMessage,latency
lf trace list --agent-fields traceId,name,startTime --limit 20
```

Sizes measured on Langfuse 4.70 with synthetic data, for one trace with three observations:

| What was requested | Size |
| --- | --- |
| Every observation field group, including inputs and outputs | 12.9 KB |
| What `trace get` requests (no inputs/outputs) | 2.9 KB |
| What `trace list` requests per row (`core,basic`) | 1.65 KB for the 3 rows |

## Failing traces

`lf trace list --status error` returns one entry per trace:

```json
[
  {
    "traceId": "487b674e9a38e8d85cd683d2f022bf1d",
    "sessionId": "sess-c",
    "userId": "user-3",
    "errors": [
      {
        "id": "b3a7feb56ff30ecb",
        "name": "search_tool_call",
        "type": "TOOL",
        "statusMessage": "503 Service Unavailable",
        "startTime": "2026-10-24T21:46:02.173Z"
      }
    ]
  }
]
```

## Timeline

`lf trace get <trace-id> --timeline` prints the observation tree; children are indented under
their parent and siblings are ordered by start time:

```text
Trace 487b674e9a38e8d85cd683d2f022bf1d: 3 observations, 1 error
✓ AGENT support-agent-turn [1ms]
  ✓ GENERATION plan-step [0ms] (model: gpt-4o-mini)
  ✗ [ERROR] TOOL search_tool_call [0ms]
      Message: 503 Service Unavailable
```

`✗ [ERROR]` and `⚠ [WARN]` mark failed and warning observations. With `--io`, inputs and outputs
shorter than 120 characters appear under their observation.
