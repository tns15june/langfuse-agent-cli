"""Configuration and profile management for Langfuse CLI."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "langfuse"
DEFAULT_PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ConfigError(Exception):
    """Credentials or the profiles file cannot be used as given."""


@dataclass
class ProfileConfig:
    name: str
    host: str
    public_key: str
    secret_key: str
    source: str = ""  # where host and keys came from: "profile", "env" or "env-file"

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

    def _load_raw(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        data: Any = {}
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except ValueError as e:
                # Refuse to continue: the next save would silently drop every saved profile.
                raise ConfigError(f"{self.config_path} is not valid JSON; fix or delete it") from e
            if not isinstance(data, dict):
                raise ConfigError(f"{self.config_path} is not a profiles file; fix or delete it")
        data.setdefault("current_profile", "default")
        data.setdefault("profiles", {})
        self._cache = data
        return data

    def _save_raw(self, data: Dict[str, Any]) -> None:
        # The file holds secret keys: create directory and file private from the start, then swap it in.
        self.config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.config_path.parent, prefix=".profiles-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.config_path)
        except BaseException:
            os.unlink(tmp)
            raise
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
                source="profile",
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
        """Take host and keys from one source, then apply explicit flag overrides.

        Sources, first match wins: --env-file, --profile / LANGFUSE_PROFILE, LANGFUSE_* environment
        variables, the saved current profile. Sources are never mixed, so a host found in one place
        (a cloned repo's .env, say) cannot receive keys that came from another.
        """
        explicit = name or os.environ.get("LANGFUSE_PROFILE")
        if env_file:
            base = self._from_vars(self._parse_dotenv(env_file), "env-file")
        elif explicit:
            base = self.list_profiles().get(explicit)
            if base is None:
                raise ConfigError(f"profile '{explicit}' not found; see 'lf auth list'")
        elif os.environ.get("LANGFUSE_PUBLIC_KEY") or os.environ.get("LANGFUSE_SECRET_KEY"):
            base = self._from_vars(os.environ, "env")
        else:
            current = self.get_current_profile_name()
            base = self.list_profiles().get(current) or ProfileConfig(current, "", "", "", "profile")

        return ProfileConfig(
            name=base.name,
            host=(host_override or base.host or "https://cloud.langfuse.com").rstrip("/"),
            public_key=pk_override or base.public_key,
            secret_key=sk_override or base.secret_key,
            source=base.source,
        )

    @staticmethod
    def _from_vars(values: Any, source: str) -> ProfileConfig:
        return ProfileConfig(
            name="",
            host=values.get("LANGFUSE_BASE_URL") or values.get("LANGFUSE_HOST") or "",
            public_key=values.get("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=values.get("LANGFUSE_SECRET_KEY", ""),
            source=source,
        )

    @staticmethod
    def _parse_dotenv(path: str) -> Dict[str, str]:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as e:
            raise ConfigError(f"cannot read env file {path}: {e}") from e
        res = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            res[k.strip()] = v.strip().strip("'\"")
        return res


def resolve_from_args(args: argparse.Namespace) -> ProfileConfig:
    """Credentials for one command, from its parsed common options."""
    return ConfigManager().resolve_profile(args.profile, args.host, args.public_key, args.secret_key, args.env_file)
