"""Offline-only closeout of the T07 high-assurance firewall evidence track.

This module has no credential, HTTP, cloud-mutation, SSH, browser, container, model,
or SiRA surface. It consumes the immutable burned capture, produces a private exact
baseline and restoration payload, and copies a sealed bundle to the approved APFS
archive. Public outputs contain structural names, JSON types, counts and hashes only.
"""

from __future__ import annotations

import os
import secrets
import stat
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from jsonschema import Draft202012Validator, FormatChecker

from . import lambda_firewall_baseline as firewall
from .lambda_archive import (
    DiskutilVolumeObserver,
    InventoryArchiveError,
    _HeldDirectory,
    _open_or_create_archive_root,
    _read_regular_at,
    _same_identity,
    _validate_external,
    _validate_system,
    _write_exclusive_at,
)
from .sira_storage import APPROVED_MOUNT, SYSTEM_DATA_MOUNT, VolumeObservation


class HighAssuranceCloseoutError(ValueError):
    """The offline closeout could not preserve its evidence or freeze contract."""


CLOSEOUT_ID: Final = "T07-HIGH-ASSURANCE-FIREWALL-CLOSEOUT-0001"
CLOSEOUT_STATE: Final = "high-assurance-infrastructure-frozen"
BOUNDED_FORK_STATE: Final = "bounded-smoke-fork-ready"
LOCAL_ROOT_RELATIVE: Final = Path("artifacts/t07/lambda/gate-l2m") / CLOSEOUT_ID
PUBLIC_ADJUDICATION_RELATIVE: Final = Path(
    "docs/harness/evidence/T07_FIREWALL_CAPTURE_0001_OFFLINE_ADJUDICATION.json"
)
PUBLIC_STRUCTURAL_REPORT_RELATIVE: Final = Path(
    "docs/harness/evidence/T07_FIREWALL_CAPTURE_0001_STRUCTURAL_REPORT.json"
)
ADJUDICATION_SCHEMA_RELATIVE: Final = Path(
    "schemas/t07-lambda-firewall-capture-adjudication.schema.json"
)

CAPTURE_LEDGER_SHA256: Final = "f37e4e450ff5d7ab203dcbdfcd00318bf3ee5b053469207517b19e26c549fb43"
CAPTURE_RAW_BYTES: Final = 660
CAPTURE_RAW_SHA256: Final = "983d231beefd2e446c4b9261be5da812862a7e629535cb063c6413cd67f55adf"
CAPTURE_EXTERNAL_MANIFEST_SHA256: Final = (
    "2b2c9deb74f45e2da45bc6209aa3a45e10f290a9aff6ac955da543d89df4823d"
)
CAPTURE_EXTERNAL_COPY_RECORD_SHA256: Final = (
    "4256db4e1657e29e59b3ff642039157f6866590403ee02b7b4a4a6fa69cfe268"
)
CAPTURE_EXTERNAL_SEAL_SHA256: Final = (
    "2ac3a92a4f6e4cd2963b8f816925c0a7111d4f2f469a3104d1d94e4522723897"
)
CAPTURE_EXTERNAL_ROOT: Final = (
    APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts" / firewall.CAPTURE_RUN_ID
)
MAX_CLOSEOUT_BUNDLE_BYTES: Final = 2_097_152
MAX_CLOSEOUT_WALL_SECONDS: Final = 60

SCIENTIFIC_HASHES: Final[Mapping[str, str]] = {
    "experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml": (
        "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c"
    ),
    "experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml": (
        "f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d"
    ),
    "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml": (
        "ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425"
    ),
    "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml": (
        "7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018"
    ),
    "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml": (
        "68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436"
    ),
}


@dataclass(frozen=True, slots=True)
class ImmutableCaptureEvidence:
    ledger: bytes = field(repr=False)
    raw_response: bytes = field(repr=False)
    ledger_rows: tuple[Mapping[str, object], ...] = field(repr=False)
    authorization_reference: str
    retrieved_at_utc: str
    elapsed_ms: int


