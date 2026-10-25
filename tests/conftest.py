import json as jsonlib
import os
from urllib.parse import urlsplit

import pytest
import requests

from langfuse_cli import config
from langfuse_cli.commands import doctor


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Keep every test away from the real profiles file, ./.env and LANGFUSE_* variables."""
    monkeypatch.setattr(config, "DEFAULT_PROFILES_FILE", tmp_path / "profiles.json")
    monkeypatch.chdir(tmp_path)
    for name in [n for n in os.environ if n.startswith("LANGFUSE_")]:
        monkeypatch.delenv(name)


class FakeAPI:
    """Stands in for the Langfuse server at the HTTP boundary (requests.Session.request)."""

    def __init__(self):
        self.routes = {}
        self.calls = []  # (method, path, params) with params as sent on the wire
        self.bodies = []  # JSON request bodies, parallel to calls

    def route(self, method, path, json=None, status=200, text=None, content_type="application/json", headers=None):
        """Queue a response; several routes for one path are served in order, the last one repeats."""
        self.routes.setdefault((method, path), []).append((json, status, text, content_type, headers or {}))

    def __call__(self, method, url, params=None, json=None, **kwargs):
        # Installed as a class attribute on requests.Session; an instance is not bound, so no session arg.
        path = urlsplit(url).path
        self.calls.append((method, path, {k: [str(i) for i in v] if isinstance(v, list) else str(v)
                                          for k, v in (params or {}).items()}))
        self.bodies.append(json)
        queue = self.routes.get((method, path))
        if not queue:
            raise AssertionError(f"unrouted request: {method} {path}")
        body, status, text, content_type, headers = queue.pop(0) if len(queue) > 1 else queue[0]
        resp = requests.Response()
        resp.status_code = status
        resp.url = url
        resp.headers["Content-Type"] = content_type
        resp.headers.update(headers)
        resp._content = (text if text is not None else jsonlib.dumps(body or {})).encode()
        return resp


@pytest.fixture
def no_skill_dirs(monkeypatch, tmp_path):
    """Doctor looks for the skill only under tmp_path, never in the real home directory."""
    monkeypatch.setattr(doctor, "KNOWN_SKILL_TARGETS", [("Claude Code", tmp_path / "skills")])


@pytest.fixture
def fake_api(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(requests.Session, "request", api)
    return api
