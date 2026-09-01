from __future__ import annotations

import json
from pathlib import Path

import pytest

from giclab.control.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[2]


def test_stable_control_subcommands_are_registered() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    for command in (
        "state-capsule",
        "registry-check",
        "version-lint",
        "compose",
        "shadow",
        "incident-check",
        "agent-check",
        "refresh-receipts",
    ):
        assert command in help_text


def test_version_lint_cli_emits_json_and_writes_identical_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "version-lint.json"
    assert (
        main(
            [
                "version-lint",
                "--repository",
                str(ROOT),
                "--output-file",
                str(output),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    stdout_document = json.loads(captured.out)
    assert stdout_document["complete"] is True
    assert json.loads(output.read_text(encoding="utf-8")) == stdout_document


def test_shadow_cli_writes_only_shadow_receipts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "shadow"
    assert (
        main(
            [
                "shadow",
                "--repository",
                str(ROOT),
                "--provider-contract",
                "V16",
                "--scenario",
                "happy-path",
                "--fixed-tick",
                "7",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    aggregate = json.loads(captured.out)
    assert aggregate["complete"] is True
    paths = sorted(path.name for path in output.iterdir())
    assert paths == ["happy-path.json"]
    receipt = json.loads((output / "happy-path.json").read_text(encoding="utf-8"))
    assert receipt["shadow_only"] is True
    assert receipt["scientific_interpretation_allowed"] is False