@dataclass(frozen=True, slots=True)
class AuthoritativeFirewallDocuments:
    baseline_alias: str
    canonical_semantic_sha256: str
    restoration_payload_alias: str
    restoration_payload_sha256: str
    private_baseline: bytes = field(repr=False)
    restoration_payload: bytes = field(repr=False)
    canonical_report: bytes = field(repr=False)
    adjudication: bytes = field(repr=False)
    raw_response: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class AuthoritativeFirewallSeal:
    baseline_alias: str
    canonical_semantic_sha256: str
    restoration_payload_alias: str
    restoration_payload_sha256: str
    local_seal_sha256: str
    archive_alias: str
    external_copy_record_sha256: str
    external_seal_sha256: str
    destination_hashes_verified: bool
    source_retained: bool
    local_root: Path = field(repr=False)
    external_root: Path = field(repr=False)


def _read_exact(path: Path, *, expected_sha256: str, expected_bytes: int | None = None) -> bytes:
    encoded = firewall._read_regular_no_follow(path, max_bytes=MAX_CLOSEOUT_BUNDLE_BYTES)
    if expected_bytes is not None and len(encoded) != expected_bytes:
        raise HighAssuranceCloseoutError("immutable capture evidence byte identity drifted")
    if firewall.sha256_bytes(encoded) != expected_sha256:
        raise HighAssuranceCloseoutError("immutable capture evidence hash drifted")
    return encoded


def _strict_rows(encoded: bytes) -> tuple[Mapping[str, object], ...]:
    rows = tuple(
        firewall._strict_json(line, context="capture ledger event")
        for line in encoded.splitlines()
        if line
    )
    if not rows or any(
        row.get("event_sequence") != ordinal for ordinal, row in enumerate(rows, start=1)
    ):
        raise HighAssuranceCloseoutError("capture ledger sequence is incomplete")
    return rows


def _validate_ledger(rows: Sequence[Mapping[str, object]]) -> tuple[str, str, int]:
    sends = [row for row in rows if row.get("event_type") == "request_send_started"]
    completed = [row for row in rows if row.get("event_type") == "response_body_completed"]
    failures = [row for row in rows if row.get("event_type") == "request_failed"]
    if len(sends) != 1 or len(completed) != 1 or len(failures) != 1:
        raise HighAssuranceCloseoutError("capture ledger request cardinality drifted")
    response = completed[0]
    failure = failures[0]
    if (
        response.get("request_ordinal") != 1
        or response.get("method") != "GET"
        or response.get("host") != "cloud.lambda.ai"
        or response.get("path") != firewall.GLOBAL_FIREWALL_PATH
        or response.get("http_status") != 200
        or response.get("bytes_received_so_far") != CAPTURE_RAW_BYTES
        or response.get("response_sha256") != CAPTURE_RAW_SHA256
        or response.get("retry_count") != 0
        or response.get("pagination_request") is not False
        or failure.get("sanitized_failure_stage") != "schema_validation"
        or failure.get("sanitized_failure_class") != "schema_drift"
        or rows[-1].get("event_type") != "run_stopped"
        or rows[-1].get("sanitized_failure_class") != "schema_drift"
    ):
        raise HighAssuranceCloseoutError("capture ledger terminal evidence drifted")
    references = {row.get("authorization_reference") for row in rows}
    authorization_reference = next(iter(references)) if len(references) == 1 else None
    if not isinstance(authorization_reference, str):
        raise HighAssuranceCloseoutError("capture authorization reference drifted")
    retrieved_at = response.get("wall_timestamp_utc")
    elapsed_ms = response.get("elapsed_ms")
    if not isinstance(retrieved_at, str) or type(elapsed_ms) is not int:
        raise HighAssuranceCloseoutError("capture response timing evidence drifted")
    return authorization_reference, retrieved_at, elapsed_ms


