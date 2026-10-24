---
name: langfuse-traces
description: >
  Debug multi-turn agent conversations, diagnose tool-call errors, and analyze latency bottlenecks using Langfuse traces.
---

# langfuse-traces

Companion skill for diagnosing LLM runtime behavior, tool calls, and performance bottlenecks.

## Triage Workflow for Failed Agent Runs

1. **Locate Failed Traces**:
   ```bash
   lf trace list --status error --limit 5 --compact
   ```
2. **Inspect Trace Timeline**:
   ```bash
   lf trace get <trace-id> --timeline
   ```
   Look for `✗ [ERROR]` marks identifying the exact failing span or tool call.
3. **Session-Level Context**:
   If the issue spans multiple turns:
   ```bash
   lf trace session <session-id> --compact
   ```
4. **Inspect Specific Field Payloads**:
   ```bash
   lf trace get <trace-id> --agent-fields "observations.name,observations.statusMessage"
   ```
