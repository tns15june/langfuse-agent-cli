# Querying Traces and Observability Data

## Filtering Traces

### By Session
When an agent or user reports a conversation issue, filter by the full conversation session:

```bash
lf trace list --session-id <session_id> --compact
# or fetch consolidated session
lf trace session <session_id> --compact
```

### By Errors
To locate failures quickly:

```bash
lf trace list --status error --limit 10 --compact
```

### By Time Window
Filter traces by ISO8601 timestamps:

```bash
lf trace list --from-ts "2026-10-24T18:00:00Z" --to-ts "2026-10-24T20:00:00Z"
```

### By User
Inspect activity for a specific end user or account:

```bash
lf trace list --user-id "user_12345" --limit 5
```