def verify_immutable_capture(repository_root: Path) -> ImmutableCaptureEvidence:
    """Verify the burned local/external capture without exposing private values."""

    root = repository_root.resolve(strict=True)
    ledger = _read_exact(
        root / firewall.CAPTURE_LEDGER_RELATIVE,
        expected_sha256=CAPTURE_LEDGER_SHA256,
    )
    raw = _read_exact(
        root / firewall.CAPTURE_RUN_ROOT_RELATIVE / "raw-global-firewall-response.json",
        expected_sha256=CAPTURE_RAW_SHA256,
        expected_bytes=CAPTURE_RAW_BYTES,
    )
    external_manifest = _read_exact(
        CAPTURE_EXTERNAL_ROOT / "CAPTURE_MANIFEST.json",
        expected_sha256=CAPTURE_EXTERNAL_MANIFEST_SHA256,
    )
    external_copy = _read_exact(
        CAPTURE_EXTERNAL_ROOT / "COPY_RECORD.json",
        expected_sha256=CAPTURE_EXTERNAL_COPY_RECORD_SHA256,
    )
    external_seal = _read_exact(
        CAPTURE_EXTERNAL_ROOT / "SEAL.json",
        expected_sha256=CAPTURE_EXTERNAL_SEAL_SHA256,
    )
    if (
        _read_exact(
            CAPTURE_EXTERNAL_ROOT / "request-ledger.jsonl",
            expected_sha256=CAPTURE_LEDGER_SHA256,
        )
        != ledger
        or _read_exact(
            CAPTURE_EXTERNAL_ROOT / "raw-global-firewall-response.json",
            expected_sha256=CAPTURE_RAW_SHA256,
            expected_bytes=CAPTURE_RAW_BYTES,
        )
        != raw
    ):
        raise HighAssuranceCloseoutError("capture source/destination evidence differs")
    manifest = firewall._strict_json(external_manifest, context="capture manifest")
    copy_record = firewall._strict_json(external_copy, context="capture copy record")
    seal = firewall._strict_json(external_seal, context="capture external seal")
    if (
        manifest.get("complete_baseline") is not False
        or seal.get("complete_baseline") is not False
        or seal.get("cloud_mutation_occurred") is not False
        or seal.get("destination_hashes_verified") is not True
        or copy_record.get("destination_hashes_verified") is not True
        or copy_record.get("internal_fallback") is not False
        or copy_record.get("source_retained") is not True
    ):
        raise HighAssuranceCloseoutError("capture seal contract drifted")
    rows = _strict_rows(ledger)
    authorization_reference, retrieved_at, elapsed_ms = _validate_ledger(rows)
    return ImmutableCaptureEvidence(
        ledger,
        raw,
        rows,
        authorization_reference,
        retrieved_at,
        elapsed_ms,
    )


