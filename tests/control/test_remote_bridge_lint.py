from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from giclab.control.anti_shadow_lint import BRIDGE_LIVE_SOURCES, bridge_bypass_findings

ROOT = Path(__file__).resolve().parents[2]


def _bridge_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    for relative in BRIDGE_LIVE_SOURCES:
        source = ROOT / relative
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return repository


def _rewrite(path: Path, before: str, after: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")


@pytest.mark.parametrize(
    ("relative", "before", "after", "code"),
    [
        (
            "src/giclab/control/effects.py",
            "    def provider_entry(self, handle: ProviderHandle) -> None: ...",
            "    def provider_launch(self, *, launch_ordinal: int) -> ProviderHandle: ...\n\n"
            "    def provider_entry(self, handle: ProviderHandle) -> None: ...",
            "T09S033",
        ),
        (
            "src/giclab/control/production.py",
            '"uploaded": False',
            '"uploaded": True',
            "T09S031",
        ),
        (
            "src/giclab/control/production.py",
            "validated_manifest = validate_full_dynamic_frozen_manifest(",
            "validated_manifest = accept_minimal_frozen_manifest(",
            "T09S032",
        ),
        (
            "src/giclab/control/remote_bridge.py",
            "    sequence_number: int\n",
            "",
            "T09S034",
        ),
        (
            "src/giclab/control/remote_bridge.py",
            "self.observer.model_call(\n                event,",
            "self.observer.replay_model_call(\n                event,",
            "T09S029",
        ),
        (
            "src/giclab/harness/sira_gate_a_runtime.py",
            "admission_port.model_call(",
            "admission_port.model_call_bypassed(",
            "T09S029",
        ),
        (
            "containers/sira-smoke/pragmatic/t09_remote_runner.py",
            "condition_bridge=bridge",
            "condition_bridge=None",
            "T09S035",
        ),
    ],
)
def test_bridge_anti_bypass_lint_rejects_mutation(
    tmp_path: Path,
    relative: str,
    before: str,
    after: str,
    code: str,
) -> None:
    repository = _bridge_repository(tmp_path)
    assert bridge_bypass_findings(repository) == ()
    _rewrite(repository / relative, before, after)
    assert code in {finding.code for finding in bridge_bypass_findings(repository)}


def test_bridge_anti_bypass_lint_rejects_second_accountant_and_hidden_retry(
    tmp_path: Path,
) -> None:
    repository = _bridge_repository(tmp_path)
    admission = repository / "src/giclab/harness/t09_runtime_admission.py"
    _rewrite(
        admission,
        'class DuplexSupervisorPort:\n    """Remote event client',
        "class DuplexSupervisorPort:\n"
        "    forbidden_boundary = ProviderBudgetBoundary()\n\n"
        '    """Remote event client',
    )
    assert "T09S030" in {finding.code for finding in bridge_bypass_findings(repository)}

    # Restore the exact source, then place an effect round trip under a loop.
    shutil.copy2(ROOT / admission.relative_to(repository), admission)
    source = admission.read_text(encoding="utf-8")
    marker = "class DuplexSupervisorPort:"
    prefix, suffix = source.split(marker, 1)
    before = "        self._write_event(\n            event_id=reserve_id,"
    after = (
        "        for _retry in range(2):\n"
        '            self._read_event({"model-call-admitted"})\n'
        "        self._write_event(\n"
        "            event_id=reserve_id,"
    )
    assert before in suffix
    admission.write_text(prefix + marker + suffix.replace(before, after, 1), encoding="utf-8")
    assert "T09S036" in {finding.code for finding in bridge_bypass_findings(repository)}
