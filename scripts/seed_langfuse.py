"""Seed a Langfuse project with synthetic data for tests/test_live.py.

Only run this against a throwaway project: it creates prompts, a dataset and traces.
Needs the `langfuse` SDK and LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL.
"""
import os
import sys
import time

import requests
from langfuse import get_client, propagate_attributes


def seed() -> None:
    lf = get_client()
    if not lf.auth_check():
        sys.exit("Langfuse rejected the keys")

    lf.create_prompt(name="welcome-bot", type="text", labels=["production"],
                     prompt="Hello {{user_name}}, welcome to the {{plan}} plan!")
    lf.create_prompt(name="support/greeter", type="chat", labels=["production", "staging"], tags=["support"],
                     prompt=[{"role": "system", "content": "You help {{user_name}} with their account."},
                             {"role": "user", "content": "{{question}}"}])

    lf.create_dataset(name="intent-classification-evals", description="Synthetic intent examples")
    examples = [("reset my password", "account"), ("upgrade to pro", "billing"), ("app crashes on start", "bug")]
    for text, intent in examples:
        lf.create_dataset_item(dataset_name="intent-classification-evals", input={"text": text},
                               expected_output={"intent": intent})

    big = "lorem ipsum dolor sit amet " * 150  # ~4 KB, so payload sizes are realistic
    for i in range(12):
        attrs = {"session_id": f"sess-{'abc'[i % 3]}", "user_id": f"user-{i % 4}", "tags": ["synthetic"],
                 "trace_name": "support-agent-turn"}
        with propagate_attributes(**attrs):
            with lf.start_as_current_observation(as_type="agent", name="support-agent-turn",
                                                 input={"msg": f"question {i}", "context": big}) as root:
                with lf.start_as_current_observation(as_type="generation", name="plan-step", model="gpt-4o-mini",
                                                     usage_details={"input": 900, "output": 120}) as gen:
                    gen.update(output={"plan": "call search", "notes": big})
                with lf.start_as_current_observation(as_type="tool", name="search_tool_call",
                                                     input={"q": f"query {i}"}) as tool:
                    if i in (2, 5, 8, 11):
                        message = "503 Service Unavailable" if i % 2 else "timeout after 30s"
                        tool.update(level="ERROR", status_message=message)
                    elif i == 3:
                        tool.update(level="WARNING", status_message="slow response (4.2s)", output={"hits": 1})
                    else:
                        tool.update(output={"hits": 3})
                root.update(output={"answer": None if i in (2, 5, 8, 11) else "done"})
    lf.flush()


def wait_for_errors(minimum: int = 4, timeout: float = 120) -> None:
    """OpenTelemetry ingestion is asynchronous; wait until the error observations are queryable."""
    host = os.environ["LANGFUSE_BASE_URL"].rstrip("/")
    auth = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = requests.get(f"{host}/api/public/v2/observations", params={"level": "ERROR", "limit": 50},
                            auth=auth, timeout=10)
        if resp.ok and len(resp.json().get("data", [])) >= minimum:
            return
        time.sleep(3)
    sys.exit(f"timed out after {timeout:.0f}s waiting for {minimum} ERROR observations")


if __name__ == "__main__":
    seed()
    wait_for_errors()
    print("seeded: 2 prompts, 1 dataset (3 items), 12 traces (4 with ERROR, 1 with WARNING)")