def build_authoritative_documents(
    repository_root: Path,
    evidence: ImmutableCaptureEvidence,
    *,
    require_observed_workspace_extension: bool,
) -> AuthoritativeFirewallDocuments:
    """Adjudicate one complete retained response and render private/public records."""

    root = repository_root.resolve(strict=True)
    envelope = firewall._strict_json(evidence.raw_response, context="retained capture response")
    parsed = firewall.parse_global_firewall_response(envelope)
    ruleset = parsed.parsed_ruleset.ruleset
    baseline = parsed.parsed_ruleset.baseline
    extension_types = parsed.parsed_ruleset.extension_types
    if require_observed_workspace_extension and extension_types != (("workspace_id", "string"),):
        raise HighAssuranceCloseoutError("observed compatible extension structure drifted")
    restoration, restoration_encoded, restoration_sha256 = firewall.build_exact_restoration_payload(
        parsed.parsed_ruleset.rules,
        repository_root=root,
    )
    restoration_alias = f"l2m-firewall-restoration-{restoration_sha256[:12]}"
    canonical_report_document = firewall.complete_canonical_report(
        baseline,
        envelope=parsed.envelope,
        ruleset=ruleset,
    )
    firewall.validate_canonical_report(canonical_report_document, repository_root=root)
    canonical_report = firewall.canonical_json_bytes(canonical_report_document)
    baseline_document: dict[str, object] = {
        "schema_version": "0.1.0",
        "baseline_alias": baseline.alias,
        "canonicalization_version": firewall.CANONICALIZATION_VERSION,
        "response_parser_version": firewall.FIREWALL_RESPONSE_PARSER_VERSION,
        "capture_plan_id": firewall.CAPTURE_PLAN_ID,
        "capture_run_id": firewall.CAPTURE_RUN_ID,
        "authorization_reference": evidence.authorization_reference,
        "provider": "lambda-on-demand-cloud",
        "api_base_url": firewall.API_BASE_URL,
        "retrieved_at_utc": evidence.retrieved_at_utc,
        "official_contract": {
            "url": firewall.OPENAPI_URL,
            "api_version": firewall.API_VERSION,
            "openapi_version": firewall.OPENAPI_VERSION,
            "bytes": firewall.OPENAPI_BYTES,
            "sha256": firewall.OPENAPI_SHA256,
        },
        "request": {
            "method": "GET",
            "path": firewall.GLOBAL_FIREWALL_PATH,
            "http_status": 200,
            "response_bytes": len(evidence.raw_response),
            "response_sha256": firewall.sha256_bytes(evidence.raw_response),
        },
        "raw_response": {
            "relative_path": "raw-global-firewall-response.json",
            "bytes": len(evidence.raw_response),
            "sha256": firewall.sha256_bytes(evidence.raw_response),
            "byte_preserved": True,
        },
        "global_ruleset": dict(ruleset),
        "canonical_semantic_sha256": baseline.semantic_sha256,
        "restoration_payload_sha256": restoration_sha256,
        "unknown_fields": {
            "envelope": [],
            "global_ruleset": [name for name, _value_type in extension_types],
            "rules": [[] for _value in parsed.parsed_ruleset.rules],
        },
    }
    baseline_schema, _baseline_schema_sha256 = firewall._load_schema(
        root, firewall.BASELINE_SCHEMA_RELATIVE
    )
    if (
        next(
            Draft202012Validator(
                baseline_schema,
                format_checker=FormatChecker(),
            ).iter_errors(baseline_document),
            None,
        )
        is not None
    ):
        raise HighAssuranceCloseoutError("authoritative private baseline failed its schema")
    private_baseline = firewall.canonical_json_bytes(baseline_document)
    if (
        firewall._strict_json(restoration_encoded, context="authoritative restoration payload")
        != restoration
    ):
        raise HighAssuranceCloseoutError("restoration payload serialization drifted")
    adjudication_document: dict[str, object] = {
        "schema_version": "0.1.0",
        "capture_run_id": firewall.CAPTURE_RUN_ID,
        "capture_plan_id": firewall.CAPTURE_PLAN_ID,
        "original_disposition": "schema_drift",
        "adjudicated_classification": "compatible_additive_top_level_extension",
        "request": {
            "method": "GET",
            "path": firewall.GLOBAL_FIREWALL_PATH,
            "http_status": 200,
            "response_bytes": len(evidence.raw_response),
            "elapsed_ms": evidence.elapsed_ms,
        },
        "immutable_evidence": {
            "request_ledger_sha256": firewall.sha256_bytes(evidence.ledger),
            "raw_response_sha256": firewall.sha256_bytes(evidence.raw_response),
            "external_manifest_sha256": CAPTURE_EXTERNAL_MANIFEST_SHA256,
            "external_copy_record_sha256": CAPTURE_EXTERNAL_COPY_RECORD_SHA256,
            "external_seal_sha256": CAPTURE_EXTERNAL_SEAL_SHA256,
        },
        "official_contract": {
            "url": firewall.OPENAPI_URL,
            "api_version": firewall.API_VERSION,
            "openapi_version": firewall.OPENAPI_VERSION,
            "bytes": firewall.OPENAPI_BYTES,
            "sha256": firewall.OPENAPI_SHA256,
            "additional_properties_explicitly_forbidden": False,
        },
        "response_parser_version": firewall.FIREWALL_RESPONSE_PARSER_VERSION,
        "compatible_top_level_extensions": [
            {"name": name, "type": value_type} for name, value_type in extension_types
        ],
        "rule_count": baseline.rule_count,
        "all_rules_strictly_valid": True,
        "baseline_alias": baseline.alias,
        "canonical_semantic_sha256": baseline.semantic_sha256,
        "restoration_payload_alias": restoration_alias,
        "restoration_payload_sha256": restoration_sha256,
        "run_replay_allowed": False,
        "cloud_mutation_occurred": False,
        "external_request_during_adjudication": False,
        "private_scalar_values_retained": False,
    }
    adjudication_schema, _adjudication_schema_sha256 = firewall._load_schema(
        root, ADJUDICATION_SCHEMA_RELATIVE
    )
    if (
        next(
            Draft202012Validator(adjudication_schema).iter_errors(adjudication_document),
            None,
        )
        is not None
    ):
        raise HighAssuranceCloseoutError("offline adjudication failed its public schema")
    return AuthoritativeFirewallDocuments(
        baseline.alias,
        baseline.semantic_sha256,
        restoration_alias,
        restoration_sha256,
        private_baseline,
        restoration_encoded,
        canonical_report,
        firewall.canonical_json_bytes(adjudication_document),
        evidence.raw_response,
    )


