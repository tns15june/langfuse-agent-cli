"""REST API client for Langfuse."""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth

from langfuse_cli import __version__
from langfuse_cli.config import ProfileConfig


class LangfuseAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class LangfuseClient:
    """Client for Langfuse Public REST API v2."""

    def __init__(self, profile: ProfileConfig, timeout: float = 15.0):
        self.profile = profile
        self.host = profile.host.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"langfuse-agent-cli/{__version__}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        if profile.public_key and profile.secret_key:
            self.session.auth = HTTPBasicAuth(profile.public_key, profile.secret_key)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.host}{path}"
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data if data else None,
                timeout=self.timeout,
                allow_redirects=method == "GET",  # requests would replay a redirected POST as a GET
            )
        except requests.exceptions.ConnectionError as e:
            raise LangfuseAPIError(f"Connection failed to {self.host}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise LangfuseAPIError(f"Request timed out connecting to {self.host} ({self.timeout}s)") from e
        except requests.exceptions.RequestException as e:  # e.g. a host without http(s)://
            raise LangfuseAPIError(f"Request to {url} failed: {e}") from e

        if resp.is_redirect:  # only writes get here; a 3xx also counts as resp.ok
            location = resp.headers.get("Location")
            raise LangfuseAPIError(f"{method} {path} was redirected to {location}; set the host to the final URL",
                                   status_code=resp.status_code)
        if not resp.ok:
            try:
                body = resp.json()
                message = body.get("message")
                details = body.get("error")
            except (ValueError, AttributeError):
                message, details = None, None
            if message and isinstance(details, list) and details and isinstance(details[0], dict):
                detail = details[0].get("message")  # validation errors say which value was wrong
                message = f"{message}: {detail}" if detail else message
            if message:
                error_msg = f"HTTP {resp.status_code}: {message}"
            elif "html" in resp.headers.get("Content-Type", ""):
                error_msg = f"HTTP {resp.status_code} on {path}"  # framework error pages carry no detail
            else:
                error_msg = f"HTTP {resp.status_code} on {path}: {resp.text[:200]}"
            raise LangfuseAPIError(error_msg, status_code=resp.status_code, response_body=resp.text)

        try:
            return resp.json()  # every endpoint lf calls answers 2xx with a JSON body
        except ValueError as e:
            kind = resp.headers.get("Content-Type") or "no content type"
            raise LangfuseAPIError(f"HTTP {resp.status_code} on {path} is not JSON ({kind}); is a login page or proxy "
                                   "answering instead of Langfuse?", status_code=resp.status_code,
                                   response_body=resp.text) from e

    # 1. System Health
    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/api/public/health")

    def get_project(self) -> Dict[str, Any]:
        """Project the API key belongs to; a cheap check that the keys are valid."""
        return self._request("GET", "/api/public/projects")

    # 2. Prompts API
    def list_prompts(
        self,
        page: int = 1,
        limit: int = 50,
        tag: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if tag:
            params["tag"] = tag
        if name:
            params["name"] = name
        return self._request("GET", "/api/public/v2/prompts", params=params)

    def get_prompt(
        self,
        name: str,
        version: Optional[int] = None,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if version is not None:
            params["version"] = version
        if label:
            params["label"] = label
        # Prompt names may contain "/" (folders); the API expects them encoded as one path segment.
        return self._request("GET", f"/api/public/v2/prompts/{quote(name, safe='')}", params=params)

    def create_prompt(
        self,
        name: str,
        prompt_content: Any,
        prompt_type: str = "text",
        config: Optional[Dict[str, Any]] = None,
        labels: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "name": name,
            "type": prompt_type,
            "prompt": prompt_content,
        }
        if config:
            body["config"] = config
        if labels:
            body["labels"] = labels
        if tags:
            body["tags"] = tags
        return self._request("POST", "/api/public/v2/prompts", data=body)

    # 3. Observations API v2: the v4 read path for traces, sessions and errors
    def list_observations(self, **params: Any) -> Dict[str, Any]:
        query = {k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items() if v is not None}
        return self._request("GET", "/api/public/v2/observations", params=query)

    def iter_observations(self, params: Dict[str, Any], max_items: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """Yield observations across cursor pages, stopping after max_items when given."""
        remaining = max_items
        cursor = None
        while remaining is None or remaining > 0:
            page = self.list_observations(
                **params, limit=1000 if remaining is None else min(1000, remaining), cursor=cursor
            )
            data = page.get("data", [])
            if remaining is not None:
                data = data[:remaining]
                remaining -= len(data)
            yield from data
            cursor = (page.get("meta") or {}).get("cursor")
            if not cursor:
                return

    # 4. Datasets API
    def list_datasets(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        return self._request("GET", "/api/public/v2/datasets", params={"page": page, "limit": limit})

    def get_dataset(self, name: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/public/v2/datasets/{quote(name, safe='')}")

    def metrics(self, query: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("GET", "/api/public/v2/metrics", params={"query": json.dumps(query)})

    def list_dataset_items(self, dataset_name: str, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        params = {"datasetName": dataset_name, "page": page, "limit": limit}
        return self._request("GET", "/api/public/dataset-items", params=params)

    # 5. Scores API
    def create_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: Optional[str] = None,
        observation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "traceId": trace_id,
            "name": name,
            "value": value,
        }
        if comment:
            body["comment"] = comment
        if observation_id:
            body["observationId"] = observation_id
        return self._request("POST", "/api/public/scores", data=body)
