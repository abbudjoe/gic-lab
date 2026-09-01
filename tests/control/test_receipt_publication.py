from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from giclab.control import cli
from giclab.control.target import SelectedRuntimeTarget, resolve_selected_runtime_target

ROOT = Path(__file__).resolve().parents[2]


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()


def _fixture_generator(*, fail_after_child: int | None = None) -> Callable[..., dict[str, object]]:
    def generate(
        _repository: Path,
        output: Path,
        *,
        target: SelectedRuntimeTarget,
        commit: str,
        tree: str,
    ) -> dict[str, object]:
        del target
        output.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, str] = {}
        for index in range(1, 7):
            path = output / f"artifact-{index}.json"
            encoded = _json_bytes({"artifact": index})
            path.write_bytes(encoded)
            artifacts[path.name] = hashlib.sha256(encoded).hexdigest()
            if fail_after_child == index:
                raise OSError(f"injected preparation failure after child {index}")
        binding = output / "t09-control-receipt-bindings.json"
        encoded_binding = _json_bytes({"artifacts": artifacts, "sealed": True})
        binding.write_bytes(encoded_binding)
        return {
            "schema_version": "test-only",
            "control_commit": commit,
            "control_tree": tree,
            "binding_file_sha256": hashlib.sha256(encoded_binding).hexdigest(),
            "complete": True,
            "semantic_sha256": "0" * 64,
        }

    return generate


def _assert_fixture_complete(output: Path) -> None:
    binding = json.loads((output / "t09-control-receipt-bindings.json").read_bytes())
    assert binding["sealed"] is True
    assert binding["artifacts"] == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.glob("artifact-*.json"))
    }
    assert len(binding["artifacts"]) == 6


def _arguments(repository: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repository=repository,
        output_root=Path("control/receipts/packages/v16"),
        provider_contract=None,
    )


def _install_fast_publication(
    monkeypatch: pytest.MonkeyPatch,
    *,
    generator: Callable[..., dict[str, object]] | None = None,
) -> None:
    target = resolve_selected_runtime_target(ROOT)
    monkeypatch.setattr(cli, "_target_from_args", lambda _args: target)
    monkeypatch.setattr(cli, "_clean_git_identity", lambda _repository: ("a" * 40, "b" * 40))
    monkeypatch.setattr(cli, "_generate_receipt_tree", generator or _fixture_generator())
    monkeypatch.setattr(
        cli,
        "validate_current_control_receipt_set",
        lambda *_args, **_kwargs: object(),
    )


@pytest.mark.parametrize(
    "failure_point",
    (
        "before-final-publication",
        "after-first-generated-child",
        "halfway-through-preparation",
        "immediately-before-commit",
        "immediately-after-commit",
        "during-post-publication-validation",
    ),
)
def test_publication_interruption_never_exposes_a_partial_final_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    real_effect_counts = {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_calls": 0,
        "condition_reservations": 0,
    }
    fail_after = {
        "after-first-generated-child": 1,
        "halfway-through-preparation": 3,
    }.get(failure_point)
    _install_fast_publication(
        monkeypatch,
        generator=_fixture_generator(fail_after_child=fail_after),
    )
    original_publish = cli._publish_receipt_tree
    if failure_point == "before-final-publication":
        monkeypatch.setattr(
            cli,
            "_publish_receipt_tree",
            lambda _staging, _output: (_ for _ in ()).throw(OSError("injected before publication")),
        )
    elif failure_point == "immediately-before-commit":
        monkeypatch.setattr(
            cli,
            "_commit_path_no_replace",
            lambda _source, _destination: (_ for _ in ()).throw(OSError("injected before commit")),
        )
    elif failure_point == "immediately-after-commit":

        def publish_then_fail(staging: Path, output: Path) -> None:
            original_publish(staging, output)
            raise OSError("injected after commit")

        monkeypatch.setattr(cli, "_publish_receipt_tree", publish_then_fail)
    elif failure_point == "during-post-publication-validation":
        monkeypatch.setattr(
            cli,
            "validate_current_control_receipt_set",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("injected post-publication validation failure")
            ),
        )

    output = tmp_path / "control/receipts/packages/v16"
    with pytest.raises(OSError, match="injected"):
        cli._command_refresh_receipts(_arguments(tmp_path))
    if output.exists():
        _assert_fixture_complete(output)
    else:
        assert not output.exists()
    assert not list(output.parent.glob(".v16-receipt-staging-*"))
    assert real_effect_counts == {
        "secret_reads": 0,
        "metadata_requests": 0,
        "provider_calls": 0,
        "condition_reservations": 0,
    }


