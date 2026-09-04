"""Reject deterministic fixture assumptions from effect-neutral production source."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Final, cast

from giclab.control.category3 import repository_identity
from giclab.control.target import (
    SelectedRuntimeTarget,
    resolve_selected_runtime_target,
    validate_selected_runtime_target,
)
from giclab.registry import DuplicateKeyError, load_yaml, loads_json

ANTI_SHADOW_LINT_SCHEMA_VERSION: Final = "4.0.0"
AUDITED_BASE_COMMIT: Final = "f1d872d59c4952eb98467c2506850af7772f4454"
AUDITED_BASE_TREE: Final = "eb70e20024559d65b3fadd240f72d3522895ef04"
SHARED_EFFECT_NEUTRAL_SOURCES: Final = (
    "src/giclab/control/adapters.py",
    "src/giclab/control/category3.py",
    "src/giclab/control/consumers.py",
    "src/giclab/control/contracts.py",
    "src/giclab/control/effects.py",
    "src/giclab/control/live_method_viability.py",
    "src/giclab/control/production.py",
    "src/giclab/control/remote_bridge.py",
    "src/giclab/harness/sira_gate_a_runtime.py",
    "src/giclab/harness/t09_remote_host_phases.py",
    "src/giclab/harness/t09_runtime_admission.py",
    "src/giclab/harness/t09_sira_pilot.py",
)
BRIDGE_LIVE_SOURCES: Final = (
    "src/giclab/control/category3.py",
    "src/giclab/control/effects.py",
    "src/giclab/control/production.py",
    "src/giclab/control/remote_bridge.py",
    "src/giclab/harness/sira_gate_a_runtime.py",
    "src/giclab/harness/t09_remote_host_phases.py",
    "src/giclab/harness/t09_runtime_admission.py",
    "containers/sira-smoke/pragmatic/t09_remote_runner.py",
)
INVENTORY_ROOTS: Final = (
    "src/giclab/control",
    "tests/control",
    "docs",
    "control/incidents",
)
INVENTORY_SUFFIXES: Final = frozenset({".json", ".md", ".py", ".yaml", ".yml"})
LINT_DEFINITION_PATH: Final = "src/giclab/control/anti_shadow_lint.py"
_RUNTIME_TOPOLOGY_MARKERS: Final = ("/private/", "/var/folders/", "/tmp/", "/Users/")
_PACKAGE_RECEIPT_PREFIX: Final = PurePosixPath("control/receipts/packages")
_BOUND_GOAL_RECORD: Final = "bound-goal-record.yaml"
_BINDING_DOCUMENT: Final = "t09-control-receipt-bindings.json"

_FORBIDDEN_TEXT: Final = (
    ("T09S001", re.compile(r"_FAKE_OPENAI_VALUE"), "fake OpenAI credential constant"),
    ("T09S002", re.compile(r"_FAKE_LAMBDA_VALUE"), "fake provider credential constant"),
    ("T09S003", re.compile(r"CALL-SHADOW"), "shadow call identity"),
    ("T09S004", re.compile(r"shadow-response"), "shadow response identity"),
    ("T09S005", re.compile(r"shadow-finalized"), "shadow finalizer path"),
    ("T09S006", re.compile(r"_TASK_A_ANSWER"), "canned Task A answer"),
    ("T09S007", re.compile(r"_TASK_B_ANSWER"), "canned Task B answer"),
    ("T09S008", re.compile(r"\bFakeScenario\b"), "scenario-driven production branch"),
    (
        "T09S009",
        re.compile(r"(?<![0-9])1_?700_?000_?000(?:\.0)?(?![0-9])"),
        "fixed fake epoch",
    ),
    ("T09S010", re.compile(r"production-shadow"), "production-shadow identity"),
)
_INVENTORY_TEXT: Final = (
    re.compile(r"_FAKE_(?:OPENAI|LAMBDA)_VALUE"),
    re.compile(r"CALL-SHADOW"),
    re.compile(r"shadow-response"),
    re.compile(r"shadow-finalized"),
    re.compile(r"production-shadow"),
    re.compile(r"_TASK_[AB]_ANSWER"),
    re.compile(r"\bFakeScenario\b"),
    re.compile(r"(?<![0-9])1_?700_?000_?000(?:\.0)?(?![0-9])"),
    re.compile(r"max_model_call_attempts\s*[=:]\s*1\b"),
    re.compile(r"max_model_calls\s*[=:]\s*1\b"),
)


@dataclass(frozen=True, slots=True)
class AntiShadowFinding:
    path: str
    line: int
    column: int
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ShadowAssumptionOccurrence:
    path: str
    line: int
    token: str
    classification: str


@dataclass(frozen=True, slots=True)
class BaseShadowAssumption:
    assumption_id: str
    path: str
    source_lines: str
    classification: str
    defect: str
    repair_boundary: str


BASE_SHADOW_ASSUMPTION_INVENTORY: Final = (
    BaseShadowAssumption(
        "SA-01",
        "src/giclab/control/production.py",
        "73-74, 105, 160-163, 415-417",
        "shared production-wrapper defect",
        "module fake credentials and equality checks controlled metadata transport",
        "exact mutable parser credential reaches the injected one-send metadata channel",
    ),
    BaseShadowAssumption(
        "SA-02",
        "src/giclab/control/production.py",
        "568-580, 1305-1314, 1670",
        "shared production-wrapper defect",
        "advancing synthetic time, synthetic sleep, and fixed freeze/checkpoint epochs",
        "validated injected monotonic, wall-time, and sleep domains",
    ),
    BaseShadowAssumption(
        "SA-03",
        "src/giclab/control/production.py",
        "1027-1076",
        "shared production-wrapper defect",
        "staging wrote a three-field synthetic fixture instead of the tracked package closure",
        "typed tracked-only archive, acknowledgement, and host-side rehash receipt",
    ),
    BaseShadowAssumption(
        "SA-04",
        "src/giclab/control/production.py",
        "1238-1272",
        "shared production-wrapper defect",
        "host preflight reconstructed a reduced provider-entry document",
        "typed preflight consumes the exact retained launch receipt",
    ),
    BaseShadowAssumption(
        "SA-05",
        "src/giclab/control/production.py",
        "1274-1314",
        "shared production-wrapper defect",
        "qualification and freeze returned synthetic identities without actual effect receipts",
        "request-bound host qualification and dynamic freeze manifests are validated",
    ),
    BaseShadowAssumption(
        "SA-06",
        "src/giclab/control/production.py",
        "1404-1503",
        "shared production-wrapper defect",
        "fixed caps and one hardcoded CRITIC request modeled every condition",
        "package-derived caps and a multi-call/multi-role/multi-action event session",
    ),
    BaseShadowAssumption(
        "SA-07",
        "src/giclab/control/production.py",
        "1505-1543",
        "shared production-wrapper defect",
        "raw manifest and completion identities were synthesized from in-memory accounting",
        "file-backed raw seal, ledgers, process/completion evidence, export, and acknowledgement",
    ),
    BaseShadowAssumption(
        "SA-08",
        "src/giclab/control/production.py",
        "1545-1591",
        "shared production-wrapper defect",
        "finalization used synthetic paths, interpreter, dependency, and completion identities",
        "qualified-local offline finalizer consumes immutable exact raw evidence and receipts",
    ),
    BaseShadowAssumption(
        "SA-09",
        "src/giclab/control/production.py",
        "82-89, 1593-1651",
        "shared production-wrapper defect",
        "the evaluator replaced condition output with canned Task A and Task B answers",
        "the evaluator consumes the effect-produced finalized session",
    ),
    BaseShadowAssumption(
        "SA-10",
        "src/giclab/control/production.py",
        "38, 148-286, 568, 979-1025, 1743-1785",
        "shared production-wrapper defect",
        "the production object required FakeScenario and branched on scenario names",
        "fault injection and deterministic values live only in shadow_effects",
    ),
    BaseShadowAssumption(
        "SA-11",
        "src/giclab/control/adapters.py",
        "25-74",
        "shared production-wrapper defect",
        "effect authority bound no exact package, proof, effect source, root, or external grant",
        "one full EffectAuthorizationContext is validated before assembly and invocation",
    ),
    BaseShadowAssumption(
        "SA-12",
        "src/giclab/control/production.py",
        "75-76, 249, 286-382, 614",
        "shared production-wrapper defect",
        "synthetic network, response, browser, image, and provider fixtures lived in shared source",
        "all deterministic fixture data is confined below the effect boundary",
    ),
)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _line_column(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    previous = source.rfind("\n", 0, offset)
    return line, offset - previous


def _literal_cap_findings(source: str, *, relative_path: str) -> list[AntiShadowFinding]:
    findings: list[AntiShadowFinding] = []
    tree = ast.parse(source, filename=relative_path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = (
            function.id
            if isinstance(function, ast.Name)
            else function.attr
            if isinstance(function, ast.Attribute)
            else None
        )
        if name != "ProviderBudgetCaps":
            continue
        literal_keywords = [
            keyword.arg
            for keyword in node.keywords
            if keyword.arg is not None and isinstance(keyword.value, ast.Constant)
        ]
        if literal_keywords:
            findings.append(
                AntiShadowFinding(
                    path=relative_path,
                    line=node.lineno,
                    column=node.col_offset + 1,
                    code="T09S011",
                    message=(
                        "shared production constructs literal budget caps instead of loading "
                        "the selected package: " + ", ".join(sorted(literal_keywords))
                    ),
                )
            )
    return findings


def _review_bypass_findings(source: str, *, relative_path: str) -> list[AntiShadowFinding]:
    """Reject the exact review bypass shapes in effect-neutral source."""

    findings: list[AntiShadowFinding] = []
    tree = ast.parse(source, filename=relative_path)
    resolved_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "resolve"
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    def add(node: ast.AST, code: str, message: str) -> None:
        findings.append(
            AntiShadowFinding(
                path=relative_path,
                line=getattr(node, "lineno", 1),
                column=getattr(node, "col_offset", 0) + 1,
                code=code,
                message=message,
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "decision"
                    and isinstance(value, ast.Constant)
                    and value.value == "continue-to-task-b"
                ):
                    add(
                        value,
                        "T09S012",
                        "checkpoint continuation is hardcoded instead of retained-policy sourced",
                    )
        if isinstance(node, ast.ClassDef):
            lowered = node.name.casefold()
            if "live" in lowered and (
                lowered.endswith("authority")
                or "authoritygrant" in lowered
                or "livegrant" in lowered
            ):
                opaque_dataclass = any(
                    isinstance(decorator, ast.Call)
                    and (
                        (isinstance(decorator.func, ast.Name) and decorator.func.id == "dataclass")
                        or (
                            isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr == "dataclass"
                        )
                    )
                    and any(
                        keyword.arg == "init"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is False
                        for keyword in decorator.keywords
                    )
                    for decorator in node.decorator_list
                )
                constructor_raises = any(
                    child.name == "__init__"
                    and any(isinstance(statement, ast.Raise) for statement in ast.walk(child))
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                if not opaque_dataclass or not constructor_raises:
                    add(
                        node,
                        "T09S013",
                        "live authority class is publicly constructible",
                    )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "is_symlink"
            and (
                (
                    isinstance(node.func.value, ast.Call)
                    and isinstance(node.func.value.func, ast.Attribute)
                    and node.func.value.func.attr == "resolve"
                )
                or (isinstance(node.func.value, ast.Name) and node.func.value.id in resolved_names)
            )
        ):
            add(
                node,
                "T09S014",
                "symlink identity is checked only after path resolution",
            )
        if (
            relative_path.endswith("/effects.py")
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "spec_from_file_location"
        ):
            add(
                node,
                "T09S015",
                "package effect source execution reopens a pathname through import machinery",
            )
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "transaction_root_identity"
        ) or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "transaction_root_identity"
        ):
            add(
                node,
                "T09S016",
                "effect-supplied transaction-root identity is used as authority",
            )
    return findings


def _required_architecture_findings(
    source: str,
    *,
    relative_path: str,
) -> list[AntiShadowFinding]:
    """Require the residual review contracts to remain visible in shared source."""

    findings: list[AntiShadowFinding] = []

    def missing(code: str, message: str) -> None:
        findings.append(AntiShadowFinding(relative_path, 1, 1, code, message))

    if relative_path.endswith("/production.py"):
        if not all(
            token in source
            for token in (
                "_derive_provider_lifecycle_cost_proof",
                "active_entry_receipt_sha256",
                "closed_slot_source_binding_sha256s",
                "_validate_provider_cost_reconciliation",
            )
        ):
            missing(
                "T09S017",
                "provider cost lacks retained lifecycle source bindings",
            )
        if not all(
            token in source
            for token in (
                "_enumerate_essential_envelope",
                "MAX_ESSENTIAL_FAILURE_JSON_MEMBER_BYTES",
                "export-acknowledgement.json",
            )
        ):
            missing("T09S019", "complete essential envelope lacks finite member caps")
        if "_essential_failure_roots" not in source or "_held_tree_privacy_findings" not in source:
            missing("T09S020", "terminal privacy scan omits essential-failure envelopes")
        if "held_transaction_root.to_document()" in source:
            offset = source.index("held_transaction_root.to_document()")
            line, column = _line_column(source, offset)
            findings.append(
                AntiShadowFinding(
                    relative_path,
                    line,
                    column,
                    "T09S021",
                    "public control evidence retains runtime transaction-root topology",
                )
            )
    if relative_path.endswith("/t09_sira_pilot.py"):
        tree = ast.parse(source, filename=relative_path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "PairCheckpointInput":
                defaults = {
                    child.target.id
                    for child in node.body
                    if isinstance(child, ast.AnnAssign)
                    and isinstance(child.target, ast.Name)
                    and child.value is not None
                }
                if defaults & {"valid_scored_attempt", "finalizer_closure_valid"}:
                    missing("T09S018", "checkpoint safety evidence has pass-valued defaults")
                break
        else:
            missing("T09S018", "PairCheckpointInput is absent")
    if relative_path.endswith("/category3.py"):
        tree = ast.parse(source, filename=relative_path)
        execute = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "execute_category3_transaction"
            ),
            None,
        )
        release_in_finally = execute is not None and any(
            isinstance(node, ast.Try)
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "release_resources"
                for statement in node.finalbody
                for call in ast.walk(statement)
            )
            for node in ast.walk(execute)
        )
        if not release_in_finally:
            missing("T09S022", "Category 3 controller lacks guaranteed resource release")
    return findings


def _definition(
    tree: ast.AST,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    return next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        ),
        None,
    )


def _class_definition(tree: ast.AST, name: str) -> ast.ClassDef | None:
    return next(
        (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == name),
        None,
    )


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _calls(node: ast.AST, name: str) -> int:
    return sum(
        1 for child in ast.walk(node) if isinstance(child, ast.Call) and _called_name(child) == name
    )


def _bridge_bypass_findings(repository: Path) -> list[AntiShadowFinding]:
    """Reject live-bridge shapes that would bypass the accepted shared control plane."""

    findings: list[AntiShadowFinding] = []
    sources: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}

    def add(path: str, code: str, message: str, node: ast.AST | None = None) -> None:
        findings.append(
            AntiShadowFinding(
                path=path,
                line=getattr(node, "lineno", 1),
                column=getattr(node, "col_offset", 0) + 1,
                code=code,
                message=message,
            )
        )

    for relative in BRIDGE_LIVE_SOURCES:
        path = repository / relative
        if not path.is_file() or path.is_symlink():
            add(relative, "T09S029", "required live-bridge source is unavailable")
            continue
        try:
            sources[relative] = path.read_text(encoding="utf-8")
            trees[relative] = ast.parse(sources[relative], filename=relative)
        except (OSError, UnicodeError, SyntaxError):
            add(relative, "T09S029", "required live-bridge source is unreadable")

    effects_path = "src/giclab/control/effects.py"
    effects_tree = trees.get(effects_path)
    if effects_tree is not None:
        protocol = _class_definition(effects_tree, "LowLevelEffects")
        provider_launch = _definition(protocol, "provider_launch") if protocol is not None else None
        campaign_transport = (
            _definition(protocol, "campaign_transport") if protocol is not None else None
        )
        if provider_launch is not None or campaign_transport is None:
            add(
                effects_path,
                "T09S033",
                "LowLevelEffects exposes more or less than the sole campaign-transport launch seam",
                provider_launch or protocol,
            )

    production_path = "src/giclab/control/production.py"
    production_tree = trees.get(production_path)
    production_source = sources.get(production_path, "")
    if production_tree is not None:
        if (
            _calls(production_tree, "launch_campaign") != 1
            or _calls(production_tree, "campaign_transport") != 1
            or _calls(production_tree, "provider_launch") != 0
        ):
            add(
                production_path,
                "T09S033",
                "shared production does not have exactly one "
                "launch_campaign/campaign_transport seam",
            )
        for node in ast.walk(production_tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "uploaded"
                    and isinstance(value, ast.Constant)
                    and value.value is True
                ):
                    add(
                        production_path,
                        "T09S031",
                        "pre-entry local package assembly claims a remote upload",
                        value,
                    )
        if (
            _calls(production_tree, "validate_full_dynamic_frozen_manifest") != 1
            or "manifest_projection_sha256" not in production_source
        ):
            add(
                production_path,
                "T09S032",
                "shared freeze does not require the full retained manifest validator",
            )

    admission_path = "src/giclab/harness/t09_runtime_admission.py"
    admission_tree = trees.get(admission_path)
    if admission_tree is not None:
        duplex = _class_definition(admission_tree, "DuplexSupervisorPort")
        if duplex is None or _calls(duplex, "ProviderBudgetBoundary"):
            add(
                admission_path,
                "T09S030",
                "duplex runtime path constructs a second authoritative ProviderBudgetBoundary",
                duplex,
            )
        effect_methods = (
            "model_call",
            "browser_action",
            "output_bytes",
            "process_exit",
            "completion",
            "raw_published",
        )
        for method_name in effect_methods:
            method = _definition(duplex, method_name) if duplex is not None else None
            if method is None:
                add(
                    admission_path,
                    "T09S034",
                    f"duplex runtime lacks typed event method {method_name}",
                    duplex,
                )
                continue
            for loop in (
                child
                for child in ast.walk(method)
                if isinstance(child, (ast.For, ast.AsyncFor, ast.While))
            ):
                if any(
                    isinstance(call, ast.Call)
                    and _called_name(call) in {"_write_event", "_read_event", "send", "perform"}
                    for call in ast.walk(loop)
                ):
                    add(
                        admission_path,
                        "T09S036",
                        "duplex/provider operation is hidden behind a retry loop",
                        loop,
                    )

    bridge_path = "src/giclab/control/remote_bridge.py"
    bridge_tree = trees.get(bridge_path)
    bridge_source = sources.get(bridge_path, "")
    if bridge_tree is not None:
        frame = _class_definition(bridge_tree, "ConditionBridgeFrame")
        frame_fields = (
            {
                node.target.id
                for node in frame.body
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            }
            if frame is not None
            else set()
        )
        required_frame_fields = {
            "protocol_version",
            "session_id",
            "provider_contract_version",
            "plan_id",
            "host_run_id",
            "condition_run_id",
            "evaluator_run_id",
            "frozen_manifest_sha256",
            "sequence_number",
            "previous_frame_sha256",
            "event_id",
            "event_type",
            "payload",
            "payload_sha256",
            "frame_sha256",
        }
        if not required_frame_fields <= frame_fields:
            add(
                bridge_path,
                "T09S034",
                "condition-session frame omits sequence, hash-chain, or run identity",
                frame,
            )
        supervisor = _class_definition(bridge_tree, "ConditionSessionSupervisor")
        if (
            supervisor is None
            or _calls(supervisor, "model_call") == 0
            or "model-call-admitted" not in bridge_source
            or "browser-action-admitted" not in bridge_source
        ):
            add(
                bridge_path,
                "T09S029",
                "remote condition events are not admitted by the shared observer in real time",
                supervisor,
            )

    runtime_path = "src/giclab/harness/sira_gate_a_runtime.py"
    runtime_tree = trees.get(runtime_path)
    runtime_source = sources.get(runtime_path, "")
    if runtime_tree is not None:
        run = _definition(runtime_tree, "run")
        if (
            run is None
            or "build_private_socket_supervisor_port" not in runtime_source
            or _calls(runtime_tree, "model_call") == 0
            or _calls(run, "browser_action") == 0
        ):
            add(
                runtime_path,
                "T09S029",
                "SiRA remote runtime can bypass the typed shared-admission client",
                run,
            )

    runner_path = "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    runner_tree = trees.get(runner_path)
    runner_source = sources.get(runner_path, "")
    if runner_tree is not None:
        condition = _definition(runner_tree, "condition_session")
        if (
            condition is None
            or _calls(condition, "ProviderBudgetBoundary") != 0
            or "_ConditionSessionBridge" not in runner_source
            or "condition_bridge=bridge" not in runner_source
        ):
            add(
                runner_path,
                "T09S035",
                "retained condition-session bypasses the transparent duplex relay",
                condition,
            )
        if not all(
            _definition(runner_tree, name) is not None
            for name in (
                "host_transfer_verify",
                "host_preflight",
                "host_qualify",
                "host_freeze",
                "condition_session",
                "host_cleanup",
            )
        ):
            add(
                runner_path,
                "T09S032",
                "retained runner lacks one phase-specific host operation",
            )

    # Package-owned implementations are environmental adapters, not alternate
    # lifecycle controllers. There is no real registration in V3-V16, but this
    # scan automatically applies when a future package registers one.
    from giclab.harness.t09_provider_contracts import PROVIDER_CONTRACTS

    for contract in PROVIDER_CONTRACTS.values():
        registration = contract.effect_registration
        if registration is None:
            continue
        relative = registration.implementation_path
        path = repository / relative
        try:
            package_source = path.read_text(encoding="utf-8")
            package_tree = ast.parse(package_source, filename=relative)
        except (OSError, UnicodeError, SyntaxError):
            add(relative, "T09S035", "registered package-live effect source is unreadable")
            continue
        for node in ast.walk(package_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name == "provider_launch" or _calls(node, "provider_launch"):
                add(
                    relative,
                    "T09S033",
                    "package effect exposes the removed secondary launch seam",
                    node,
                )
            if node.name != "campaign_transport" and any(
                isinstance(call, ast.Call)
                and _called_name(call) in {"launch_campaign", "launch_instance", "create_instance"}
                for call in ast.walk(node)
            ):
                add(
                    relative,
                    "T09S035",
                    "package effect launches outside the selected campaign transport",
                    node,
                )
    return findings


def bridge_bypass_findings(repository: Path) -> tuple[AntiShadowFinding, ...]:
    """Return the deterministic live-bridge anti-bypass findings."""

    return tuple(
        sorted(
            _bridge_bypass_findings(repository.resolve(strict=True)),
            key=lambda item: (item.path, item.line, item.column, item.code),
        )
    )


def _topology_finding(path: str, code: str, message: str) -> AntiShadowFinding:
    return AntiShadowFinding(path=path, line=1, column=1, code=code, message=message)


def _selected_receipt_root(target: SelectedRuntimeTarget) -> str:
    return (_PACKAGE_RECEIPT_PREFIX / target.selected_contract.version.lower()).as_posix()


def _bound_member_paths(binding: Mapping[str, object]) -> frozenset[str]:
    """Return the exact sealed inventory named by one aggregate binding."""

    artifacts = binding.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("receipt binding lacks its artifact inventory")
    members = {_BINDING_DOCUMENT}
    for name, reference in artifacts.items():
        references = (
            reference.values()
            if name == "shadow_failures" and isinstance(reference, dict)
            else (reference,)
        )
        for item in references:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise ValueError("receipt binding contains a malformed artifact reference")
            relative = cast(str, item["path"])
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
                raise ValueError("receipt binding contains an unsafe artifact path")
            members.add(relative)
    return frozenset(members)


def _validate_bound_root_proof(
    repository: Path,
    receipt_root: Path,
    binding: Mapping[str, object],
) -> None:
    """Validate one root under its own immutable goal, contract, and revision."""

    from giclab.control.proofs import (  # local import keeps the lint layer acyclic
        REPOSITORY_SLUG,
        ControlProofReference,
        validate_control_receipt_set,
    )
    from giclab.harness import t09_provider_contracts as provider_contracts

    revision = binding.get("control_plane_revision")
    selected = binding.get("selected_runtime_target")
    if not isinstance(revision, dict) or not isinstance(selected, dict):
        raise ValueError("receipt binding identity sections are malformed")
    version = selected.get("selected_provider_contract_version")
    if not isinstance(version, str) or version not in provider_contracts.PROVIDER_CONTRACTS:
        raise ValueError("receipt binding selects an unregistered contract")
    binding_path = receipt_root / _BINDING_DOCUMENT
    encoded = binding_path.read_bytes()
    validate_control_receipt_set(
        repository,
        provider_contracts.PROVIDER_CONTRACTS[version],
        ControlProofReference(
            approved_root=receipt_root,
            binding_path=binding_path,
            expected_file_sha256=hashlib.sha256(encoded).hexdigest(),
            expected_control_commit=str(revision.get("commit")),
            expected_control_tree=str(revision.get("tree")),
            expected_repository_slug=str(binding.get("repository_slug", REPOSITORY_SLUG)),
            expected_provider_contract_version=version,
            expected_plan_id=str(selected.get("selected_plan_id")),
            expected_command_package_sha256=str(selected.get("selected_command_package_sha256")),
            expected_target_source=str(selected.get("source")),
            expected_goal_record_sha256=str(selected.get("goal_record_sha256")),
            expected_target_semantic_sha256=str(selected.get("semantic_sha256")),
        ),
    )


def _scan_bound_receipt_root(
    repository: Path,
    receipt_root: Path,
    *,
    display_root: str,
    validate_seal: bool,
) -> tuple[list[AntiShadowFinding], int, dict[str, object] | None]:
    """Scan every and only member named by one sealed binding."""

    findings: list[AntiShadowFinding] = []
    binding_path = receipt_root / _BINDING_DOCUMENT
    try:
        encoded_binding = binding_path.read_bytes()
        binding_value = loads_json(encoded_binding)
        if not isinstance(binding_value, dict):
            raise ValueError("binding is not one object")
        binding = cast(dict[str, object], binding_value)
        expected = _bound_member_paths(binding)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        findings.append(
            _topology_finding(
                display_root,
                "T09S026",
                f"sealed public receipt binding is invalid: {exc}",
            )
        )
        return findings, 0, None

    selected_value = binding.get("selected_runtime_target")
    bound_target = (
        cast(dict[str, object], selected_value) if isinstance(selected_value, dict) else None
    )
    if validate_seal:
        try:
            _validate_bound_root_proof(repository, receipt_root, binding)
        except (OSError, ValueError) as exc:
            findings.append(
                _topology_finding(
                    display_root,
                    "T09S026",
                    f"sealed public receipt root fails its immutable proof: {exc}",
                )
            )

    observed: set[str] = set()
    legacy = receipt_root == repository / "control/receipts"
    try:
        candidates = sorted(receipt_root.rglob("*"), key=lambda item: item.as_posix())
    except OSError as exc:
        findings.append(
            _topology_finding(display_root, "T09S027", f"receipt inventory failed: {exc}")
        )
        return findings, 0, bound_target
    for path in candidates:
        relative_path = path.relative_to(receipt_root)
        if legacy and relative_path.parts[:1] == ("packages",):
            continue
        try:
            metadata = path.stat(follow_symlinks=False)
        except OSError as exc:
            findings.append(
                _topology_finding(
                    f"{display_root}/{relative_path.as_posix()}",
                    "T09S027",
                    f"bound receipt member is unavailable: {exc}",
                )
            )
            continue
        if stat.S_ISDIR(metadata.st_mode):
            continue
        relative = relative_path.as_posix()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            findings.append(
                _topology_finding(
                    f"{display_root}/{relative}",
                    "T09S027",
                    "public receipt root contains a nonregular or symlink member",
                )
            )
            continue
        observed.add(relative)

    for relative in sorted(expected - observed):
        findings.append(
            _topology_finding(
                f"{display_root}/{relative}",
                "T09S027",
                "bound public receipt member was omitted from the scan",
            )
        )
    for relative in sorted(observed - expected):
        findings.append(
            _topology_finding(
                f"{display_root}/{relative}",
                "T09S027",
                "sealed public receipt root contains an unbound extra member",
            )
        )

    for relative in sorted(expected & observed):
        path = receipt_root / relative
        display_path = f"{display_root}/{relative}"
        try:
            encoded = path.read_bytes()
            source = encoded.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(
                _topology_finding(
                    display_path,
                    "T09S028",
                    f"bound receipt member is not readable text: {exc}",
                )
            )
            continue

        document: object = None
        structured_error: Exception | None = None
        try:
            if path.suffix.casefold() == ".json":
                document = loads_json(encoded)
            elif path.suffix.casefold() in {".yaml", ".yml"}:
                document = load_yaml(path)
        except (UnicodeError, json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
            structured_error = exc

        declared_marker_allowance = Counter[str]()
        if PurePosixPath(relative).name == "anti-shadow-lint.json" and isinstance(document, dict):
            topology = document.get("public_receipt_topology_scan")
            declared = (
                topology.get("forbidden_path_markers") if isinstance(topology, dict) else None
            )
            if declared == list(_RUNTIME_TOPOLOGY_MARKERS):
                declared_marker_allowance.update(cast(list[str], declared))
        for marker in _RUNTIME_TOPOLOGY_MARKERS:
            if source.count(marker) > declared_marker_allowance[marker]:
                findings.append(
                    _topology_finding(
                        display_path,
                        "T09S023",
                        f"public receipt contains runtime path marker {marker}",
                    )
                )

        if structured_error is not None:
            findings.append(
                _topology_finding(
                    display_path,
                    "T09S028",
                    f"bound structured receipt member is invalid: {structured_error}",
                )
            )
            continue

        def visit(
            value: object,
            *,
            parent_key: str | None = None,
            scanned_path: str = display_path,
        ) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if str(key).casefold() in {"device", "inode", "uid"}:
                        findings.append(
                            _topology_finding(
                                scanned_path,
                                "T09S024",
                                f"public receipt retains runtime filesystem field {key}",
                            )
                        )
                    visit(child, parent_key=str(key))
            elif isinstance(value, list):
                for child in value:
                    visit(child, parent_key=parent_key)
            elif isinstance(value, str) and parent_key != "forbidden_path_markers":
                for marker in _RUNTIME_TOPOLOGY_MARKERS:
                    if marker in value:
                        findings.append(
                            _topology_finding(
                                scanned_path,
                                "T09S023",
                                f"public receipt contains runtime path marker {marker}",
                            )
                        )

        if document is not None:
            visit(document)
    return findings, len(expected & observed), bound_target


def _public_receipt_topology_scan(
    repository: Path,
    *,
    target: SelectedRuntimeTarget,
    selected_receipt_root: Path | None = None,
    validate_selected_seal: bool = True,
) -> tuple[tuple[AntiShadowFinding, ...], dict[str, object]]:
    """Validate the selected root plus every independently sealed historical root."""

    from giclab.control.proofs import ControlProofError, discover_sealed_control_receipt_roots

    root = repository.resolve(strict=True)
    selected_relative = _selected_receipt_root(target)
    selected_path = root / selected_relative
    findings: list[AntiShadowFinding] = []
    try:
        discovered = list(discover_sealed_control_receipt_roots(root))
    except (OSError, ControlProofError) as exc:
        discovered = []
        findings.append(
            _topology_finding(
                "control/receipts",
                "T09S026",
                f"sealed receipt-root inventory is invalid: {exc}",
            )
        )

    explicit = selected_receipt_root
    if explicit is not None:
        explicit = Path(os.path.abspath(explicit))
        expected_staging_prefix = f".{target.selected_contract.version.lower()}-receipt-staging-"
        if explicit != selected_path and (
            explicit.parent != selected_path.parent
            or not explicit.name.startswith(expected_staging_prefix)
        ):
            findings.append(
                _topology_finding(
                    selected_relative,
                    "T09S025",
                    "selected receipt candidate is outside its exact publication boundary",
                )
            )
            explicit = None
    if explicit is not None:
        discovered = [
            candidate
            for candidate in discovered
            if candidate != selected_path or candidate == explicit
        ]
        if explicit not in discovered:
            discovered.append(explicit)
    elif selected_path not in discovered:
        findings.append(
            _topology_finding(
                selected_relative,
                "T09S025",
                "selected runtime target lacks its exact sealed public receipt root",
            )
        )

    sealed_roots: list[str] = []
    counts: dict[str, int] = {}
    selected_scanned = False
    seen_paths: set[Path] = set()
    for candidate in sorted(discovered, key=lambda item: item.as_posix()):
        absolute = Path(os.path.abspath(candidate))
        if absolute in seen_paths:
            continue
        seen_paths.add(absolute)
        display = (
            selected_relative
            if explicit is not None and absolute == explicit
            else absolute.relative_to(root).as_posix()
        )
        sealed_roots.append(display)
        root_findings, count, bound_target = _scan_bound_receipt_root(
            root,
            absolute,
            display_root=display,
            validate_seal=(validate_selected_seal if display == selected_relative else True),
        )
        findings.extend(root_findings)
        counts[display] = count
        if display == selected_relative:
            selected_scanned = bound_target == target.to_document()
            if not selected_scanned:
                findings.append(
                    _topology_finding(
                        display,
                        "T09S025",
                        "selected receipt root does not bind the exact selected runtime target",
                    )
                )
    if not selected_scanned:
        findings.append(
            _topology_finding(
                selected_relative,
                "T09S025",
                "selected provider contract was not scanned at its exact receipt root",
            )
        )
    ordered_findings = tuple(
        sorted(
            findings, key=lambda item: (item.path, item.line, item.column, item.code, item.message)
        )
    )
    summary: dict[str, object] = {
        "selected_provider_contract_version": target.selected_contract.version,
        "selected_receipt_root": selected_relative,
        "selected_root_matches_version": selected_relative.endswith(
            "/" + target.selected_contract.version.lower()
        ),
        "sealed_roots_scanned": sorted(sealed_roots),
        "member_count_by_root": {key: counts[key] for key in sorted(counts)},
        "forbidden_path_markers": list(_RUNTIME_TOPOLOGY_MARKERS),
        "forbidden_filesystem_fields": ["device", "inode", "uid"],
        "findings": len(ordered_findings),
        "complete": not ordered_findings,
    }
    return ordered_findings, summary


def public_receipt_topology_findings(
    repository: Path,
    *,
    target: SelectedRuntimeTarget | None = None,
    selected_receipt_root: Path | None = None,
) -> tuple[AntiShadowFinding, ...]:
    """Reject topology from the selected and every retained sealed receipt root."""

    root = repository.resolve(strict=True)
    selected = (
        resolve_selected_runtime_target(root)
        if target is None
        else validate_selected_runtime_target(root, target)
    )
    findings, _summary = _public_receipt_topology_scan(
        root,
        target=selected,
        selected_receipt_root=selected_receipt_root,
    )
    return findings


def lint_effect_neutral_source(
    source: str,
    *,
    relative_path: str,
) -> tuple[AntiShadowFinding, ...]:
    """Lint one shared module for fixture literals and hard-coded budget caps."""

    findings: list[AntiShadowFinding] = []
    for code, pattern, message in _FORBIDDEN_TEXT:
        for match in pattern.finditer(source):
            line, column = _line_column(source, match.start())
            findings.append(
                AntiShadowFinding(
                    path=relative_path,
                    line=line,
                    column=column,
                    code=code,
                    message=message,
                )
            )
    findings.extend(_literal_cap_findings(source, relative_path=relative_path))
    findings.extend(_review_bypass_findings(source, relative_path=relative_path))
    findings.extend(_required_architecture_findings(source, relative_path=relative_path))
    return tuple(sorted(findings, key=lambda item: (item.line, item.column, item.code)))


def _classification(relative: str) -> str:
    if relative.startswith("tests/"):
        return "historical test fixture"
    if relative in {
        "src/giclab/control/shadow.py",
        "src/giclab/control/shadow_effects.py",
    }:
        return "legitimate deterministic effect fixture"
    if relative.startswith("docs/") or relative.startswith("control/incidents/"):
        return "documentation"
    if relative in SHARED_EFFECT_NEUTRAL_SOURCES:
        return "shared production-wrapper defect"
    return "historical test fixture"


def _inventory(repository: Path) -> tuple[ShadowAssumptionOccurrence, ...]:
    occurrences: list[ShadowAssumptionOccurrence] = []
    paths = sorted(
        {
            path
            for relative_root in INVENTORY_ROOTS
            for path in (repository / relative_root).rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.casefold() in INVENTORY_SUFFIXES
        }
    )
    for path in paths:
        relative = path.relative_to(repository).as_posix()
        if relative == LINT_DEFINITION_PATH:
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in _INVENTORY_TEXT:
            for match in pattern.finditer(source):
                line, _column = _line_column(source, match.start())
                occurrences.append(
                    ShadowAssumptionOccurrence(
                        relative,
                        line,
                        match.group(0),
                        _classification(relative),
                    )
                )
    return tuple(
        sorted(
            occurrences,
            key=lambda item: (item.path, item.line, item.token),
        )
    )


def validate_anti_shadow_lint(
    repository: Path,
    *,
    target: SelectedRuntimeTarget | None = None,
    selected_receipt_root: Path | None = None,
    validate_selected_seal: bool = True,
) -> dict[str, object]:
    """Return a deterministic receipt for the exact effect-neutral source set."""

    root = repository.resolve(strict=True)
    selected = (
        resolve_selected_runtime_target(root)
        if target is None
        else validate_selected_runtime_target(root, target)
    )
    findings: list[AntiShadowFinding] = []
    scanned: list[str] = []
    for relative in SHARED_EFFECT_NEUTRAL_SOURCES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            findings.append(
                AntiShadowFinding(
                    path=relative,
                    line=1,
                    column=1,
                    code="T09S000",
                    message="effect-neutral source is unavailable",
                )
            )
            continue
        scanned.append(relative)
        findings.extend(
            lint_effect_neutral_source(
                path.read_text(encoding="utf-8"),
                relative_path=relative,
            )
        )
    topology_findings, topology_scan = _public_receipt_topology_scan(
        root,
        target=selected,
        selected_receipt_root=selected_receipt_root,
        validate_selected_seal=validate_selected_seal,
    )
    findings.extend(topology_findings)
    findings.extend(bridge_bypass_findings(root))
    inventory = _inventory(root)
    counts = Counter(item.classification for item in inventory)
    commit, tree = repository_identity(root)
    document: dict[str, object] = {
        "schema_version": ANTI_SHADOW_LINT_SCHEMA_VERSION,
        "repository_commit": commit,
        "repository_tree": tree,
        "audited_base": {
            "commit": AUDITED_BASE_COMMIT,
            "tree": AUDITED_BASE_TREE,
        },
        "base_assumption_inventory": [asdict(item) for item in BASE_SHADOW_ASSUMPTION_INVENTORY],
        "shared_effect_neutral_sources": scanned,
        "bridge_live_sources": list(BRIDGE_LIVE_SOURCES),
        "lint_definition_path": LINT_DEFINITION_PATH,
        "forbidden_rule_codes": [code for code, _pattern, _message in _FORBIDDEN_TEXT]
        + [f"T09S{index:03d}" for index in range(11, 37)],
        "findings": [asdict(item) for item in findings],
        "assumption_inventory": [asdict(item) for item in inventory],
        "classification_counts": {
            classification: counts.get(classification, 0)
            for classification in (
                "legitimate deterministic effect fixture",
                "shared production-wrapper defect",
                "historical test fixture",
                "documentation",
            )
        },
        "public_receipt_topology_scan": topology_scan,
        "complete": not findings,
    }
    document["semantic_sha256"] = _canonical_sha256(document)
    return document


__all__ = [
    "ANTI_SHADOW_LINT_SCHEMA_VERSION",
    "BASE_SHADOW_ASSUMPTION_INVENTORY",
    "BRIDGE_LIVE_SOURCES",
    "SHARED_EFFECT_NEUTRAL_SOURCES",
    "bridge_bypass_findings",
    "lint_effect_neutral_source",
    "public_receipt_topology_findings",
    "validate_anti_shadow_lint",
]
