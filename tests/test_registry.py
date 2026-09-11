from __future__ import annotations

from pathlib import Path

import pytest
from referencing.exceptions import NoSuchResource

from giclab.registry import (
    DuplicateKeyError,
    discover_repo_root,
    load_json,
    load_yaml,
    loads_json,
    local_schema_registry,
    resolve_repo_path,
)

ROOT = Path(__file__).resolve().parents[1]


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("key: one\nkey: two\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError):
        load_yaml(path)


def test_duplicate_json_keys_are_rejected_recursively(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"authorization": {"authorized": false, "authorized": true}}\n')
    with pytest.raises(DuplicateKeyError, match="authorized"):
        load_json(path)
    with pytest.raises(DuplicateKeyError, match="budget"):
        loads_json('{"budget": 1, "budget": 2}')


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_numbers_are_rejected(constant: str) -> None:
    with pytest.raises(ValueError, match="non-finite JSON value"):
        loads_json(f'{{"value": {constant}}}')


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


def test_local_schema_registry_requires_exact_files_for_ambiguous_historical_ids() -> None:
    registry = local_schema_registry(ROOT / "schemas")
    with pytest.raises(NoSuchResource):
        registry.contents("urn:gic-lab:schema:t09-sira-pilot-execution:0.5.0")
    for version in ("v10", "v16"):
        path = ROOT / f"schemas/t09-sira-pilot-{version}-execution.schema.json"
        assert registry.contents(path.resolve().as_uri())["title"].startswith(
            f"T09 {version.upper()}"
        )
