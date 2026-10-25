# Agent examples

Questions people ask their coding agent, and the `lf` commands that answer them. Times are UTC:
replace `<start>`, `<end>` and `<today>` with ISO timestamps such as `2026-10-20T00:00:00Z`.

## Failures

**"Why did my LLM app fail in the last hour?"**

```bash
lf trace list --status error --from-ts <start> --limit 10 --compact
lf trace get <trace-id> --timeline
```

Each failing trace lists its failed steps with their `statusMessage`. One trace's timeline shows where
in the run the step failed.

**"Which tool fails most often this week, and is it getting worse?"**

```bash
lf metrics --where level=ERROR --by name --order-by count_count --from-ts <start>
lf metrics --where level=ERROR --where name=<tool> --granularity day --from-ts <start>
```

**"Was last night's error spike one outage or several problems?"**

```bash
lf metrics --where level=ERROR --granularity hour --from-ts <start> --to-ts <end>
lf trace list --status error --from-ts <start> --to-ts <end> --limit 20 --compact
```

Errors from one step with one message, inside one burst, point to a single cause, such as a service
that was down.

## One trace

**"What happened in trace 33579e8e8ec602e878f0744ad53ac1fe?"**

```bash
lf trace get 33579e8e8ec602e878f0744ad53ac1fe --timeline
```

**"What did the model get and answer in that trace?"**

```bash
lf trace get 33579e8e8ec602e878f0744ad53ac1fe --io --output-summary
```

When the output is a summary, read the file it names:
`jq '.[] | select(.type == "GENERATION") | {name, input, output}' <outputFile>`.

## Conversations and users

**"Walk me through the conversation in session sess-c."**

```bash
lf trace session sess-c --compact
lf trace get <trace-id> --timeline --io
```

**"What did user user-3 run into today?"**

```bash
lf trace list --user-id user-3 --from-ts <today> --compact
lf trace list --user-id user-3 --status error --from-ts <today> --compact
```

## Cost and tokens

**"What did we spend on each model this week?"**

```bash
lf metrics --metric totalCost,totalTokens --by providedModelName --from-ts <start>
```

`sum_totalCost` is in USD. Rows with a null model are steps that are not model calls.

**"How many tokens did we use per day?"**

```bash
lf metrics --metric totalTokens --granularity day --from-ts <start>
```

**"Which prompt version costs the most?"**

```bash
lf metrics --metric totalCost --by promptName,promptVersion --order-by sum_totalCost --from-ts <start>
```

## Speed

**"Which step of my agent is the slowest?"**

```bash
lf metrics --metric latency:p95 --by name --order-by p95_latency --from-ts <start>
```

Metrics latency is in milliseconds.

**"Which runs were slowest today?"**

```bash
lf trace list --from-ts <today> --limit 100 --agent-fields traceId,name,latency,startTime
```

Sort the rows by `latency`, which trace rows give in seconds.

**"How quickly does each model start answering?"**

```bash
lf metrics --metric timeToFirstToken:p50 --by providedModelName --from-ts <start>
```

## Prompts

**"Which version of the welcome-bot prompt is live?"**

```bash
lf prompt get welcome-bot --label production -o text
```

**"Show it for Alice on the pro plan."**

```bash
lf prompt get welcome-bot --label production --vars '{"user_name": "Alice", "plan": "pro"}' -o text
```

**"Put a new version on staging that greets people by first name."** This writes: read the current
version first, tell the user what will change, and push only after they agree.

```bash
lf prompt get welcome-bot
lf prompt push welcome-bot --text 'Hi {{user_name}}, welcome to the {{plan}} plan!' --labels staging
```

## Datasets and scores

**"What is in the intent-classification-evals dataset?"**

```bash
lf dataset get intent-classification-evals --compact
```

**"How are our evaluation scores this week?"**

```bash
lf metrics --view scores-numeric --metric value --by name --from-ts <start>
```

**"Mark that trace as correct."** This writes; run it when the user asks.

```bash
lf score create --trace-id <trace-id> --name correctness --value 1 --comment 'checked by hand'
```

## Setup

**"Is lf connected to Langfuse?"**

```bash
lf doctor
```

**"Install lf for me."** Follow https://tns15june.github.io/langfuse-agent-cli/AGENTS.md.