def adjudicate_capture_run(repository_root: Path) -> AuthoritativeFirewallDocuments:
    """Build deterministic closeout documents from the exact immutable real capture."""

    evidence = verify_immutable_capture(repository_root)
    return build_authoritative_documents(
        repository_root,
        evidence,
        require_observed_workspace_extension=True,
    )


def verify_scientific_locks(repository_root: Path) -> None:
    root = repository_root.resolve(strict=True)
    for relative, expected in SCIENTIFIC_HASHES.items():
        encoded = firewall._read_regular_no_follow(root / relative, max_bytes=1_048_576)
        if firewall.sha256_bytes(encoded) != expected:
            raise HighAssuranceCloseoutError("locked scientific input drifted")


def _create_local_bundle(
    root: Path,
    documents: AuthoritativeFirewallDocuments,
    *,
    implementation_commit: str,
) -> tuple[Path, dict[str, bytes], bytes, bytes]:
    parent = root / LOCAL_ROOT_RELATIVE.parent
    final_name = LOCAL_ROOT_RELATIVE.name
    staging_name = f".{final_name}.partial"
    try:
        held_parent = _HeldDirectory.open(parent)
    except InventoryArchiveError as error:
        raise HighAssuranceCloseoutError(
            "offline closeout local parent is missing or contains a symlink"
        ) from error
    parent_observed = os.fstat(held_parent.descriptor)
    if parent_observed.st_uid != os.getuid():
        held_parent.close()
        raise HighAssuranceCloseoutError("offline closeout local parent is not user-owned")
    staging_fd = -1
    try:
        for name in (final_name, staging_name):
            try:
                os.stat(name, dir_fd=held_parent.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise HighAssuranceCloseoutError("offline closeout local identity is not fresh")
        os.mkdir(staging_name, mode=0o700, dir_fd=held_parent.descriptor)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=held_parent.descriptor,
        )
        members = {
            "canonical-report.json": documents.canonical_report,
            "firewall-baseline.json": documents.private_baseline,
            "offline-adjudication.json": documents.adjudication,
            "raw-global-firewall-response.json": documents.raw_response,
            "restoration-payload.json": documents.restoration_payload,
            "sanitized-structural-report.json": documents.canonical_report,
        }
        for name, encoded in sorted(members.items()):
            _write_exclusive_at(staging_fd, name, encoded)
        manifest = firewall.canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "closeout_id": CLOSEOUT_ID,
                "closeout_state": CLOSEOUT_STATE,
                "implementation_commit": implementation_commit,
                "capture_run_id": firewall.CAPTURE_RUN_ID,
                "capture_run_replay_allowed": False,
                "baseline_alias": documents.baseline_alias,
                "canonical_semantic_sha256": documents.canonical_semantic_sha256,
                "restoration_payload_alias": documents.restoration_payload_alias,
                "restoration_payload_sha256": documents.restoration_payload_sha256,
                "files": [
                    {"path": name, "bytes": len(encoded), "sha256": firewall.sha256_bytes(encoded)}
                    for name, encoded in sorted(members.items())
                ],
            }
        )
        local_seal = firewall.canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "closeout_id": CLOSEOUT_ID,
                "manifest_sha256": firewall.sha256_bytes(manifest),
                "baseline_alias": documents.baseline_alias,
                "canonical_semantic_sha256": documents.canonical_semantic_sha256,
                "restoration_payload_alias": documents.restoration_payload_alias,
                "restoration_payload_sha256": documents.restoration_payload_sha256,
                "capture_ledger_sha256": CAPTURE_LEDGER_SHA256,
                "capture_raw_response_sha256": CAPTURE_RAW_SHA256,
                "original_capture_unchanged": True,
                "source_retained": True,
                "cloud_mutation_occurred": False,
                "external_request_during_closeout": False,
            }
        )
        _write_exclusive_at(staging_fd, "BASELINE_MANIFEST.json", manifest)
        _write_exclusive_at(staging_fd, "BASELINE_SEAL.json", local_seal)
        os.fsync(staging_fd)
        os.rename(
            staging_name,
            final_name,
            src_dir_fd=held_parent.descriptor,
            dst_dir_fd=held_parent.descriptor,
        )
        os.fsync(held_parent.descriptor)
        return (
            parent / final_name,
            {**members, "BASELINE_MANIFEST.json": manifest, "BASELINE_SEAL.json": local_seal},
            manifest,
            local_seal,
        )
    except (OSError, InventoryArchiveError) as error:
        raise HighAssuranceCloseoutError("offline closeout local seal failed") from error
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        held_parent.close()


