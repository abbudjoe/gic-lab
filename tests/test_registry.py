from __future__ import annotations

from pathlib import Path

import pytest

from giclab.registry import (
    DuplicateKeyError,
    discover_repo_root,
    load_yaml,
    resolve_repo_path,
)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("key: one\nkey: two\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError):
        load_yaml(path)


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes repository"):
        resolve_repo_path(tmp_path, "../outside")


def test_repo_root_is_discovered_from_nested_project_markers(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/PROJECT_STATE.yaml").write_text("phase: test\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    nested = tmp_path / "a/b/c"
    nested.mkdir(parents=True)
    assert discover_repo_root(nested) == tmp_path
