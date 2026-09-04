"""Source-grounded viability checks for package-owned live effects.

The validator performs no environmental effect. It proves that every method on the
shared ``LowLevelEffects`` protocol has one declared retained primitive and that the
cross-process path exposes the phase, admission, evidence, and cleanup seams a future
package must adapt.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Final, cast

from jsonschema import Draft202012Validator, RefResolver

from giclab.control.category3 import repository_identity
from giclab.control.effects import EFFECT_PROTOCOL_VERSION
from giclab.registry import load_json

METHOD_MAP_PATH: Final = "control/live-method-map.json"
METHOD_MAP_SCHEMA: Final = "schemas/t09-live-method-map.schema.json"
VIABILITY_SCHEMA: Final = "schemas/t09-live-method-viability.schema.json"
EXPECTED_PHASE_ORDER: Final = (
    "exact identity and composition",
    "validated state capsule and control proof",
    "deterministic local package assembly",
    "external authority reservation",
    "exact secret reads",
    "sole authenticated metadata request",
    "provider inventory and launch",
    "provider entry validation",
    "post-entry host package transfer and rehash",
    "host preflight",
    "host qualification",
    "full dynamic scientific freeze",
    "Task A reactive duplex condition session",
    "Task A reactive raw export/finalizer/evaluator",
    "Task A simulative duplex condition session",
    "Task A simulative raw export/finalizer/evaluator",
    "retained first-pair checkpoint",
    "Task B simulative duplex condition session when admitted",
    "Task B simulative raw export/finalizer/evaluator",
    "Task B reactive duplex condition session",
    "Task B reactive raw export/finalizer/evaluator",
    "empirical-prefix cleanup",
    "provider and security terminal verification",
    "authority terminalization and descriptor release",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise ValueError(f"required class is unavailable: {name}")


def _function_names(node: ast.ClassDef) -> tuple[str, ...]:
    return tuple(
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _module_function_names(tree: ast.Module) -> frozenset[str]:
    return frozenset(
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _calls_named(tree: ast.AST, name: str) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        if (isinstance(called, ast.Name) and called.id == name) or (
            isinstance(called, ast.Attribute) and called.attr == name
        ):
            count += 1
    return count


def _validate_map_schema(repository: Path, document: object) -> bool:
    schema_path = repository / METHOD_MAP_SCHEMA
    schema = load_json(schema_path)
    resolver = RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=schema)
    return not list(Draft202012Validator(schema, resolver=resolver).iter_errors(document))


def _source(repository: Path, relative: str) -> tuple[str, ast.Module]:
    value = (repository / relative).read_text(encoding="utf-8")
    return value, ast.parse(value, filename=relative)


def validate_live_method_viability(repository: Path) -> dict[str, object]:
    """Return a deterministic receipt without importing a package effect."""

    root = repository.resolve(strict=True)
    commit, tree = repository_identity(root)
    map_path = root / METHOD_MAP_PATH
    map_bytes = map_path.read_bytes()
    method_map = load_json(map_path)
    methods_raw = method_map.get("methods")
    phases_raw = method_map.get("shared_phase_order")
    if not isinstance(methods_raw, list) or not isinstance(phases_raw, list):
        raise ValueError("live-method map lacks methods or shared phase order")
    methods = [cast(dict[str, object], value) for value in methods_raw]
    mapped_names = tuple(cast(str, item.get("method_name")) for item in methods)

    effects_source, effects_tree = _source(root, "src/giclab/control/effects.py")
    category_source, _category_tree = _source(root, "src/giclab/control/category3.py")
    production_source, production_tree = _source(root, "src/giclab/control/production.py")
    bridge_source, bridge_tree = _source(root, "src/giclab/control/remote_bridge.py")
    runtime_source, runtime_tree = _source(root, "src/giclab/harness/t09_runtime_admission.py")
    gate_source, _gate_tree = _source(root, "src/giclab/harness/sira_gate_a_runtime.py")
    runner_source, runner_tree = _source(
        root, "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    )
    synthetic_source, _synthetic_tree = _source(root, "tests/control/_synthetic_successor.py")

    protocol_names = _function_names(_class(effects_tree, "LowLevelEffects"))
    runner_functions = _module_function_names(runner_tree)
    findings: list[str] = []

    def checked(name: str, predicate: bool, detail: str) -> bool:
        if not predicate:
            findings.append(f"{name}: {detail}")
        return predicate

    map_valid = checked(
        "map-schema",
        _validate_map_schema(root, method_map),
        "declarative method map does not validate",
    )
    protocol_exact = checked(
        "protocol-surface",
        mapped_names == protocol_names and len(mapped_names) == len(set(mapped_names)),
        "mapped method order is not the exact LowLevelEffects surface",
    )
    protocol_version = checked(
        "effect-protocol",
        method_map.get("effect_protocol_version") == EFFECT_PROTOCOL_VERSION == "2.0.0",
        "effect protocol version is not exactly 2.0.0",
    )
    launch_seam = checked(
        "launch-seam",
        "def provider_launch(" not in effects_source
        and "def provider_launch(" not in synthetic_source
        and _calls_named(production_tree, "launch_campaign") == 1
        and "campaign_transport(" in production_source,
        "provider launch does not have one launch_campaign/campaign_transport seam",
    )
    local_assembly = checked(
        "local-assembly",
        "LOCAL_PACKAGE_ASSEMBLY" in category_source
        and "assemble_local_package" in category_source
        and "reserve_before_secret" in production_source
        and EXPECTED_PHASE_ORDER.index("deterministic local package assembly")
        < EXPECTED_PHASE_ORDER.index("external authority reservation"),
        "local assembly is not visibly ordered before external authority reservation",
    )
    post_entry_transfer = checked(
        "host-transfer",
        "HOST_PACKAGE_TRANSFER" in category_source
        and "transfer_package" in category_source
        and category_source.index("adapters.provider_transport.provider_entry(handle)")
        < category_source.index("adapters.host_runtime.transfer_package(handle)"),
        "host transfer is not visibly ordered after provider entry",
    )
    phase_operations = checked(
        "host-phases",
        {
            "host_transfer_verify",
            "host_preflight",
            "host_qualify",
            "host_freeze",
            "condition_session",
            "host_cleanup",
        }
        <= runner_functions,
        "retained runner lacks one or more independent bridge phase entrypoints",
    )
    full_manifest = checked(
        "full-manifest",
        "validate_full_dynamic_frozen_manifest" in bridge_source
        and "_validate_retained_manifest_v0_1" in bridge_source
        and "ValidatedFullFrozenManifest" in bridge_source
        and "validate_full_dynamic_frozen_manifest" in production_source
        and "omitted retained fields" in bridge_source,
        "shared full retained manifest validation/projection is incomplete",
    )
    duplex_admission = checked(
        "duplex-admission",
        "ConditionSessionSupervisor" in bridge_source
        and "DuplexSupervisorPort" in runtime_source
        and "admission_port.model_call" in gate_source
        and "admission_port.browser_action" in gate_source,
        "remote runtime is not visibly coupled to the duplex admission port",
    )
    duplex_class = _class(runtime_tree, "DuplexSupervisorPort")
    sole_accountant = checked(
        "sole-accountant",
        _calls_named(duplex_class, "ProviderBudgetBoundary") == 0
        and "ConditionEventObserver" in bridge_source,
        "duplex client constructs a second authoritative budget boundary",
    )
    transcript_evidence = checked(
        "transcript-evidence",
        {
            "ConditionSessionTerminalReceipt",
            "CanonicalFrameRelay",
            "persist_transcript",
        }
        <= {
            node.name
            for node in ast.walk(bridge_tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        and all(
            token in runner_source
            for token in (
                "duplex-transcript-prefix.json",
                "duplex-remote-event-journal.json",
                "duplex-transcript-manifest.json",
                "condition-session-terminal-receipt.json",
                "essential-failure-manifest.json",
                "raw-attempt-manifest.json",
            )
        ),
        "raw/essential evidence does not bind both transcript sides and terminal chain",
    )
    cleanup_mapping = checked(
        "cleanup-mapping",
        "cleanup_transaction" in effects_source
        and "host_cleanup" in runner_functions
        and "terminalize" in category_source,
        "cleanup or authority terminalization mapping is incomplete",
    )
    phase_order = checked(
        "phase-order",
        tuple(cast(list[str], phases_raw)) == EXPECTED_PHASE_ORDER,
        "shared phase order is not the exact 24-phase lifecycle",
    )
    synthetic_compatible = checked(
        "synthetic-successor",
        'effect_protocol_version="2.0.0"' in synthetic_source
        and "build_live_shaped_no_network_effects" in synthetic_source
        and "provider_launch" not in synthetic_source,
        "synthetic successor does not implement the repaired protocol without a second launch seam",
    )

    mapped_complete = {
        cast(str, item["method_name"])
        for item in methods
        if item.get("live_mapping_complete") is True
        and item.get("post_repair_classification")
        not in {"shadow-only fixture", "redundant and must be removed"}
    }
    unresolved = sorted(set(protocol_names) - mapped_complete)
    if unresolved:
        findings.append("unresolved methods: " + ", ".join(unresolved))
    checks = {
        "map_schema_valid": map_valid,
        "protocol_surface_exact": protocol_exact,
        "effect_protocol_exact": protocol_version,
        "single_launch_mutation_seam": launch_seam,
        "local_assembly_before_effects": local_assembly,
        "post_entry_host_transfer": post_entry_transfer,
        "phase_specific_host_operations": phase_operations,
        "full_manifest_validator": full_manifest,
        "duplex_remote_admission": duplex_admission,
        "sole_authoritative_accountant": sole_accountant,
        "transcript_evidence_binding": transcript_evidence,
        "cleanup_mapping": cleanup_mapping,
        "shared_phase_order_exact": phase_order,
        "synthetic_successor_compatible": synthetic_compatible,
    }
    receipt: dict[str, object] = {
        "schema_version": "1.0.0",
        "repository_commit": commit,
        "repository_tree": tree,
        "effect_protocol_version": EFFECT_PROTOCOL_VERSION,
        "method_map_path": METHOD_MAP_PATH,
        "method_map_bytes": len(map_bytes),
        "method_map_file_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "method_map_semantic_sha256": _canonical_sha256(method_map),
        "methods": methods,
        "shared_phase_order": phases_raw,
        "checks": checks,
        "unresolved_methods": unresolved,
        "findings": findings,
        "live_environment_required": False,
        "real_effects_performed": 0,
        "complete": not findings and all(checks.values()) and not unresolved,
    }
    receipt["semantic_sha256"] = _canonical_sha256(receipt)
    viability_schema_path = root / VIABILITY_SCHEMA
    viability_schema = load_json(viability_schema_path)
    method_map_schema = load_json(root / METHOD_MAP_SCHEMA)
    resolver = RefResolver(
        base_uri=viability_schema_path.resolve().as_uri(),
        referrer=viability_schema,
        store={cast(str, method_map_schema["$id"]): method_map_schema},
    )
    errors = sorted(
        Draft202012Validator(viability_schema, resolver=resolver).iter_errors(receipt),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        raise ValueError(f"live-method viability receipt is invalid: {errors[0].message}")
    return receipt


__all__ = ["EXPECTED_PHASE_ORDER", "METHOD_MAP_PATH", "validate_live_method_viability"]
