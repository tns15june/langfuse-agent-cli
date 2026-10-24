"""Agent Skills installer and manager for Langfuse companion skills."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

TARGET_PLATFORMS: List[Tuple[str, Path]] = [
    ("Claude Code", Path.home() / ".claude" / "skills"),
    ("Antigravity", Path.home() / ".gemini" / "config" / "skills"),
    ("Universal Agents", Path.home() / ".agents" / "skills"),
    ("Cursor", Path.home() / ".cursor" / "skills"),
    ("OpenCode", Path.home() / ".config" / "opencode" / "skills"),
]


def get_source_skills_dir() -> Path:
    # 1. Package directory
    pkg_skills = Path(__file__).resolve().parent.parent.parent / "skills"
    if pkg_skills.exists():
        return pkg_skills
    # 2. Bundled inside package
    bundled = Path(__file__).resolve().parent.parent / "skills"
    if bundled.exists():
        return bundled
    raise FileNotFoundError("Could not locate source skills directory.")


def handle_skills(args: argparse.Namespace) -> int:
    action = getattr(args, "skills_action", "list")
    try:
        src_dir = get_source_skills_dir()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    available_skills = [d.name for d in src_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

    if action == "list":
        print(f"Available Companion Skills ({len(available_skills)}):")
        for s in sorted(available_skills):
            desc = ""
            skill_md = src_dir / s / "SKILL.md"
            if skill_md.exists():
                for line in skill_md.read_text(encoding="utf-8").splitlines():
                    if line.startswith("description:"):
                        desc = " — " + line.replace("description:", "").strip().strip(">'\"")
                        break
            print(f"  • {s}{desc}")

        print("\nTarget Ecosystem Status:")
        for name, target_path in TARGET_PLATFORMS:
            installed = []
            if target_path.exists():
                for s in available_skills:
                    if (target_path / s).exists():
                        installed.append(s)
            if installed:
                print(f"  ✓ {name:<18} [{', '.join(installed)}] in {target_path}")
            else:
                print(f"  – {name:<18} (not installed in {target_path})")
        return 0

    elif action == "install":
        selected_target = getattr(args, "target", "all").lower()
        use_symlinks = getattr(args, "symlink", False)
        installed_count = 0

        for name, target_path in TARGET_PLATFORMS:
            # Check target filter
            if selected_target != "all":
                normalized_name = name.lower().replace(" ", "")
                if selected_target not in normalized_name:
                    continue

            target_path.mkdir(parents=True, exist_ok=True)
            for skill_name in available_skills:
                skill_src = src_dir / skill_name
                skill_dest = target_path / skill_name

                if skill_dest.exists():
                    if skill_dest.is_symlink() or skill_dest.is_file():
                        skill_dest.unlink()
                    else:
                        shutil.rmtree(skill_dest)

                if use_symlinks:
                    try:
                        os.symlink(skill_src, skill_dest)
                        print(f"  ✓ Linked {skill_name} -> {skill_dest}")
                        installed_count += 1
                        continue
                    except OSError:
                        pass

                # Fallback: copy tree
                shutil.copytree(skill_src, skill_dest)
                print(f"  ✓ Copied {skill_name} -> {skill_dest}")
                installed_count += 1

        print(f"\n✓ Completed installation ({installed_count} skill targets deployed).")
        return 0

    return 0
