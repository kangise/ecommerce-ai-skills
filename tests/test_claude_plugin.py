"""Claude Code plugin marketplace.

The repository is a plugin marketplace (.claude-plugin/marketplace.json) whose
one plugin is dist/, the artifact the gates verify. These tests pin the parts
that can drift without anyone noticing: the version, the skill metadata Claude
Code reads, and the packaging of the manifest itself.
"""

from __future__ import annotations

import glob
import json
import os
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
DIST = ROOT / "dist"
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _marketplace() -> dict:
    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))


def _plugin_root() -> Path:
    (entry,) = _marketplace()["plugins"]
    return (ROOT / entry["source"]).resolve()


def _plugin() -> dict:
    return json.loads((_plugin_root() / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def test_marketplace_points_at_the_verified_artifact() -> None:
    market = _marketplace()
    assert KEBAB.match(market["name"])
    (entry,) = market["plugins"]
    assert KEBAB.match(entry["name"])
    assert _plugin_root() == DIST.resolve(), "the plugin must be dist/, not a hand-kept copy"
    assert entry["name"] == _plugin()["name"]


def test_plugin_version_follows_pyproject() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert _plugin()["version"] == version


def test_plugin_description_numbers_match_the_package() -> None:
    counts = json.loads((DIST / "package-manifest.json").read_text(encoding="utf-8"))["counts"]
    description = _plugin()["description"]
    for key in ("skills", "constraints", "prompts"):
        assert re.search(rf"\b{counts[key]}\b", description), (key, counts[key], description)


def test_every_skill_is_loadable_by_claude_code() -> None:
    """Claude Code reads name and description from SKILL.md frontmatter; the
    description (plus when_to_use) is capped at 1,536 characters."""
    skills_dir = _plugin_root() / _plugin()["skills"]
    skill_dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir())
    assert len(skill_dirs) == json.loads((DIST / "package-manifest.json").read_text())["counts"]["skills"]
    for skill in skill_dirs:
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        assert match, f"{skill.name}: no frontmatter"
        fields = dict(re.findall(r"^([a-z_-]+):\s*(.*)$", match.group(1), re.M))
        assert fields.get("name") == skill.name, skill.name
        assert KEBAB.match(skill.name) and not skill.name.startswith("synced"), skill.name
        described = " ".join((fields.get("description", "") + " " + fields.get("when_to_use", "")).split())
        assert 0 < len(described) <= 1536, (skill.name, len(described))


def test_every_manifest_file_is_packaged_into_the_wheel() -> None:
    """setuptools' package-data globs do not match dot-directories.

    dist/.claude-plugin/plugin.json is listed in package-manifest.json; without
    an explicit pattern the wheel omitted it and the installed MCP server
    refused to start ("package file missing: .claude-plugin/plugin.json").
    This replays setuptools' matching (glob, recursive, hidden files excluded)
    against the configured patterns.
    """
    package = ROOT / "ecommerce_ai_skills"
    patterns = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"]["setuptools"]["package-data"]["ecommerce_ai_skills"]
    packaged = set()
    for pattern in patterns:
        for match in glob.glob(os.path.join(str(package), pattern), recursive=True):
            if os.path.isfile(match):
                packaged.add(Path(match).resolve())
    manifest = json.loads((package / "package_data" / "dist" / "package-manifest.json").read_text())
    missing = sorted(
        rel for rel in manifest["sha256"]
        if (package / "package_data" / "dist" / rel).resolve() not in packaged
    )
    assert not missing, f"listed in package-manifest.json but not packaged: {missing}"
