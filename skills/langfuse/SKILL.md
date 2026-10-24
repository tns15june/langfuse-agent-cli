---
name: langfuse
description: >
  Use with Langfuse for LLM observability, prompt management, dataset evaluations,
  and trace inspection. Provides token-efficient queries and debugging for AI coding assistants.
---

# langfuse

Universal companion skill for the Langfuse platform. Use this skill whenever inspecting LLM application
telemetry, debugging failed agent loops, evaluating prompts, or querying traces and sessions.

Companions:
- `langfuse-prompts`: Fetching, compiling, and versioning prompts in code.
- `langfuse-traces`: In-depth error diagnosis, observation trees, and latency breakdown.

## Fast Path for Common Commands

| Need | Command |
|---|---|
| Check system and auth health | `lf doctor` |
| View command catalog | `lf help-map` |
| Fetch a prompt with variable preview | `lf prompt get <name> --label production --vars '{"var": "val"}'` |
| List recent failed traces | `lf trace list --status error --limit 10 --compact` |
| View trace timeline tree | `lf trace get <trace-id> --timeline` |
| Inspect full multi-turn session | `lf trace session <session-id> --compact` |
| Score a trace from evaluation | `lf score create --trace-id <id> --name "accuracy" --value 1.0` |

## Agent Token-Saving Rules

1. **Always use `--compact`** when querying lists of traces or sessions in agent loops to avoid blowing your context window.
2. **Use `--agent-fields <paths>`** when you only need specific attributes (e.g. `lf trace list --agent-fields "id,name,latency_sec,errors"`).
3. **Progressive Disclosure**: When unsure about command parameters, run `lf help describe "<command>"` rather than guessing arguments.
4. **Read Before Mutating**: Before pushing a new prompt version with `lf prompt push`, fetch the active version with `lf prompt get <name>` to prevent accidental schema changes.

## Authentication & Environments

- Default profiles live in `~/.config/langfuse/profiles.json`.
- Switch environments using `lf auth switch <profile>` (e.g. `local`, `uat`, `prod`, `cloud`).
- Environment variables `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` take precedence when supplied.
