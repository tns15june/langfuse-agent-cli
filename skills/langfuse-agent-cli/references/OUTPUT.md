# Output

## Formats

- JSON (default for data commands): exactly one JSON document on stdout, safe to pipe into `jq`.
  `doctor`, `setup`, `auth`, `help-map` and `trace get --timeline` print text.
- Text (`-o text`): short lines for people. `lf trace get <trace-id> -o text` prints the timeline.
- Errors go to stderr and the exit code is non-zero; `doctor`, `setup` and `auth status` print their
  report, failures included, on stdout.

Terminal control characters found in server data (trace names, inputs, error messages) are
printed escaped, as `\u001b` and so on; inside JSON that is an ordinary escape, so values are unchanged.

## Smaller output

`--compact` removes fields that are null, empty strings, empty lists or empty objects, at every
level, in the JSON output of the data commands. Rows stay in place even when they end up empty.

`--agent-fields` keeps only the listed fields of each row and leaves out listed fields whose value
is null. Dotted paths reach into nested objects and through lists:

```bash
lf trace get <trace-id> --agent-fields name,type,level,statusMessage,latency
lf trace list --agent-fields traceId,name,startTime --limit 20
```

API response sizes measured on Langfuse 4.70 with synthetic data, for one trace with three
observations (`lf` indents its JSON, so what it prints is about a quarter larger):

| Field groups requested | Size |
| --- | --- |
| All ten, including inputs and outputs | 12.9 KB |
| `core,basic,time,model,usage` | 2.9 KB |
| `core,basic` | 1.65 KB |

`trace get` requests `core,basic,time,model,usage,metrics` (no inputs/outputs, metadata or prompt
fields); the list commands request `core,basic,metrics`. `metrics` adds a few bytes per row.

## Large output

With `--output-summary`, JSON output larger than 16 KB, measured after `--agent-fields` and
`--compact`, is written to a new file in the system temp directory, readable only by you. The command
prints a summary instead. This one came from `lf trace list --limit 100 --output-summary` on a
synthetic project (24,322 bytes of JSON, 36 rows), with the path and the key list shortened:

```json
{
  "summary": true,
  "outputFile": "/tmp/lf-y7qgu_0r.json",
  "bytes": 24322,
  "rows": 36,
  "rowKeys": ["id", "traceId", "startTime", "name", "level", "statusMessage", "latency", "sessionId"],
  "hint": "The JSON output is larger than 16 KB, so it was written to outputFile. Read only the parts you need, for example with jq, or narrow the command with --agent-fields."
}
```

A list gives `rows` and `rowKeys`, the keys found in its rows; an object, such as the result of
`dataset get`, gives `keys`. Output of 16 KB or less is printed as usual, so check for
`"summary": true` before you use the result. Read the file with `jq`, for example
`jq '.[] | select(.level == "ERROR") | {traceId, statusMessage}' /tmp/lf-y7qgu_0r.json`. Text output
is never summarized, and `lf` does not delete the files.

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
Trace 33579e8e8ec602e878f0744ad53ac1fe: 3 observations, 1 error
✓ AGENT support-agent-turn
  ✓ GENERATION plan-step (model: gpt-4o-mini)
  ✗ [ERROR] TOOL search_tool_call
      Message: 503 Service Unavailable
```

`✗ [ERROR]` and `⚠ [WARN]` mark failed and warning observations. A measured duration appears in
brackets, such as `[1.24s]`; Langfuse 4.70 reports none for observations of zero length, like these
synthetic ones. With `--io`, inputs and outputs shorter than 120 characters appear under their
observation.
