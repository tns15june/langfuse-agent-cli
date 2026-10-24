from pathlib import Path
from langfuse_cli.config import ConfigManager, ProfileConfig


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
