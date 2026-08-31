from __future__ import annotations

from pathlib import Path

from giclab.control.version_lint import lint_source, validate_active_version_dispatch

ROOT = Path(__file__).resolve().parents[2]


def _codes(source: str) -> set[str]:
    return {item.code for item in lint_source(source, relative_path="src/giclab/example.py")}


def test_literal_active_version_set_fails() -> None:
    assert _codes('if contract.version in {"V14", "V15", "V16"}:\n    use()\n') == {"T09V001"}


def test_chained_equality_dispatch_fails() -> None:
    source = 'if version == "V14" or version == "V15":\n    use()\n'
    assert _codes(source) == {"T09V001"}


def test_supported_versions_helper_fails() -> None:
    source = '_SUPPORTED_VERSIONS = frozenset({"V14", "V15"})\n'
    assert _codes(source) == {"T09V003"}


def test_ordered_version_dispatch_fails() -> None:
    assert _codes('if version >= "V12":\n    use()\n') == {"T09V002"}


def test_historical_identity_assertion_passes() -> None:
    assert _codes('assert historical_record["version"] == "V14"\n') == set()


def test_generated_identity_formatting_passes() -> None:
    assert _codes('identifier = f"pilot-{contract.version.lower()}"\n') == set()


def test_central_registry_declarations_pass() -> None:
    source = 'V16 = _contract(version="V16")\nREGISTRY = {V16.version: V16}\n'
    assert _codes(source) == set()


def test_line_annotation_allows_exact_historical_adjudication() -> None:
    source = 'if contract.version == "V9":  # giclab-version-lint: historical-identity\n    use()\n'
    assert _codes(source) == set()


def test_actual_repository_has_zero_prohibited_active_dispatches() -> None:
    receipt = validate_active_version_dispatch(ROOT)
    assert receipt["complete"] is True
    assert receipt["findings"] == []
