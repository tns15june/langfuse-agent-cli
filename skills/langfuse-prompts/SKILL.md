---
name: langfuse-prompts
description: >
  Fetch, compile, diff, and update Langfuse prompts directly from code assistants.
---

# langfuse-prompts

Companion skill for managing and testing prompt templates stored in Langfuse.

## Common Workflows

### 1. Fetching a Production Prompt into Code
When developing an agent or evaluating prompt performance:

```bash
lf prompt get "customer-support-agent" --label production
```

### 2. Testing Mustache Template Compilation
Preview how variables will render without deploying or making LLM API calls:

```bash
lf prompt get "customer-support-agent" --vars '{"user_name": "Alice", "ticket_id": "TICKET-102"}'
```

### 3. Publishing a New Prompt Version
Save an updated prompt from a file or inline string:

```bash
# From file:
lf prompt push "customer-support-agent" --file ./prompts/support_v3.json --labels "staging"

# Inline text:
lf prompt push "greeter" --text "Hello {{name}}, welcome to our platform!" --labels "staging"
```

## Safety Rule
Always run `lf prompt get <name>` to inspect existing variables and model configurations before publishing an update.
