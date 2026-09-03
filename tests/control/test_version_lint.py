from __future__ import annotations

from pathlib import Path

from giclab.control.version_lint import (
    lint_active_selection_text,
    lint_source,
    validate_active_version_dispatch,
)

ROOT = Path(__file__).resolve().parents[2]


def _codes(source: str) -> set[str]:
    return {
        item.code
        for item in lint_source(
            source,
            relative_path="src/giclab/control/example.py",
        )
    }


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


def test_literal_package_receipt_root_fails() -> None:
    assert _codes('root = "control/receipts/packages/v17"\n') == {"T09V009"}


def test_central_registry_declarations_pass() -> None:
    source = (
        'V16_PROVIDER_CONTRACT = _contract(version="V16")\n'
        "REGISTRY = {V16_PROVIDER_CONTRACT.version: V16_PROVIDER_CONTRACT}\n"
    )
    findings = lint_source(
        source,
        relative_path="src/giclab/harness/t09_provider_contracts.py",
    )
    assert findings == ()


def test_line_annotation_allows_exact_historical_adjudication() -> None:
    source = 'if contract.version == "V9":  # giclab-version-lint: historical-identity\n    use()\n'
    assert _codes(source) == set()


def test_literal_provider_contract_call_fails_even_with_historical_annotation() -> None:
    source = 'contract = provider_contract("V16")  # giclab-version-lint: historical-identity\n'
    assert _codes(source) == {"T09V004"}


def test_literal_provider_contract_keyword_call_fails() -> None:
    assert _codes('contract = provider_contract(version="V16")\n') == {"T09V004"}


def test_historical_module_cannot_resolve_literal_active_selector() -> None:
    findings = lint_source(
        'contract = provider_contract("V16")\n',
        relative_path="src/giclab/validation.py",
    )
    assert {finding.code for finding in findings} == {"T09V004"}


def test_old_agent_check_direct_import_and_assignment_form_fails() -> None:
    source = (
        "from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT\n"
        "target = V16_PROVIDER_CONTRACT\n"
    )
    assert {"T09V007", "T09V008"} <= _codes(source)


def test_module_attribute_provider_contract_form_fails() -> None:
    source = (
        "from giclab.harness import t09_provider_contracts\n"
        "target = t09_provider_contracts.V16_PROVIDER_CONTRACT\n"
    )
    assert _codes(source) == {"T09V008"}


def test_aliased_provider_contract_import_fails() -> None:
    source = (
        "from giclab.harness.t09_provider_contracts import "
        "V16_PROVIDER_CONTRACT as selected_contract\n"
        "target = selected_contract\n"
    )
    assert {"T09V007", "T09V008"} <= _codes(source)


def test_returning_versioned_provider_contract_constant_fails() -> None:
    source = "def selected():\n    return V16_PROVIDER_CONTRACT\n"
    assert _codes(source) == {"T09V008"}


def test_unannotated_historical_validation_context_does_not_bypass_lint() -> None:
    source = (
        "from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT\n"
        "selected = provider_contract('V16')\n"
    )
    findings = lint_source(source, relative_path="src/giclab/validation.py")
    assert {finding.code for finding in findings} == {"T09V004"}


def test_historical_validation_context_requires_narrow_annotation() -> None:
    source = "assert receipt['version'] == 'V16'  # giclab-version-lint: historical-identity\n"
    assert lint_source(source, relative_path="src/giclab/validation.py") == ()


def test_annotated_historical_constant_is_allowed_only_in_assertion() -> None:
    source = (
        "from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT  "
        "# giclab-version-lint: historical-identity\n"
        "assert receipt['version'] == V16_PROVIDER_CONTRACT.version  "
        "# giclab-version-lint: historical-identity\n"
    )
    findings = lint_source(
        source,
        relative_path="src/giclab/control/historical_adjudication.py",
    )
    assert findings == ()


def test_annotation_cannot_allow_constant_assignment_selection() -> None:
    source = (
        "from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT  "
        "# giclab-version-lint: historical-identity\n"
        "target = V16_PROVIDER_CONTRACT  "
        "# giclab-version-lint: historical-identity\n"
    )
    assert _codes(source) == {"T09V008"}


def test_make_literal_active_selector_fails() -> None:
    findings = lint_active_selection_text(
        "\tgiclab-control shadow --provider-contract V16 --all-required\n",
        relative_path="Makefile",
    )
    assert {item.code for item in findings} == {"T09V005"}


def test_make_quoted_or_equals_literal_active_selector_fails() -> None:
    for selector in ('--provider-contract="V16"', "--provider-contract 'V16'"):
        findings = lint_active_selection_text(selector, relative_path="Makefile")
        assert {item.code for item in findings} == {"T09V005"}


def test_make_or_ci_literal_package_receipt_root_fails() -> None:
    for relative in ("Makefile", ".github/workflows/ci.yml"):
        findings = lint_active_selection_text(
            "giclab-control refresh-receipts --output-root control/receipts/packages/v17\n",
            relative_path=relative,
        )
        assert {item.code for item in findings} == {"T09V009"}


def test_make_default_has_no_hardcoded_active_v16_selector() -> None:
    findings = lint_active_selection_text(
        (ROOT / "Makefile").read_text(encoding="utf-8"),
        relative_path="Makefile",
    )
    assert findings == ()


def test_actual_repository_has_zero_prohibited_active_dispatches() -> None:
    receipt = validate_active_version_dispatch(ROOT)
    assert receipt["complete"] is True
    assert receipt["findings"] == []
