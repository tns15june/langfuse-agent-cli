"""Configuration and profile management for Langfuse CLI."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "langfuse"
DEFAULT_PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


@dataclass
class ProfileConfig:
    name: str
    host: str
    public_key: str
    secret_key: str

    def is_complete(self) -> bool:
        return bool(self.host and self.public_key and self.secret_key)

    def masked_public_key(self) -> str:
        if not self.public_key:
            return "(not set)"
        if len(self.public_key) <= 8:
            return "******"
        return f"{self.public_key[:6]}...{self.public_key[-4:]}"

    def masked_secret_key(self) -> str:
        if not self.secret_key:
            return "(not set)"
        if len(self.secret_key) <= 8:
            return "******"
        return f"{self.secret_key[:6]}...{self.secret_key[-4:]}"


class ConfigManager:
    """Manages persistent profiles and active session configurations."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_PROFILES_FILE
        self._cache: Optional[Dict[str, Any]] = None

    def _ensure_dir(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not self.config_path.exists():
            self._cache = {"current_profile": "default", "profiles": {}}
            return self._cache
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
                if "profiles" not in self._cache:
                    self._cache["profiles"] = {}
                return self._cache
        except Exception:
            self._cache = {"current_profile": "default", "profiles": {}}
            return self._cache

    def _save_raw(self, data: Dict[str, Any]) -> None:
        self._ensure_dir()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # secure file permissions
        try:
            os.chmod(self.config_path, 0o600)
        except OSError:
            pass
        self._cache = data

    def list_profiles(self) -> Dict[str, ProfileConfig]:
        data = self._load_raw()
        profiles = {}
        for name, p in data.get("profiles", {}).items():
            profiles[name] = ProfileConfig(
                name=name,
                host=p.get("host", ""),
                public_key=p.get("public_key", ""),
                secret_key=p.get("secret_key", ""),
            )
        return profiles

    def get_current_profile_name(self) -> str:
        return self._load_raw().get("current_profile", "default")

    def set_current_profile(self, name: str) -> None:
        data = self._load_raw()
        data["current_profile"] = name
        self._save_raw(data)

    def save_profile(
        self,
        name: str,
        host: str,
        public_key: str,
        secret_key: str,
        set_default: bool = False,
    ) -> None:
        data = self._load_raw()
        clean_host = host.rstrip("/")
        data["profiles"][name] = {
            "host": clean_host,
            "public_key": public_key,
            "secret_key": secret_key,
        }
        if set_default or len(data["profiles"]) == 1:
            data["current_profile"] = name
        self._save_raw(data)

    def resolve_profile(
        self,
        name: Optional[str] = None,
        host_override: Optional[str] = None,
        pk_override: Optional[str] = None,
        sk_override: Optional[str] = None,
        env_file: Optional[str] = None,
    ) -> ProfileConfig:
        """Resolves config with precedence: CLI overrides > Named Profile > Env vars."""
        # 1. Start from named or current profile
        target_name = name or os.environ.get("LANGFUSE_PROFILE") or self.get_current_profile_name()
        profiles = self.list_profiles()
        base = profiles.get(
            target_name,
            ProfileConfig(name=target_name, host="", public_key="", secret_key=""),
        )

        host = base.host
        pk = base.public_key
        sk = base.secret_key

        # 2. Check .env if requested or fallback to env vars if profile is incomplete
        env_dict = {}
        if env_file and os.path.exists(env_file):
            env_dict = self._parse_dotenv(env_file)
        elif not base.is_complete() and os.path.exists(".env"):
            env_dict = self._parse_dotenv(".env")

        # Fallback to environment variables / dotenv values if not present in profile
        if not host:
            host = os.environ.get("LANGFUSE_HOST") or env_dict.get("LANGFUSE_HOST") or ""
        if not pk:
            pk = os.environ.get("LANGFUSE_PUBLIC_KEY") or env_dict.get("LANGFUSE_PUBLIC_KEY") or ""
        if not sk:
            sk = os.environ.get("LANGFUSE_SECRET_KEY") or env_dict.get("LANGFUSE_SECRET_KEY") or ""

        # 3. Command line flag overrides (highest precedence)
        if host_override:
            host = host_override
        if pk_override:
            pk = pk_override
        if sk_override:
            sk = sk_override

        # Default host fallback if empty
        if not host:
            host = "https://cloud.langfuse.com"

        return ProfileConfig(
            name=target_name,
            host=host.rstrip("/"),
            public_key=pk,
            secret_key=sk,
        )

    @staticmethod
    def _parse_dotenv(path: str) -> Dict[str, str]:
        res = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    res[k] = v
        except Exception:
            pass
        return res