def test_concurrent_complete_tree_winner_is_accepted_without_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_publication(monkeypatch)
    original_commit = cli._commit_path_no_replace
    injected = False

    def concurrent_commit(source: Path, destination: Path) -> None:
        nonlocal injected
        if not injected:
            injected = True
            competitor = source.parent / ".competitor-complete"
            shutil.copytree(source, competitor)
            original_commit(competitor, destination)
            raise FileExistsError(destination)
        original_commit(source, destination)

    monkeypatch.setattr(cli, "_commit_path_no_replace", concurrent_commit)
    result, complete = cli._command_refresh_receipts(_arguments(tmp_path))
    assert complete is True
    assert result["complete"] is True
    _assert_fixture_complete(tmp_path / "control/receipts/packages/v16")


def test_concurrent_partial_final_path_is_quarantined_before_atomic_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_publication(monkeypatch)
    original_commit = cli._commit_path_no_replace
    injected = False

    def concurrent_commit(source: Path, destination: Path) -> None:
        nonlocal injected
        if not injected:
            injected = True
            destination.mkdir()
            (destination / "partial.json").write_text("{}\n", encoding="utf-8")
            raise FileExistsError(destination)
        original_commit(source, destination)

    monkeypatch.setattr(cli, "_commit_path_no_replace", concurrent_commit)
    result, complete = cli._command_refresh_receipts(_arguments(tmp_path))
    assert complete is True
    recovery = tmp_path / str(result["recovered_unsealed_root"])
    assert recovery.name == ".v16-unowned-partial-recovery"
    assert (recovery / "partial.json").is_file()
    _assert_fixture_complete(tmp_path / "control/receipts/packages/v16")


def test_existing_sealed_root_is_immutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_publication(monkeypatch)
    output = tmp_path / "control/receipts/packages/v16"
    _fixture_generator()(
        tmp_path,
        output,
        target=resolve_selected_runtime_target(ROOT),
        commit="a" * 40,
        tree="b" * 40,
    )
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(ValueError, match="sealed"):
        cli._command_refresh_receipts(_arguments(tmp_path))
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before


def test_existing_unowned_partial_root_is_quarantined_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_publication(monkeypatch)
    output = tmp_path / "control/receipts/packages/v16"
    output.mkdir(parents=True)
    (output / "partial.json").write_text("{}\n", encoding="utf-8")
    result, complete = cli._command_refresh_receipts(_arguments(tmp_path))
    assert complete is True
    recovery = tmp_path / str(result["recovered_unsealed_root"])
    assert recovery.name == ".v16-unowned-partial-recovery"
    assert (recovery / "partial.json").is_file()
    _assert_fixture_complete(output)


def test_two_atomic_complete_tree_publications_are_byte_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fast_publication(monkeypatch)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    cli._command_refresh_receipts(_arguments(first))
    cli._command_refresh_receipts(_arguments(second))
    first_root = first / "control/receipts/packages/v16"
    second_root = second / "control/receipts/packages/v16"
    assert {
        path.relative_to(first_root): path.read_bytes()
        for path in first_root.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(second_root): path.read_bytes()
        for path in second_root.rglob("*")
        if path.is_file()
    }
