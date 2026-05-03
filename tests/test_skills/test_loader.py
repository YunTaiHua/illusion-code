"""Tests for skill loading."""

from __future__ import annotations

from pathlib import Path

from illusion.skills import get_user_skills_dir, load_skill_registry
from illusion.skills.loader import get_project_skills_dir, load_project_skills


def test_load_skill_registry_includes_bundled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    registry = load_skill_registry()

    names = [skill.name for skill in registry.list_skills()]
    assert "simplify" in names
    assert "review" in names


def test_load_skill_registry_includes_user_skills(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    skills_dir = get_user_skills_dir()
    (skills_dir / "deploy.md").write_text("# Deploy\nDeployment workflow guidance\n", encoding="utf-8")

    registry = load_skill_registry()
    deploy = registry.get("Deploy")

    assert deploy is not None
    assert deploy.source == "user"
    assert "Deployment workflow guidance" in deploy.content


def test_load_project_skills_from_subdirectory(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # 创建项目级 skill 子目录结构: .illusion/skills/deploy/deploy.md
    skills_dir = get_project_skills_dir(project_dir)
    skill_subdir = skills_dir / "deploy"
    skill_subdir.mkdir()
    (skill_subdir / "deploy.md").write_text(
        "---\nname: deploy\ndescription: Project deploy skill\n---\n\n# Deploy\n\nDeploy steps.\n",
        encoding="utf-8",
    )

    skills = load_project_skills(project_dir)
    assert len(skills) == 1
    assert skills[0].name == "deploy"
    assert skills[0].source == "project"


def test_load_skill_registry_includes_project_skills(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    skills_dir = get_project_skills_dir(project_dir)
    skill_subdir = skills_dir / "my-skill"
    skill_subdir.mkdir()
    (skill_subdir / "my-skill.md").write_text(
        "---\nname: my-skill\ndescription: A project skill\n---\n\n# My Skill\n\nContent.\n",
        encoding="utf-8",
    )

    registry = load_skill_registry(project_dir)
    skill = registry.get("my-skill")

    assert skill is not None
    assert skill.source == "project"


def test_project_skill_overrides_global_skill(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # 创建全局 skill
    user_skills_dir = get_user_skills_dir()
    (user_skills_dir / "deploy.md").write_text(
        "# Deploy\nGlobal deploy skill.\n",
        encoding="utf-8",
    )

    # 创建同名项目级 skill（子目录结构）
    skills_dir = get_project_skills_dir(project_dir)
    skill_subdir = skills_dir / "deploy"
    skill_subdir.mkdir()
    (skill_subdir / "deploy.md").write_text(
        "---\nname: deploy\ndescription: Project deploy skill\n---\n\n# Deploy\n\nProject deploy.\n",
        encoding="utf-8",
    )

    registry = load_skill_registry(project_dir)
    skill = registry.get("deploy")

    assert skill is not None
    assert skill.source == "project"
    assert "Project deploy" in skill.content
