import os
import stat
from pathlib import Path

import pytest

from langfuse_cli.config import ConfigError, ConfigManager


def test_config_profiles(tmp_path: Path):
    cfg_file = tmp_path / "profiles.json"
    mgr = ConfigManager(cfg_file)

    # Save profile
    mgr.save_profile("test-local", "http://localhost:3000", "pk-lf-12345678", "sk-lf-87654321")

    profiles = mgr.list_profiles()
    assert "test-local" in profiles
    p = profiles["test-local"]
    assert p.host == "http://localhost:3000"
    assert p.is_complete() is True
    assert p.masked_public_key() == "pk-lf-...5678"
    assert p.masked_secret_key() == "sk-lf-...4321"


def test_resolve_profile_override(tmp_path: Path):
    cfg_file = tmp_path / "profiles.json"
    mgr = ConfigManager(cfg_file)
    mgr.save_profile("cloud", "https://cloud.langfuse.com", "pk-1", "sk-1")

    resolved = mgr.resolve_profile(name="cloud", host_override="http://override:3000")
    assert resolved.host == "http://override:3000"
    assert resolved.public_key == "pk-1"


@pytest.fixture
def saved_cloud(tmp_path):
    mgr = ConfigManager(tmp_path / "p.json")
    mgr.save_profile("cloud", "https://eu.example.test", "pk-1", "sk-1")
    return mgr


def set_env_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-env")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-env")


def test_env_vars_beat_saved_current_profile(saved_cloud, monkeypatch):
    set_env_keys(monkeypatch)
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://env.test")

    p = saved_cloud.resolve_profile()

    assert (p.host, p.public_key, p.secret_key, p.source) == ("http://env.test", "pk-env", "sk-env", "env")


def test_env_langfuse_host_used_when_base_url_missing(saved_cloud, monkeypatch):
    set_env_keys(monkeypatch)
    monkeypatch.setenv("LANGFUSE_HOST", "http://legacy.test")

    assert saved_cloud.resolve_profile().host == "http://legacy.test"


def test_explicit_profile_beats_env(saved_cloud, monkeypatch):
    set_env_keys(monkeypatch)

    p = saved_cloud.resolve_profile(name="cloud")

    assert (p.host, p.public_key, p.source) == ("https://eu.example.test", "pk-1", "profile")


def test_unknown_explicit_profile_raises(saved_cloud):
    with pytest.raises(ConfigError, match="prod"):
        saved_cloud.resolve_profile(name="prod")


def test_env_source_never_takes_host_from_profile(saved_cloud, monkeypatch):
    set_env_keys(monkeypatch)  # keys from env, host only in the saved profile

    assert saved_cloud.resolve_profile().host == "https://cloud.langfuse.com"


def test_cwd_dotenv_cannot_redirect_exported_keys(monkeypatch, tmp_path):
    # A cloned repo plants only a host in ./.env; the user's real keys are exported in the shell.
    (tmp_path / ".env").write_text("LANGFUSE_HOST=http://evil.test\n")  # tmp_path is the cwd (conftest)
    set_env_keys(monkeypatch)

    p = ConfigManager(tmp_path / "none.json").resolve_profile()

    assert (p.host, p.public_key) == ("https://cloud.langfuse.com", "pk-env")


def test_env_file_is_used_when_given(saved_cloud, monkeypatch, tmp_path):
    env_file = tmp_path / "creds.env"
    env_file.write_text('LANGFUSE_PUBLIC_KEY=pk-file\nLANGFUSE_SECRET_KEY="sk-file"\nLANGFUSE_HOST=http://file.test\n')
    set_env_keys(monkeypatch)

    p = saved_cloud.resolve_profile(env_file=str(env_file))

    assert (p.host, p.public_key, p.secret_key, p.source) == ("http://file.test", "pk-file", "sk-file", "env-file")


def test_missing_env_file_raises(saved_cloud, tmp_path):
    with pytest.raises(ConfigError):
        saved_cloud.resolve_profile(env_file=str(tmp_path / "nope.env"))


def test_corrupt_profiles_file_raises(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json")

    with pytest.raises(ConfigError, match="not valid JSON"):
        ConfigManager(path).list_profiles()


def test_profiles_file_is_private_even_if_chmod_fails(tmp_path, monkeypatch):
    def failing_chmod(*args, **kwargs):
        raise OSError("chmod not supported")

    monkeypatch.setattr(os, "chmod", failing_chmod)
    old_umask = os.umask(0)  # most permissive umask: anything not created private ends up world-readable
    try:
        path = tmp_path / "newdir" / "profiles.json"
        ConfigManager(path).save_profile("x", "http://h", "pk", "sk")
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
