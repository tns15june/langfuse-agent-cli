"""Shared test helpers: recorded Langfuse responses, a fake terminal and an installed skill."""
import io
import json
from pathlib import Path

from langfuse_cli import __version__, install_info

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


class TTY(io.StringIO):
    """stdin that claims to be a terminal."""

    def isatty(self):
        return True


def install_skill(ref=f"v{__version__}", lock_path=None):
    """What `npx skills add ... -g` leaves behind: the shared skill folder and its entry in the global lock."""
    skill = install_info.AGENTS_DIR / "skills" / install_info.SKILL_NAME
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("---\nname: langfuse-agent-cli\n---\n")
    lock = {"version": 3, "skills": {install_info.SKILL_NAME: {"source": "tns15june/langfuse-agent-cli", "ref": ref}}}
    lock_path = lock_path or install_info.AGENTS_DIR / ".skill-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock))
    return skill


def link_skill(agent_skills_dir):
    """The per-agent link `npx skills add -g` creates, pointing at the shared copy."""
    agent_skills_dir.mkdir(parents=True, exist_ok=True)
    link = agent_skills_dir / install_info.SKILL_NAME
    link.symlink_to(install_info.AGENTS_DIR / "skills" / install_info.SKILL_NAME)
    return link
