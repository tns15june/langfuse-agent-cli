"""Shared test helpers: recorded Langfuse responses and CLI invocation."""
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Response body recorded from a Langfuse 4.70.0 instance seeded with synthetic data."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def route_doctor(fake_api, projects_status=200, observations_status=200):
    """Routes for the three requests `lf doctor` makes."""
    fake_api.route("GET", "/api/public/health", json=load_fixture("health"))
    projects = load_fixture("projects") if projects_status == 200 else {"message": "Invalid credentials"}
    fake_api.route("GET", "/api/public/projects", json=projects, status=projects_status)
    observations = load_fixture("obs_empty") if observations_status == 200 else None
    fake_api.route("GET", "/api/public/v2/observations", json=observations, status=observations_status,
                   text=None if observations_status == 200 else "<html>404</html>",
                   content_type="application/json" if observations_status == 200 else "text/html")
