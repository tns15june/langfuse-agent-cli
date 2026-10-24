from pathlib import Path
from unittest.mock import patch
from langfuse_cli.commands.skills import handle_skills, TARGET_PLATFORMS
import argparse


def test_skills_install_to_mock_dirs(tmp_path: Path):
    mock_claude = tmp_path / "claude_skills"
    mock_agents = tmp_path / "agents_skills"

    mock_platforms = [
        ("Claude Code", mock_claude),
        ("Universal Agents", mock_agents),
    ]

    with patch("langfuse_cli.commands.skills.TARGET_PLATFORMS", mock_platforms):
        args = argparse.Namespace(skills_action="install", target="all", symlink=False)
        rc = handle_skills(args)
        assert rc == 0

        # Verify skills exist
        assert (mock_claude / "langfuse" / "SKILL.md").exists()
        assert (mock_claude / "langfuse-prompts" / "SKILL.md").exists()
        assert (mock_claude / "langfuse-traces" / "SKILL.md").exists()

        assert (mock_agents / "langfuse" / "SKILL.md").exists()
