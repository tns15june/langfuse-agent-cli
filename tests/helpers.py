"""Shared test helpers: recorded Langfuse responses and CLI invocation."""
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Response body recorded from a Langfuse 4.70.0 instance seeded with synthetic data."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
