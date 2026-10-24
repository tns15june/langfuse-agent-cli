# RFC: Agent-Native CLI and Coding Assistant Skills (`langfuse-cli`)

**Author**: Tarkeshwar Narayan (@tns15june)  
**Repository**: [https://github.com/tns15june/langfuse-agent-cli](https://github.com/tns15june/langfuse-agent-cli)  
**Status**: Proposal / Working Prototype Available  
**Target**: `langfuse/langfuse` Community & Ecosystem  

---

## 1. Executive Summary

As AI coding assistants (Claude Code, Cursor, Antigravity, OpenCode, GitHub Copilot) become standard development environments for engineers building LLM applications, there is an increasing friction: **developers constantly switch between their terminal/codebase and the Langfuse Web UI** to inspect traces, pull/test prompts, and triage runtime errors.

Furthermore, when AI coding agents attempt to debug LLM applications autonomously, standard API dumps return verbose, uncompressed JSON (50KB–200KB per trace) that quickly bloats the agent's context window.

This RFC proposes **an Agent-Native CLI (`lf`) and Companion Skills library for Langfuse**, modeled after the architectural successes of Atlassian's **Teamwork Graph (TWG) CLI**. A fully tested, functional working prototype has been developed and verified against local Langfuse (`v4.30.0`).

---

## 2. Key Pain Points & Motivation

1. **Prompt Management in Code**:
   Developers writing agent prompts or evaluation harnesses must leave their IDE to inspect prompt versions, copy Mustache templates, or verify variable substitutions. An agent-native command (`lf prompt get <name> --vars '{...}'`) brings prompt compilation directly into local test loops.
2. **Observability Triage Without Context Switching**:
   When a local integration test or evaluation fails, human engineers and AI coding assistants need instant visibility into failing tool calls, model outputs, and latency without opening a browser tab.
3. **Agent Token Consumption**:
   Traditional REST responses contain extensive metadata, raw system prompts, and full execution payloads. Coding agents need **compact, token-efficient projections** (`--compact`, `--agent-fields`) that extract high-signal indicators (errors, model names, latency, cost) while saving 80–90% of token context.
4. **Agent Skill Fragmentation**:
   Different tools look in different locations for skill definitions (`~/.claude/skills`, `~/.agents/skills`, `~/.cursor/skills`, `~/.gemini/config/skills`). A unified CLI command (`lf skills install`) provides automated, multi-platform deployment.

---

## 3. Architecture & Design Principles

Inspired by Atlassian's TWG CLI, the design rests on four pillars:

```text
┌────────────────────────────────────────────────────────┐
│             AI Coding Assistants & Humans              │
│     (Claude Code, Cursor, Antigravity, Terminal)       │
└───────────────────────────┬────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│     Agent Companion Skills    │   │        Langfuse CLI (lf)      │
│  - skills/langfuse/SKILL.md   │   │  - Auth Profiles & Doctor     │
│  - langfuse-prompts/SKILL.md  │◄──┤  - Output Compactor & Fields  │
│  - langfuse-traces/SKILL.md   │   │  - Progressive Disclosure     │
└───────────────┬───────────────┘   └───────────────┬───────────────┘
                │                                   │
                └─────────────────┬─────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │     Langfuse Public API   │
                    │   (Cloud & Self-Hosted)   │
                    └───────────────────────────┘
```

### Pillar 1: Progressive Disclosure (`help-map` & `describe`)
AI coding assistants perform better when they can dynamically discover available operations without reading bloated documentation:
- `lf help-map`: Returns a compact catalog of commands, their purpose, and whether they mutate state (`*`).
- `lf help describe "<command>"`: Emits a structured JSON schema detailing exact options, types, and execution rules.

### Pillar 2: Token-Saving Formatters
- `--compact`: Aggregates errors, flattens durations, lists distinct models used, and removes redundant trace attributes.
- `--agent-fields <paths>`: Projects nested JSON fields down to exact developer-requested attributes.

### Pillar 3: Terminal Timeline Visualizer
`lf trace get <trace-id> --timeline` renders a clean ASCII observation tree highlighting tool calls, latencies, and error messages.

### Pillar 4: Multi-Agent Companion Skills
The companion skills (`SKILL.md`) adhere to the open Agent Skills standard and are automatically installed and synced to:
- Claude Code (`~/.claude/skills/`)
- Antigravity (`~/.gemini/config/skills/`)
- Universal Agents (`~/.agents/skills/`)
- Cursor (`~/.cursor/skills/`)
- OpenCode (`~/.config/opencode/skills/`)

---

## 4. Command Specification

| Command Family | Operations | Key Capabilities |
|---|---|---|
| **Auth & Config** | `lf auth login`, `switch`, `list`, `status` | Supports multiple profiles (`local`, `staging`, `prod`, `cloud`), masked keys, and standard `LANGFUSE_*` env vars. |
| **Diagnostics** | `lf doctor` | End-to-end audit of API health, auth validity, and agent skill installations. |
| **Prompts** | `lf prompt list`, `get`, `push` | Fetch by version/label, compile Mustache templates inline with `--vars '{"key": "val"}'`, publish from files or raw text. |
| **Traces** | `lf trace list`, `get`, `session` | Filter by status (`error`), session ID, time windows; `--timeline` ASCII tree renderer; `--compact` agent format. |
| **Datasets & Evals** | `lf dataset list`, `get`, `run`, `lf score create` | Inspect ground-truth items, trigger evaluation runs, and record quantitative scores on traces. |
| **Agent Skills** | `lf skills list`, `install` | Discovers and deploys companion skills across all installed coding assistant directories. |

---

## 5. Working Prototype Validation

A working implementation was developed and validated against a local self-hosted Langfuse stack (`v4.30.0`):

1. **Diagnostics (`lf doctor`)**:
   Successfully verified local host connectivity on `:3000`, validated API key authorization against the traces probe, and inspected skill directory health.
2. **Trace Inspection (`lf trace list --compact`)**:
   Verified that trace outputs are compressed into token-efficient payloads with observation error extraction.
3. **Trace Timeline (`lf trace get <id> --timeline`)**:
   Rendered execution timelines of tool calls and latencies.
4. **Prompt Lifecycle (`lf prompt push` & `lf prompt get`)**:
   Published a test prompt `welcome-bot` (v1) and compiled Mustache variables (`{{user_name}}`, `{{plan}}`) into the final output.
5. **Automated Test Suite**:
   Pytest suite covering config management, template compilation, agent formatters, and skill deployment passed (100% pass rate).

---

## 6. Proposed Contribution Paths

We would love feedback from the Langfuse maintainers and community on the preferred path forward:

- **Option A (Official Monorepo Package)**:
  Contribute as an official package under `packages/cli` in `langfuse/langfuse`, published to npm/PyPI under `@langfuse/cli` or `langfuse-cli`.
- **Option B (Community Ecosystem Project)**:
  Maintain as an independent, community-driven open-source project (`langfuse-agent-cli`), featured in the official Langfuse ecosystem documentation and integration directory.

---

## 7. Next Steps

1. Publish prototype to a public GitHub repository with open MIT license.
2. Share RFC on Langfuse GitHub Discussions and Discord (`#contributing` / `#showcase`).
3. Gather feedback from the Langfuse core team (Marc Klingen, Clemens Rawert, Max Deichmann) and community users.
