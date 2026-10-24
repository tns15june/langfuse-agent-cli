# Langfuse Agent CLI (`lf`)

> An agent-native CLI and companion skills library for [Langfuse](https://github.com/langfuse/langfuse), designed for human developers and AI coding assistants (Claude Code, Cursor, Antigravity, Codex, OpenCode).

Inspired by the architecture of Atlassian's **Teamwork Graph (TWG) CLI**, `lf` bridges LLM observability, prompt management, and dataset evaluations directly into terminal and coding agent workflows with **strict token efficiency and progressive disclosure**.

---

## 🌟 Why Langfuse Agent CLI?

When developers build LLM applications with AI pair programmers:
1. **Prompt Management in Code**: Fetching production prompt templates, testing Mustache variable compilation, or pushing new prompt versions without opening a web browser.
2. **Terminal Debugging & Observability**: Inspecting failed agent turns, viewing latency breakdowns, or investigating tool call errors during local test runs.
3. **Agent Token Preservation**: Traditional REST API dumps return bloated JSON (50KB-200KB) that consumes large amounts of model context. `lf` provides `--compact` and `--agent-fields` projections that compress telemetry payloads by 80-90%.
4. **Companion Skills Standard**: Automatically installs open `SKILL.md` companion skills across all coding assistant environments.

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/tns15june/langfuse-agent-cli.git
cd langfuse-agent-cli

# Install in editable mode
pip install -e .
```

Verify installation:
```bash
lf --version
lf help-map
```

### 1. Configure Authentication

Configure connection profiles for Cloud, Staging, or Local instances:

```bash
# Connect to local Langfuse
lf auth login --profile-name local --host http://localhost:3000 --default

# Or connect to Langfuse Cloud
lf auth login --profile-name cloud --host https://cloud.langfuse.com
```

### 2. Verify System Health (`doctor`)

Run full diagnostics across connectivity, API keys, and agent skill locations:

```bash
lf doctor
```

```text
Langfuse Agent CLI System Diagnostics
=============================================
1. Build & Runtime
  CLI Version: 0.1.0
  Python Version: 3.11.15

2. Resolved Authentication
  Profile Name: local
  Host Endpoint: http://localhost:3000
  Public Key: pk-lf-...abcd
  Secret Key: sk-lf-...wxyz
  ✓ Connectivity: OK (server status: OK, version: 4.30.0)
  ✓ API Authorization: Valid (trace probe returned 1 items)

3. Agent Skills Ecosystem
  ✓ Claude Code        Installed at ~/.claude/skills/langfuse
  ✓ Antigravity        Installed at ~/.gemini/config/skills/langfuse
  ✓ Universal Agents   Installed at ~/.agents/skills/langfuse
```

### 3. Deploy Skills to Your Coding Assistants

Install the bundled companion skills into all active coding agent environments:

```bash
lf skills install
```

Supported platforms:
- **Claude Code**: `~/.claude/skills/`
- **Antigravity**: `~/.gemini/config/skills/`
- **Universal Agents / AGY**: `~/.agents/skills/`
- **Cursor**: `~/.cursor/skills/`
- **OpenCode**: `~/.config/opencode/skills/`

---

## 📖 Command Reference

### Prompt Management (`lf prompt`)

```bash
# List prompts
lf prompt list

# Fetch a prompt and compile mustache variables
lf prompt get "welcome-bot" --vars '{"user_name": "Alice", "plan": "pro"}'

# Publish a new prompt version
lf prompt push "support-agent" --file ./prompts/agent_v2.json --labels "staging"
```

### Observability & Traces (`lf trace`)

```bash
# List recent traces with compact agent projection
lf trace list --limit 10 --compact

# Filter for failed agent turns
lf trace list --status error --limit 5 --compact

# Render visual turn-by-turn ASCII timeline
lf trace get <trace-id> --timeline

# Query all traces belonging to a multi-turn conversation session
lf trace session <session-id> --compact
```

### Datasets & Evaluations (`lf dataset`, `lf score`)

```bash
# List datasets
lf dataset list

# Fetch ground-truth items
lf dataset get "intent-classification-evals"

# Record an evaluation score against a trace
lf score create --trace-id <trace_id> --name "accuracy" --value 1.0 --comment "All constraints matched"
```

### Progressive Disclosure for AI Agents

```bash
# High-level command catalog (* indicates mutation)
lf help-map

# Detailed schema and usage rules for an agent planning a call
lf help "prompt get" -o json
```

---

## 🧩 Architecture

```text
langfuse-agent-cli/
├── pyproject.toml                     # Package & CLI script definitions
├── README.md                          # Documentation
├── RFC.md                             # Open Source contribution proposal
├── langfuse_cli/
│   ├── cli.py                         # Argument parser & command dispatcher
│   ├── client.py                      # Resilient REST API client (Auth, Health, Retries)
│   ├── config.py                      # Multi-profile manager (~/.config/langfuse/profiles.json)
│   ├── commands/                      # Subcommand handlers (auth, doctor, prompt, trace, skills)
│   └── formatters/
│       ├── agent.py                   # Token-saving compact JSON & field selectors
│       └── timeline.py                # Visual terminal ASCII trace renderer
├── skills/                            # Agent Skills (SKILL.md)
│   ├── langfuse/                      # Root agent skill
│   ├── langfuse-prompts/              # Prompt management companion skill
│   └── langfuse-traces/               # Observability & error debugging companion skill
└── tests/                             # Pytest test suite
```

---

## 🤝 Contributing to Open Source

This project is prepared for contribution to the [Langfuse](https://github.com/langfuse/langfuse) ecosystem. See [`RFC.md`](./RFC.md) for the detailed proposal and discussion points.