def materialize_authoritative_baseline(
    repository_root: Path,
    *,
    implementation_commit: str,
    volume_observer: Callable[[], tuple[VolumeObservation, VolumeObservation]] | None = None,
    entropy: Callable[[int], bytes] = secrets.token_bytes,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> AuthoritativeFirewallSeal:
    """Create and externally seal the one offline authoritative baseline bundle."""

    started = time.monotonic()
    root = repository_root.resolve(strict=True)
    if (
        firewall._git(root, "branch", "--show-current") != "phase-1/sira-smoke-lambda"
        or firewall._git(root, "rev-parse", "HEAD") != implementation_commit
        or firewall._git(root, "status", "--short")
    ):
        raise HighAssuranceCloseoutError("closeout materialization requires its exact clean commit")
    verify_scientific_locks(root)
    documents = adjudicate_capture_run(root)
    committed_adjudication = firewall._read_regular_no_follow(
        root / PUBLIC_ADJUDICATION_RELATIVE,
        max_bytes=262_144,
    )
    committed_report = firewall._read_regular_no_follow(
        root / PUBLIC_STRUCTURAL_REPORT_RELATIVE,
        max_bytes=262_144,
    )
    if committed_adjudication != documents.adjudication or committed_report != (
        documents.canonical_report
    ):
        raise HighAssuranceCloseoutError("committed public closeout evidence drifted")
    local_root, local_members, manifest, local_seal = _create_local_bundle(
        root,
        documents,
        implementation_commit=implementation_commit,
    )
    if sum(len(value) for value in local_members.values()) > MAX_CLOSEOUT_BUNDLE_BYTES:
        raise HighAssuranceCloseoutError("offline closeout local bundle exceeds its cap")
    random_identity = entropy(16)
    if len(random_identity) != 16:
        raise HighAssuranceCloseoutError("offline closeout archive entropy is invalid")
    archive_identity = f"{CLOSEOUT_ID}-{random_identity.hex()}"
    staging_name = f".{archive_identity}.partial"
    archive_alias = f"l2m-firewall-closeout-{firewall.sha256_bytes(manifest)[:12]}"
    archive_root_path = APPROVED_MOUNT / "GIC-Lab/t07/sealed-artifacts"
    observer = DiskutilVolumeObserver() if volume_observer is None else volume_observer
    external_mount: _HeldDirectory | None = None
    system_mount: _HeldDirectory | None = None
    repository_handle: _HeldDirectory | None = None
    archive_root: _HeldDirectory | None = None
    staging_fd = -1
    try:
        external_pre, system_pre = observer()
        external_floor = _validate_external(
            external_pre,
            incremental_bytes=MAX_CLOSEOUT_BUNDLE_BYTES,
        )
        _validate_system(system_pre, floor_bytes=firewall.MIN_LOCAL_PREWRITE_FREE_BYTES)
        external_mount = _HeldDirectory.open(APPROVED_MOUNT)
        system_mount = _HeldDirectory.open(SYSTEM_DATA_MOUNT)
        repository_handle = _HeldDirectory.open(root)
        if external_mount.device == system_mount.device or repository_handle.device != (
            system_mount.device
        ):
            raise HighAssuranceCloseoutError("offline closeout topology drifted")
        archive_root = _open_or_create_archive_root(external_mount, archive_root_path)
        if archive_root.device != external_mount.device:
            raise HighAssuranceCloseoutError("offline closeout used an internal fallback")
        for name in (archive_identity, staging_name):
            try:
                os.stat(name, dir_fd=archive_root.descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise HighAssuranceCloseoutError("offline closeout archive identity is not fresh")
        os.mkdir(staging_name, mode=0o700, dir_fd=archive_root.descriptor)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_root.descriptor,
        )
        for name, encoded in sorted(local_members.items()):
            _write_exclusive_at(staging_fd, name, encoded)
        copy_record = firewall.canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "action": "t07-high-assurance-firewall-closeout-copy",
                "closeout_id": CLOSEOUT_ID,
                "archive_alias": archive_alias,
                "copied_at_utc": utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "files": [
                    {"path": name, "bytes": len(encoded), "sha256": firewall.sha256_bytes(encoded)}
                    for name, encoded in sorted(local_members.items())
                ],
                "external_volume_uuid": external_pre.volume_uuid.upper(),
                "external_physical_store_uuid": (external_pre.physical_store_uuid or "").upper(),
                "external_retained_floor_bytes": external_floor,
                "source_retained": True,
                "destination_hashes_verified": True,
                "held_no_follow_descriptors": True,
                "atomic_finalization": True,
                "internal_fallback": False,
            }
        )
        external_seal = firewall.canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "closeout_id": CLOSEOUT_ID,
                "closeout_state": CLOSEOUT_STATE,
                "bounded_fork_state": BOUNDED_FORK_STATE,
                "archive_alias": archive_alias,
                "local_seal_sha256": firewall.sha256_bytes(local_seal),
                "copy_record_sha256": firewall.sha256_bytes(copy_record),
                "baseline_alias": documents.baseline_alias,
                "canonical_semantic_sha256": documents.canonical_semantic_sha256,
                "restoration_payload_alias": documents.restoration_payload_alias,
                "restoration_payload_sha256": documents.restoration_payload_sha256,
                "source_retained": True,
                "destination_hashes_verified": True,
                "cloud_mutation_occurred": False,
                "external_request_during_closeout": False,
            }
        )
        if (
            sum(len(value) for value in local_members.values())
            + len(copy_record)
            + len(external_seal)
            > MAX_CLOSEOUT_BUNDLE_BYTES
        ):
            raise HighAssuranceCloseoutError("offline closeout external bundle exceeds its cap")
        _write_exclusive_at(staging_fd, "COPY_RECORD.json", copy_record)
        _write_exclusive_at(staging_fd, "SEAL.json", external_seal)
        os.fsync(staging_fd)
        os.fchmod(staging_fd, 0o500)
        os.rename(
            staging_name,
            archive_identity,
            src_dir_fd=archive_root.descriptor,
            dst_dir_fd=archive_root.descriptor,
        )
        os.fsync(archive_root.descriptor)
        final_fd = os.open(
            archive_identity,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=archive_root.descriptor,
        )
        try:
            for name, expected in {
                **local_members,
                "COPY_RECORD.json": copy_record,
                "SEAL.json": external_seal,
            }.items():
                observed = _read_regular_at(
                    final_fd,
                    name,
                    max_bytes=MAX_CLOSEOUT_BUNDLE_BYTES,
                )
                if observed != expected or firewall.sha256_bytes(observed) != (
                    firewall.sha256_bytes(expected)
                ):
                    raise HighAssuranceCloseoutError(
                        "offline closeout destination verification failed"
                    )
        finally:
            os.close(final_fd)
        external_post, system_post = observer()
        if not _same_identity(external_pre, external_post) or not _same_identity(
            system_pre, system_post
        ):
            raise HighAssuranceCloseoutError("offline closeout storage identity changed")
        _validate_external(external_post, incremental_bytes=0)
        _validate_system(system_post, floor_bytes=firewall.MIN_LOCAL_RETAINED_FREE_BYTES)
        if external_post.free_bytes < external_floor:
            raise HighAssuranceCloseoutError("offline closeout retained floor failed")
        if time.monotonic() - started > MAX_CLOSEOUT_WALL_SECONDS:
            raise HighAssuranceCloseoutError("offline closeout wall cap exceeded")
        local_verification = firewall.canonical_json_bytes(
            {
                "schema_version": "0.1.0",
                "closeout_id": CLOSEOUT_ID,
                "archive_alias": archive_alias,
                "external_copy_record_sha256": firewall.sha256_bytes(copy_record),
                "external_seal_sha256": firewall.sha256_bytes(external_seal),
                "source_retained": True,
                "destination_hashes_verified": True,
                "internal_fallback": False,
            }
        )
        local_fd = os.open(
            local_root,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            _write_exclusive_at(local_fd, "EXTERNAL_COPY_VERIFICATION.json", local_verification)
            os.fsync(local_fd)
        finally:
            os.close(local_fd)
        if (
            firewall.sha256_bytes(
                firewall._read_regular_no_follow(
                    root / firewall.CAPTURE_LEDGER_RELATIVE,
                    max_bytes=MAX_CLOSEOUT_BUNDLE_BYTES,
                )
            )
            != CAPTURE_LEDGER_SHA256
            or firewall.sha256_bytes(
                firewall._read_regular_no_follow(
                    root / firewall.CAPTURE_RUN_ROOT_RELATIVE / "raw-global-firewall-response.json",
                    max_bytes=MAX_CLOSEOUT_BUNDLE_BYTES,
                )
            )
            != CAPTURE_RAW_SHA256
        ):
            raise HighAssuranceCloseoutError("burned capture changed during closeout")
        return AuthoritativeFirewallSeal(
            documents.baseline_alias,
            documents.canonical_semantic_sha256,
            documents.restoration_payload_alias,
            documents.restoration_payload_sha256,
            firewall.sha256_bytes(local_seal),
            archive_alias,
            firewall.sha256_bytes(copy_record),
            firewall.sha256_bytes(external_seal),
            True,
            True,
            local_root,
            archive_root_path / archive_identity,
        )
    except (OSError, InventoryArchiveError) as error:
        raise HighAssuranceCloseoutError("offline closeout archive failed") from error
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        for handle in (archive_root, repository_handle, system_mount, external_mount):
            if handle is not None:
                handle.close()


def private_output_names() -> frozenset[str]:
    """Names that privacy scans must reject from Git/public surfaces."""

    return frozenset(
        {
            "firewall-baseline.json",
            "raw-global-firewall-response.json",
            "restoration-payload.json",
        }
    )


def assert_private_output_not_tracked(repository_root: Path) -> None:
    root = repository_root.resolve(strict=True)
    tracked = set(firewall._git(root, "ls-files").splitlines())
    if any(Path(path).name in private_output_names() for path in tracked):
        raise HighAssuranceCloseoutError("private firewall output entered Git")
    local = root / LOCAL_ROOT_RELATIVE
    if local.exists():
        observed = local.lstat()
        if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode):
            raise HighAssuranceCloseoutError("private closeout root is unsafe")
