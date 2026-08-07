"""Deterministic, duplicate-safe loading helpers for repository records."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import yaml


class DuplicateKeyError(ValueError):
    """Raised when YAML contains a duplicate mapping key."""


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects ambiguous duplicate keys."""


# PyYAML defaults to YAML 1.1 and treats keys such as `on` as booleans. Repository
# records and GitHub Actions use YAML 1.2 semantics, where only true/false are booleans.
UniqueKeyLoader.yaml_implicit_resolvers = {
    key: [(tag, resolver) for tag, resolver in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_yaml_12_boolean = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
for _first_character in "tTfF":
    UniqueKeyLoader.yaml_implicit_resolvers.setdefault(_first_character, []).append(
        ("tag:yaml.org,2002:bool", _yaml_12_boolean)
    )


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def discover_repo_root(start: Path | None = None) -> Path:
    """Find the repository from explicit project markers, independent of install mode."""

    candidates = (start or Path.cwd(), Path(__file__).resolve())
    for candidate in candidates:
        directory = candidate if candidate.is_dir() else candidate.parent
        for parent in (directory, *directory.parents):
            if (parent / "pyproject.toml").is_file() and (
                parent / "docs/PROJECT_STATE.yaml"
            ).is_file():
                return parent
    raise RuntimeError("cannot locate GIC Lab repository root from project markers")


def load_yaml(path: Path) -> dict[str, Any]:
    """Load one YAML mapping while rejecting duplicate keys."""

    with path.open(encoding="utf-8") as handle:
        value = yaml.load(handle, Loader=UniqueKeyLoader)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a top-level mapping")
    return cast(dict[str, Any], value)


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON mapping."""

    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a top-level object")
    return cast(dict[str, Any], value)


def resolve_repo_path(root: Path, relative: str) -> Path:
    """Resolve a repository-relative path and reject traversal outside the root."""

    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"path escapes repository root: {relative}")
    return candidate
