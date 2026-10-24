# Output Conventions & Token Management

AI coding agents have bounded token budgets. Full trace payloads containing multi-turn completions,
system prompts, and function call inputs/outputs can easily exceed 50KB-200KB per trace.

## Best Practices for Agent Workflows

### 1. Compact Mode (`--compact`)
The `--compact` flag eliminates redundant metadata, flattens durations into seconds, aggregates error messages, and summarizes observations:

```bash
$ lf trace list --limit 5 --compact
[
  {
    "id": "c1f7a28e-64d1-4328-971c-4b6843653198",
    "name": "support-agent-turn",
    "timestamp": "2026-10-24T20:15:30.120Z",
    "latency_sec": 2.45,
    "cost_usd": 0.0084,
    "sessionId": "sess_9912",
    "errors": ["search_tool_call: 503 Service Unavailable"]
  }
]
```

### 2. Targeted Projection (`--agent-fields`)
Filter directly for specific keys:

```bash
$ lf trace list --agent-fields "id,name,latency_sec,errors"
```

### 3. Timeline Rendering
When diagnosing an issue for a human developer, use `--timeline` to get a structured ASCII tree:

```bash
$ lf trace get <trace-id> --timeline
Trace: support-flow (c1f7a28e...) (2.45s) [$0.0084]
Timestamp: 2026-10-24T20:15:30.120Z | Session: sess_9912
Observations Timeline:
  ✓ 1. SPAN: router_v2.classify [120ms] (model: claude-3-5-sonnet)
  ✓ 2. SPAN: support_agent.loop [1.80s]
  ✗ [ERROR] 3. GENERATION: search_tool_call [450ms]
      Message: 503 Service Unavailable
```
