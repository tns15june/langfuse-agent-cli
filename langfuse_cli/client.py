"""REST API client for Langfuse."""
from __future__ import annotations

import json
from typing import Optional, Dict, Any, List
import requests
from requests.auth import HTTPBasicAuth

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
            "User-Agent": "langfuse-agent-cli/0.1.0",
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
            )
        except requests.exceptions.ConnectionError as e:
            raise LangfuseAPIError(f"Connection failed to {self.host}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise LangfuseAPIError(f"Request timed out connecting to {self.host} ({self.timeout}s)") from e

        if not resp.ok:
            try:
                message = resp.json().get("message")
            except (ValueError, AttributeError):
                message = None
            if message:
                error_msg = f"HTTP {resp.status_code}: {message}"
            elif "html" in resp.headers.get("Content-Type", ""):
                error_msg = f"HTTP {resp.status_code} on {path}"  # framework error pages carry no detail
            else:
                error_msg = f"HTTP {resp.status_code} on {path}: {resp.text[:200]}"
            raise LangfuseAPIError(error_msg, status_code=resp.status_code, response_body=resp.text)

        if not resp.content:
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

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
        return self._request("GET", f"/api/public/v2/prompts/{name}", params=params)

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

    # 3. Traces API
    def list_traces(
        self,
        page: int = 1,
        limit: int = 20,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "limit": limit}
        if session_id:
            params["sessionId"] = session_id
        if user_id:
            params["userId"] = user_id
        if from_ts:
            params["fromTimestamp"] = from_ts
        if to_ts:
            params["toTimestamp"] = to_ts
        if tags:
            params["tags"] = tags
        return self._request("GET", "/api/public/traces", params=params)

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/public/traces/{trace_id}")

    # 4. Sessions API
    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/public/sessions/{session_id}")

    # 5. Datasets API
    def list_datasets(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        return self._request("GET", "/api/public/datasets", params={"page": page, "limit": limit})

    def get_dataset(self, name: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/public/datasets/{name}")

    def create_dataset_run(
        self,
        dataset_name: str,
        run_name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "datasetName": dataset_name,
            "name": run_name,
        }
        if description:
            body["description"] = description
        if metadata:
            body["metadata"] = metadata
        return self._request("POST", "/api/public/dataset-runs", data=body)

    # 6. Scores API
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
