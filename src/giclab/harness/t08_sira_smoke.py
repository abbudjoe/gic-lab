"""Offline T08 adjudication of the retained T07 pragmatic SiRA smoke.

This module has no network, provider, browser, container, or subprocess surface. It
accepts only already-retained local evidence, verifies content identities, and builds
sanitized machine-readable adjudication records. Private filesystem roots and secret
values are never serialized into its outputs.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import stat
import tarfile
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, cast

from giclab.registry import load_json, load_yaml, loads_json

Provenance = Literal["observed", "derived", "inferred", "unavailable"]

SCHEMA_VERSION: Final = "0.1.0"
HOST_RUN_ID: Final = "RUN-T07-PRAGMATIC-HOST-0002"
REACTIVE_RUN_ID: Final = "RUN-T07-PRAGMATIC-SIRA-REACTIVE-0002"
SIMULATIVE_RUN_ID: Final = "RUN-T07-PRAGMATIC-SIRA-SIMULATIVE-0002"
FROZEN_GICLAB_COMMIT: Final = "5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23"
SIRA_COMMIT: Final = "93fb8d72de71f9a4a13419670adeb34d93cf7acd"
SIRA_TREE: Final = "6a6d9068b94d7632d3533a3d6f013d4de6ff76e8"
MODEL_SNAPSHOT: Final = "gpt-4o-2024-11-20"
RUN_MANIFEST_SHA256: Final = "877c26d16e242733e4f86afc54a058b868ca79ee27b826abc5e1e92ae0427ccd"
REACTIVE_STATUS_SHA256: Final = "bcacad4492d42035dc4c2c661e0eff6c3fdadc20e9ce1f63810140771968cced"
SIMULATIVE_STATUS_SHA256: Final = "2f03756fb582c32d1f7b1fc27f6843d6b2eac0d9e4198eafdd1a02f9cd330bc5"
REMOTE_ARCHIVE_SHA256: Final = "4deebc0477581377e2bbb71a8f075bf8b3712188865f0e1faa5c0e7f62dc0450"
REMOTE_MANIFEST_SHA256: Final = "7042a079bccdd6ff4dfdade4c954fd6e403f2c7d6e0cb39c725d4414835a61b1"
LOCAL_MANIFEST_SHA256: Final = "b2576a030ffa56c1b2e3b0b111e9dce71b999cb12acba8add6a78483974b4652"
EXTERNAL_MANIFEST_SHA256: Final = "9fb9ee63c1703e9701e8d5168284a1f757181baadd68a1508095eeac5fc7a167"
TRACKED_SUMMARY_SHA256: Final = "ec1e2fb0a8e04997b4a87f9f2a898f597b70440b1df4f8a9dfba1da67ef5321c"
FROZEN_PROTOCOL_SHA256: Final = "5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c"
FROZEN_CONFIG_SHA256: Final = "f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d"
ROUTING_SHA256: Final = "8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619"

REMOTE_ARCHIVE_RELATIVE: Final = Path("remote-evidence/t07-pragmatic-evidence.tar.gz")
REMOTE_MANIFEST_RELATIVE: Final = Path("remote-evidence/evidence-manifest.json")
LOCAL_MANIFEST_RELATIVE: Final = Path("LOCAL_SHA256SUMS.json")
EXTERNAL_MANIFEST_NAME: Final = "FINAL_SHA256SUMS.json"
MAX_ARCHIVE_FILES: Final = 512
MAX_ARCHIVE_MEMBER_BYTES: Final = 268_435_456
MAX_ARCHIVE_TOTAL_BYTES: Final = 536_870_912

INPUT_RATE: Final = Decimal("2.50")
CACHED_INPUT_RATE: Final = Decimal("1.25")
OUTPUT_RATE: Final = Decimal("10.00")
MILLION: Final = Decimal(1_000_000)

_EXPECTED_SENSITIVE_PROVIDER_FIELDS: Final = frozenset({"jupyter_token", "jupyter_url"})


class T08EvidenceError(ValueError):
    """Retained T07 evidence violates the T08 reconstruction contract."""


def sha256_bytes(encoded: bytes) -> str:
    """Return the lowercase SHA-256 digest of bytes."""

    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash one regular, non-symlink file without following path substitutions."""

    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise T08EvidenceError(f"evidence path is not a regular non-symlink file: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(document: object) -> bytes:
    """Encode one deterministic, finite JSON document."""

    return (
        json.dumps(
            document,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise T08EvidenceError(f"{context} must be a JSON object with string keys")
    return cast(dict[str, Any], value)


def _sequence(value: object, *, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise T08EvidenceError(f"{context} must be a JSON array")
    return value


def _string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise T08EvidenceError(f"{context} must be a nonempty string")
    return value


def _integer(value: object, *, context: str) -> int:
    if type(value) is not int or value < 0:
        raise T08EvidenceError(f"{context} must be a nonnegative integer")
    return value


def _number(value: object, *, context: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise T08EvidenceError(f"{context} must be a finite nonnegative number")
    return value


def _safe_relative_path(value: object, *, context: str) -> str:
    text = _string(value, context=context)
    path = PurePosixPath(text)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise T08EvidenceError(f"{context} is not a safe relative path")
    return path.as_posix()


def evidence_field(
    value: object,
    provenance: Provenance,
    *evidence_refs: str,
    note: str | None = None,
) -> dict[str, object]:
    """Wrap one reconstructed value with explicit field-level provenance."""

    if provenance == "unavailable" and value is not None:
        raise T08EvidenceError("unavailable evidence fields must have a null value")
    if provenance != "unavailable" and not evidence_refs:
        raise T08EvidenceError("available evidence fields require at least one evidence reference")
    document: dict[str, object] = {
        "value": value,
        "provenance": provenance,
        "evidence_refs": list(evidence_refs),
    }
    if note is not None:
        document["note"] = note
    return document


def _json_value(encoded: bytes, *, context: str) -> Any:
    try:
        return loads_json(encoded)
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, T08EvidenceError):
            raise
        raise T08EvidenceError(f"{context} is not strict JSON") from exc


def _json_object(encoded: bytes, *, context: str) -> dict[str, Any]:
    return _mapping(_json_value(encoded, context=context), context=context)


def _archive_members(archive_path: Path) -> dict[str, bytes]:
    """Read a bounded regular-file-only tar archive without extracting it."""

    if sha256_file(archive_path) != REMOTE_ARCHIVE_SHA256:
        raise T08EvidenceError("remote evidence archive SHA-256 drifted")
    files: dict[str, bytes] = {}
    total = 0
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_ARCHIVE_FILES:
                raise T08EvidenceError("remote evidence archive file count is invalid")
            for member in members:
                relative = _safe_relative_path(member.name, context="archive member path")
                if not member.isfile() or member.issym() or member.islnk():
                    raise T08EvidenceError("remote evidence archive contains a non-regular member")
                if relative in files:
                    raise T08EvidenceError("remote evidence archive repeats a member path")
                if member.size < 0 or member.size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise T08EvidenceError("remote evidence archive member size is invalid")
                total += member.size
                if total > MAX_ARCHIVE_TOTAL_BYTES:
                    raise T08EvidenceError("remote evidence archive exceeds the offline size cap")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise T08EvidenceError("remote evidence archive member cannot be read")
                encoded = extracted.read(member.size + 1)
                if len(encoded) != member.size:
                    raise T08EvidenceError("remote evidence archive member size drifted")
                files[relative] = encoded
    except (OSError, tarfile.TarError) as exc:
        if isinstance(exc, T08EvidenceError):
            raise
        raise T08EvidenceError("remote evidence archive cannot be read") from exc
    return files


def verify_archive_manifest(files: Mapping[str, bytes]) -> dict[str, int]:
    """Verify every archive payload entry against its internal hash manifest."""

    manifest_encoded = files.get("evidence-manifest.json")
    if manifest_encoded is None:
        raise T08EvidenceError("remote archive omits evidence-manifest.json")
    if sha256_bytes(manifest_encoded) != REMOTE_MANIFEST_SHA256:
        raise T08EvidenceError("remote evidence manifest SHA-256 drifted")
    manifest = _json_object(manifest_encoded, context="remote evidence manifest")
    entries = _sequence(manifest.get("files"), context="remote evidence manifest files")
    expected_paths: set[str] = set()
    expected_total = 0
    for raw in entries:
        entry = _mapping(raw, context="remote evidence manifest entry")
        if set(entry) != {"bytes", "path", "sha256"}:
            raise T08EvidenceError("remote evidence manifest entry field set drifted")
        relative = _safe_relative_path(entry.get("path"), context="remote manifest path")
        if relative in expected_paths or relative == "evidence-manifest.json":
            raise T08EvidenceError("remote evidence manifest repeats or self-lists a path")
        expected_paths.add(relative)
        size = _integer(entry.get("bytes"), context=f"remote manifest bytes for {relative}")
        digest = _string(entry.get("sha256"), context=f"remote manifest hash for {relative}")
        encoded = files.get(relative)
        if encoded is None or len(encoded) != size or sha256_bytes(encoded) != digest:
            raise T08EvidenceError(f"remote evidence payload drifted: {relative}")
        expected_total += size
    if expected_paths != set(files) - {"evidence-manifest.json"}:
        raise T08EvidenceError("remote evidence manifest coverage drifted")
    if manifest.get("total_bytes") != expected_total:
        raise T08EvidenceError("remote evidence manifest total bytes drifted")
    return {"file_count": len(entries), "total_bytes": expected_total, "mismatches": 0}


def verify_filesystem_manifest(
    root: Path,
    manifest: Mapping[str, Any],
    *,
    context: str,
) -> dict[str, int]:
    """Rehash a retained filesystem tree against a bounded JSON file manifest."""

    entries = _sequence(manifest.get("files"), context=f"{context} files")
    expected_count = _integer(manifest.get("file_count"), context=f"{context} file_count")
    expected_total = _integer(manifest.get("total_bytes"), context=f"{context} total_bytes")
    if len(entries) != expected_count:
        raise T08EvidenceError(f"{context} file count drifted")
    seen: set[str] = set()
    observed_total = 0
    for raw in entries:
        entry = _mapping(raw, context=f"{context} entry")
        if set(entry) != {"bytes", "path", "sha256"}:
            raise T08EvidenceError(f"{context} entry field set drifted")
        relative = _safe_relative_path(entry.get("path"), context=f"{context} path")
        if relative in seen:
            raise T08EvidenceError(f"{context} repeats a path")
        seen.add(relative)
        parts = PurePosixPath(relative).parts
        path = root.joinpath(*parts)
        try:
            current = root
            for part in parts[:-1]:
                current = current / part
                parent_metadata = current.lstat()
                if not stat.S_ISDIR(parent_metadata.st_mode) or current.is_symlink():
                    raise T08EvidenceError(
                        f"{context} path traverses a non-directory or symlink: {relative}"
                    )
            metadata = path.lstat()
        except OSError as exc:
            raise T08EvidenceError(f"{context} path is missing: {relative}") from exc
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise T08EvidenceError(f"{context} path is not a regular file: {relative}")
        size = _integer(entry.get("bytes"), context=f"{context} bytes for {relative}")
        digest = _string(entry.get("sha256"), context=f"{context} hash for {relative}")
        if metadata.st_size != size or sha256_file(path) != digest:
            raise T08EvidenceError(f"{context} payload drifted: {relative}")
        observed_total += size
    if observed_total != expected_total:
        raise T08EvidenceError(f"{context} byte total drifted")
    return {"file_count": len(entries), "total_bytes": observed_total, "mismatches": 0}


def recompute_cost(
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Recompute GPT-4o cost using the frozen T07 rate schedule."""

    if min(input_tokens, cached_input_tokens, output_tokens) < 0:
        raise T08EvidenceError("token counts must be nonnegative")
    if cached_input_tokens > input_tokens:
        raise T08EvidenceError("cached input tokens exceed input tokens")
    uncached = input_tokens - cached_input_tokens
    return (
        Decimal(uncached) * INPUT_RATE
        + Decimal(cached_input_tokens) * CACHED_INPUT_RATE
        + Decimal(output_tokens) * OUTPUT_RATE
    ) / MILLION


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _condition_documents(
    archive_files: Mapping[str, bytes],
    mode: str,
) -> dict[str, Any]:
    prefix = f"evidence/{mode}"
    documents: dict[str, Any] = {}
    for name in (
        "condition-started.json",
        "condition-status.json",
        "container-inspect.json",
        "provider-budget.json",
        "runtime-cleanup.json",
        "runtime-environment.json",
    ):
        relative = f"{prefix}/{name}"
        encoded = archive_files.get(relative)
        if encoded is None:
            raise T08EvidenceError(f"condition evidence is missing: {relative}")
        documents[name] = (
            _json_value(encoded, context=relative)
            if name == "container-inspect.json"
            else _json_object(encoded, context=relative)
        )
    sessions = sorted(
        relative
        for relative in archive_files
        if relative.startswith(f"{prefix}/sira-output/") and relative.endswith(".json")
    )
    if len(sessions) != 1:
        raise T08EvidenceError(f"{mode} must retain exactly one session JSON")
    documents["session_path"] = sessions[0]
    documents["session.json"] = _json_object(
        archive_files[sessions[0]], context=f"{mode} session JSON"
    )
    return documents


def _validate_session(session: Mapping[str, Any], *, query: str, max_steps: int) -> None:
    if session.get("goal") != query:
        raise T08EvidenceError("session goal contradicts the frozen query")
    if session.get("instance_id") is not None:
        raise T08EvidenceError("open-query session has a non-null instance identity")
    if type(session.get("is_complete")) is not bool or not isinstance(session.get("error"), str):
        raise T08EvidenceError("session terminal fields are malformed")
    history = _sequence(session.get("history"), context="session history")
    if len(history) > max_steps:
        raise T08EvidenceError("session history exceeds the frozen browser-step cap")
    for index, raw in enumerate(history):
        item = _sequence(raw, context=f"session history item {index}")
        if len(item) != 3 or not isinstance(item[0], dict) or not isinstance(item[1], str):
            raise T08EvidenceError(f"session history item {index} is malformed")
        step = _mapping(item[2], context=f"session history step {index}")
        if step.get("action") != item[1]:
            raise T08EvidenceError(f"session action duplication drifted at step {index}")
    expected_complete = bool(history) and cast(str, history[-1][1]).startswith("send_msg_to_user")
    if session.get("is_complete") is not expected_complete:
        raise T08EvidenceError("session is_complete contradicts its final requested action")


def _screenshot_record(session: Mapping[str, Any]) -> dict[str, object]:
    history = _sequence(session.get("history"), context="session history")
    if not history:
        return {"count": 0, "embedded_format": None, "decoded_bytes": 0, "sha256": None}
    first = _sequence(history[0], context="session first history item")
    observation = _mapping(first[0], context="session first observation")
    screenshot = _string(observation.get("screenshot"), context="embedded screenshot")
    try:
        decoded = base64.b64decode(screenshot, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise T08EvidenceError("embedded screenshot is not valid base64") from exc
    if not decoded.startswith(b"\xff\xd8\xff"):
        raise T08EvidenceError("embedded screenshot is not a JPEG")
    return {
        "count": 1,
        "embedded_format": "jpeg",
        "decoded_bytes": len(decoded),
        "sha256": sha256_bytes(decoded),
    }


def _mode_configuration(mode: str) -> dict[str, object]:
    if mode == "reactive":
        return {
            "config_name": "web_reactive",
            "planner_type": "policy",
            "base_temperature": 0.0,
            "base_top_p": 0.5,
        }
    if mode == "simulative":
        return {
            "config_name": "web_simulative",
            "planner_type": "world_model",
            "planner_search_num_actions": 5,
            "planner_search_depth": 1,
            "planner_policy_num_samples": 20,
            "planner_critic_num_samples": 20,
            "policy_temperature": 1.0,
            "policy_top_p": 0.95,
            "critic_temperature": 1.0,
            "critic_top_p": 0.95,
            "realized_planner_branch": "one_cluster_direct_selection",
        }
    raise T08EvidenceError("condition mode is invalid")


def _model_call_sequence(mode: str, call_count: int) -> dict[str, object]:
    if mode == "reactive" and call_count == 4:
        return {
            "attempt_count": 4,
            "sequence": [
                {"ordinal": 1, "role": "encoder", "purpose": "state"},
                {"ordinal": 2, "role": "policy", "purpose": "intent/plan"},
                {"ordinal": 3, "role": "actor", "purpose": "action"},
                {"ordinal": 4, "role": "memory", "purpose": "memory_update"},
            ],
            "sequence_completeness": "derived_complete_from_four_distinct_debug_logs",
        }
    if mode == "simulative" and call_count == 5:
        return {
            "attempt_count": 5,
            "sequence": [
                {"ordinal": 1, "role": "encoder", "purpose": "state"},
                {"ordinal": 2, "role": "policy", "purpose": "twenty_policy_samples"},
                {
                    "ordinal": 3,
                    "role": None,
                    "purpose": "one_cluster_planner_processing",
                },
                {"ordinal": 4, "role": "actor", "purpose": "action"},
                {"ordinal": 5, "role": "memory", "purpose": "memory_update"},
            ],
            "sequence_completeness": (
                "inferred_order; one call's exact role and per-call receipt are unavailable"
            ),
        }
    raise T08EvidenceError("condition model-call count does not match the retained smoke")


def _regulation_record(mode: str, session_path: str) -> dict[str, object]:
    return {
        "decision_id": "REG-SIRA-MODE-ASSIGNMENT",
        "source_kind": "experiment_assignment",
        "policy_id": "SIRA-REACTIVE-SIMULATIVE-EXPERIMENT-ASSIGNMENT",
        "policy_revision": FROZEN_PROTOCOL_SHA256,
        "available_modes": ["reactive", "simulative"],
        "selected_mode": mode,
        "confidence": None,
        "override": None,
        "fallback": None,
        "causal_parent_event_sequences": [],
        "raw_artifact_refs": [f"remote_archive:{session_path}"],
        "resolved_configuration_refs": [
            "remote_archive:run-manifest.json",
            "repository:docs/audits/sira/COMMAND_CONTRACT.yaml",
        ],
        "field_provenance": {
            "decision_id": "derived",
            "source_kind": "derived",
            "policy_id": "derived",
            "policy_revision": "derived",
            "available_modes": "derived",
            "selected_mode": "derived",
            "confidence": "unavailable",
            "override": "unavailable",
            "fallback": "unavailable",
            "causal_parent_event_sequences": "unavailable",
            "raw_artifact_refs": "observed",
            "resolved_configuration_refs": "derived",
        },
    }


def _normalized_events(session: Mapping[str, Any], mode: str) -> list[dict[str, object]]:
    history = _sequence(session.get("history"), context="session history")
    events: list[dict[str, object]] = [
        {
            "event_type": "regulation_decision",
            "source": "sira-adapter-resolved-configuration",
            "provenance": "derived",
            "selected_mode": mode,
        }
    ]
    for index, raw in enumerate(history):
        item = _sequence(raw, context=f"session history item {index}")
        step = _mapping(item[2], context=f"session history step {index}")
        events.append(
            {
                "event_type": "observation",
                "source": "sira-session-json",
                "provenance": "observed",
                "step_index": index,
            }
        )
        if isinstance(step.get("state"), str):
            events.append(
                {
                    "event_type": "belief_state",
                    "source": "sira-session-json",
                    "provenance": "observed",
                    "step_index": index,
                    "semantic_caveat": "natural-language upstream state; not GIC state",
                }
            )
        if isinstance(step.get("plan"), str):
            events.append(
                {
                    "event_type": "plan",
                    "source": "sira-session-json",
                    "provenance": "observed",
                    "step_index": index,
                }
            )
        events.append(
            {
                "event_type": "requested_action",
                "source": "sira-session-json",
                "provenance": "observed",
                "step_index": index,
                "semantic_caveat": (
                    "requested action only; actual performance is inferred from normal exit "
                    "because no structured execution result was retained"
                ),
            }
        )
    events.append(
        {
            "event_type": "outcome",
            "source": "sira-session-json",
            "provenance": "observed",
            "source_is_complete": session.get("is_complete"),
            "source_error_present": bool(session.get("error")),
            "scientific_outcome": None,
        }
    )
    return events


def _condition_reconstruction(
    *,
    mode: str,
    manifest: Mapping[str, Any],
    documents: Mapping[str, Any],
    archive_files: Mapping[str, bytes],
) -> dict[str, object]:
    conditions = _mapping(manifest.get("conditions"), context="run manifest conditions")
    config = _mapping(conditions.get(mode), context=f"run manifest {mode} configuration")
    manifest_runtime = _mapping(manifest.get("runtime"), context="run manifest runtime")
    started = _mapping(documents["condition-started.json"], context=f"{mode} start")
    status = _mapping(documents["condition-status.json"], context=f"{mode} status")
    budget = _mapping(documents["provider-budget.json"], context=f"{mode} budget")
    runtime = _mapping(documents["runtime-environment.json"], context=f"{mode} runtime")
    cleanup = _mapping(documents["runtime-cleanup.json"], context=f"{mode} cleanup")
    inspect = _sequence(documents["container-inspect.json"], context=f"{mode} inspect")
    if len(inspect) != 1:
        raise T08EvidenceError(f"{mode} container inspect must contain exactly one record")
    inspect_record = _mapping(
        inspect[0],
        context=f"{mode} container inspect record",
    )
    inspect_config = _mapping(inspect_record.get("Config"), context=f"{mode} container config")
    inspect_host_config = _mapping(
        inspect_record.get("HostConfig"), context=f"{mode} container host config"
    )
    inspect_restart_policy = _mapping(
        inspect_host_config.get("RestartPolicy"), context=f"{mode} restart policy"
    )
    inspect_state = _mapping(inspect_record.get("State"), context=f"{mode} container state")
    session = _mapping(documents["session.json"], context=f"{mode} session")
    session_path = _string(documents["session_path"], context=f"{mode} session path")
    task = _mapping(manifest.get("task"), context="run manifest task")
    query = _string(task.get("query"), context="run manifest query")
    max_steps = _integer(task.get("max_steps"), context="run manifest max_steps")
    _validate_session(session, query=query, max_steps=max_steps)

    expected_condition = f"SIRA-{mode.upper()}"
    if (
        config.get("attempts") != 1
        or config.get("retries") != 0
        or config.get("browser_steps") != max_steps
        or config.get("condition") != expected_condition
    ):
        raise T08EvidenceError(f"{mode} frozen condition contract drifted")
    if (
        started.get("attempt") != 1
        or started.get("condition") != expected_condition
        or started.get("started_at_utc") != status.get("started_at_utc")
        or status.get("attempt") != 1
        or status.get("condition") != expected_condition
        or status.get("condition_attempt_consumed") is not True
        or status.get("empirical_boundary_crossed") is not True
        or status.get("timeout_observed") is not False
        or status.get("container_removed") is not True
    ):
        raise T08EvidenceError(f"{mode} lifecycle evidence drifted")
    _number(status.get("wall_seconds"), context=f"{mode} wall seconds")
    if (
        runtime.get("python_version") != manifest_runtime.get("python_version")
        or runtime.get("routing_sha256") != ROUTING_SHA256
        or runtime.get("runtime_adaptation_sha256")
        != manifest_runtime.get("runtime_adaptation_sha256")
        or runtime.get("architecture") != "x86_64"
        or runtime.get("os") != "Linux"
        or runtime.get("upstream_runner") != "/opt/sira/scripts/run_web_agent.py"
    ):
        raise T08EvidenceError(f"{mode} runtime identity drifted")
    if (
        inspect_record.get("Image") != manifest_runtime.get("built_image_id")
        or inspect_config.get("Image") != manifest_runtime.get("built_image_id")
        or inspect_config.get("WorkingDir") != "/opt/sira"
        or inspect_host_config.get("NetworkMode") != "bridge"
        or inspect_host_config.get("ReadonlyRootfs") is not True
        or inspect_host_config.get("Privileged") is not False
        or inspect_restart_policy.get("Name") != "no"
    ):
        raise T08EvidenceError(f"{mode} container isolation identity drifted")

    usage = _mapping(status.get("usage"), context=f"{mode} status usage")
    for field in (
        "model_call_attempts",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "browser_actions",
        "unreconciled_provider_attempts",
    ):
        if budget.get(field) != usage.get(field):
            raise T08EvidenceError(f"{mode} status and provider ledger disagree on {field}")
    if budget.get("cost_usd") != usage.get("cost_usd"):
        raise T08EvidenceError(f"{mode} status and provider ledger disagree on cost")
    input_tokens = _integer(budget.get("input_tokens"), context=f"{mode} input tokens")
    cached = _integer(budget.get("cached_input_tokens"), context=f"{mode} cached tokens")
    output_tokens = _integer(budget.get("output_tokens"), context=f"{mode} output tokens")
    total_tokens = _integer(budget.get("total_tokens"), context=f"{mode} total tokens")
    if total_tokens != input_tokens + output_tokens:
        raise T08EvidenceError(f"{mode} total tokens do not reconcile")
    reported_cost = Decimal(str(_number(budget.get("cost_usd"), context=f"{mode} cost")))
    recomputed_cost = recompute_cost(
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
    )
    if abs(reported_cost - recomputed_cost) > Decimal("0.000000000001"):
        raise T08EvidenceError(f"{mode} reported cost does not reconcile")
    call_count = _integer(budget.get("model_call_attempts"), context=f"{mode} model call attempts")
    if (
        budget.get("model_revision") != MODEL_SNAPSHOT
        or budget.get("request_service_tier") != "default"
        or budget.get("observed_response_service_tiers") != ["default"]
        or budget.get("default_service_tier_response_count") != call_count
        or budget.get("unreconciled_provider_attempts") != 0
    ):
        raise T08EvidenceError(f"{mode} provider accounting identity drifted")
    history = _sequence(session.get("history"), context=f"{mode} session history")
    browser_actions = _integer(budget.get("browser_actions"), context=f"{mode} browser actions")
    if browser_actions != len(history) or status.get("returncode") != 0:
        raise T08EvidenceError(f"{mode} execution evidence does not reconcile")
    if inspect_state.get("ExitCode") != 0 or inspect_state.get("Running") is not False:
        raise T08EvidenceError(f"{mode} container did not exit normally")
    if cleanup.get("all_environment_closes_succeeded") is not True:
        raise T08EvidenceError(f"{mode} browser environment cleanup failed")

    text_logs = sorted(
        relative
        for relative in archive_files
        if relative.startswith(f"evidence/{mode}/source-logs/") and relative.endswith(".log")
    )
    source_runtime_logs = sorted(
        relative
        for relative in archive_files
        if relative.startswith(f"evidence/{mode}/source-runtime/logs/")
    )
    command = _sequence(config.get("docker_argv"), context=f"{mode} docker argv")
    mode_configuration = _mode_configuration(mode)
    model_roles = {
        role: MODEL_SNAPSHOT
        for role in (
            "default",
            "encoder",
            "memory",
            "policy",
            "world_model",
            "critic",
            "actor",
            "fallback",
        )
    }
    normalized_events = _normalized_events(session, mode)
    regulation = _regulation_record(mode, session_path)
    screenshot = _screenshot_record(session)
    error_text = cast(str, session.get("error"))

    reconstruction = {
        "exact_command": evidence_field(
            command,
            "observed",
            "remote_archive:run-manifest.json",
            f"remote_archive:evidence/{mode}/container-inspect.json",
        ),
        "resolved_configuration": evidence_field(
            {**config, "source_resolved_mode": mode_configuration},
            "derived",
            "remote_archive:run-manifest.json",
            "repository:docs/audits/sira/COMMAND_CONTRACT.yaml",
            "repository:docs/audits/sira/UPSTREAM_AUDIT.md",
            note=(
                "The Docker/budget configuration is observed; source-resolved planner fields "
                "are derived from the pinned SiRA commit and audited mode contract."
            ),
        ),
        "task_query": evidence_field(
            query,
            "observed",
            "remote_archive:run-manifest.json",
            f"remote_archive:{session_path}",
        ),
        "condition_mode": evidence_field(
            mode,
            "observed",
            "remote_archive:run-manifest.json",
            f"remote_archive:evidence/{mode}/container-inspect.json",
        ),
        "working_directory": evidence_field(
            inspect_config.get("WorkingDir"),
            "observed",
            f"remote_archive:evidence/{mode}/container-inspect.json",
        ),
        "environment_identity": evidence_field(
            runtime,
            "observed",
            f"remote_archive:evidence/{mode}/runtime-environment.json",
        ),
        "python_runtime": evidence_field(
            {
                "version": runtime.get("python_version"),
                "executable": runtime.get("python_executable"),
                "executable_sha256": manifest_runtime.get("python_executable_sha256"),
            },
            "observed",
            f"remote_archive:evidence/{mode}/runtime-environment.json",
            "remote_archive:run-manifest.json",
        ),
        "container_image": evidence_field(
            {
                "image_id": inspect_record.get("Image"),
                "base_image": manifest_runtime.get("base_image"),
            },
            "observed",
            f"remote_archive:evidence/{mode}/container-inspect.json",
            "remote_archive:run-manifest.json",
        ),
        "model_revision_by_role": evidence_field(
            {"routing_sha256": ROUTING_SHA256, "routes": model_roles},
            "derived",
            f"remote_archive:evidence/{mode}/runtime-environment.json",
            "repository:src/giclab/harness/sira_gate_a.py@frozen-commit",
        ),
        "service_tier": evidence_field(
            {
                "requested": budget.get("request_service_tier"),
                "returned_values": budget.get("observed_response_service_tiers"),
                "returned_response_count": budget.get("default_service_tier_response_count"),
                "per_call_assignment": None,
            },
            "observed",
            f"remote_archive:evidence/{mode}/provider-budget.json",
            note="Tier totals are observed; individual response receipts were not retained.",
        ),
        "maximum_browser_steps": evidence_field(
            max_steps,
            "observed",
            "remote_archive:run-manifest.json",
        ),
        "start_timestamp": evidence_field(
            status.get("started_at_utc"),
            "observed",
            f"remote_archive:evidence/{mode}/condition-status.json",
        ),
        "stop_timestamp": evidence_field(
            status.get("finished_at_utc"),
            "observed",
            f"remote_archive:evidence/{mode}/condition-status.json",
        ),
        "terminal_status": evidence_field(
            {
                "terminal_state": status.get("terminal_state"),
                "returncode": status.get("returncode"),
                "container_state": inspect_state.get("Status"),
                "container_exit_code": inspect_state.get("ExitCode"),
            },
            "observed",
            f"remote_archive:evidence/{mode}/condition-status.json",
            f"remote_archive:evidence/{mode}/container-inspect.json",
        ),
        "model_call_sequence": evidence_field(
            _model_call_sequence(mode, call_count),
            "derived" if mode == "reactive" else "inferred",
            f"remote_archive:evidence/{mode}/provider-budget.json",
            f"remote_archive:evidence/{mode}/source-logs/agent",
            f"remote_archive:evidence/{mode}/source-logs/debug",
            note="No per-call provider request/response receipt was retained.",
        ),
        "provider_usage_records": evidence_field(
            {
                "condition_aggregate": budget,
                "per_call_usage": None,
                "per_call_latency": None,
                "per_call_cost": None,
            },
            "observed",
            f"remote_archive:evidence/{mode}/provider-budget.json",
        ),
        "browser_actions": evidence_field(
            {
                "recorded_request_count": browser_actions,
                "requested_actions": [cast(list[Any], item)[1] for item in history],
                "performance": "inferred_from_normal_exit",
                "structured_execution_results": None,
            },
            "inferred",
            f"remote_archive:{session_path}",
            f"remote_archive:evidence/{mode}/provider-budget.json",
            f"remote_archive:evidence/{mode}/condition-status.json",
            note=(
                "The requested action and ledger count are observed records, but the runtime "
                "derives that count from session history before env.step. With no post-action "
                "result, actual performance is inferred from normal process exit."
            ),
        ),
        "output_locations": evidence_field(
            {
                "attempt_root": f"remote_archive:evidence/{mode}",
                "session_root": f"remote_archive:evidence/{mode}/sira-output",
                "source_log_root": f"remote_archive:evidence/{mode}/source-logs",
            },
            "observed",
            "remote_archive:run-manifest.json",
            "remote_archive:evidence-manifest.json",
        ),
        "session_json": evidence_field(
            {
                "path": f"remote_archive:{session_path}",
                "bytes": len(archive_files[session_path]),
                "sha256": sha256_bytes(archive_files[session_path]),
                "history_items": len(history),
                "is_complete": session.get("is_complete"),
                "error_present": bool(error_text),
            },
            "observed",
            f"remote_archive:{session_path}",
        ),
        "text_logs": evidence_field(
            {
                "source_logs": [f"remote_archive:{item}" for item in text_logs],
                "source_runtime_logs": [
                    {
                        "path": f"remote_archive:{item}",
                        "bytes": len(archive_files[item]),
                    }
                    for item in source_runtime_logs
                ],
                "condition_stdout": f"remote_archive:evidence/{mode}/condition.stdout",
                "condition_stderr": f"remote_archive:evidence/{mode}/condition.stderr",
            },
            "observed",
            "remote_archive:evidence-manifest.json",
        ),
        "screenshots": evidence_field(
            screenshot,
            "observed",
            f"remote_archive:{session_path}#history[0][0].screenshot",
            note="The only screenshot is the pre-action about:blank observation.",
        ),
        "normalized_events": evidence_field(
            normalized_events,
            "derived",
            f"remote_archive:{session_path}",
            "repository:src/giclab/harness/adapters/sira.py@frozen-commit",
            note="T07 did not retain a normalized event stream; T08 derives this view.",
        ),
        "regulation_decision_record": evidence_field(
            regulation,
            "derived",
            "remote_archive:run-manifest.json",
            f"remote_archive:{session_path}",
            "repository:docs/harness/sira/H2K_REGULATION_DECISION_ADDENDUM.yaml",
            note="T07 did not retain a standalone regulation-decision artifact.",
        ),
        "cleanup_record": evidence_field(
            {
                "browser_environment": cleanup,
                "container_removed": status.get("container_removed"),
            },
            "observed",
            f"remote_archive:evidence/{mode}/runtime-cleanup.json",
            f"remote_archive:evidence/{mode}/condition-status.json",
        ),
    }
    return {
        "run_id": REACTIVE_RUN_ID if mode == "reactive" else SIMULATIVE_RUN_ID,
        "artifact_execution": "passed",
        "artifact_execution_basis": {
            "runtime_initialized": evidence_field(
                True,
                "observed",
                f"remote_archive:evidence/{mode}/runtime-environment.json",
                f"remote_archive:evidence/{mode}/condition-started.json",
            ),
            "model_requests_issued": evidence_field(
                call_count > 0,
                "observed",
                f"remote_archive:evidence/{mode}/provider-budget.json",
            ),
            "browser_action_performed": evidence_field(
                True,
                "inferred",
                f"remote_archive:{session_path}",
                f"remote_archive:evidence/{mode}/condition-status.json",
                note=(
                    "One requested action is retained and the process exited normally, but no "
                    "structured post-action result proves env.step completion."
                ),
            ),
            "session_evidence_written": evidence_field(
                True,
                "observed",
                f"remote_archive:{session_path}",
            ),
            "normal_exit": evidence_field(
                True,
                "observed",
                f"remote_archive:evidence/{mode}/condition-status.json",
                f"remote_archive:evidence/{mode}/container-inspect.json",
            ),
            "owned_state_cleanup": evidence_field(
                True,
                "observed",
                f"remote_archive:evidence/{mode}/runtime-cleanup.json",
                f"remote_archive:evidence/{mode}/condition-status.json",
            ),
        },
        "task_completion": "not_observed",
        "session_is_complete": False,
        "reconstruction": reconstruction,
        "accounting": {
            "model_calls": call_count,
            "input_tokens": input_tokens,
            "cached_input_tokens": cached,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "reported_cost_usd_raw": str(budget.get("cost_usd")),
            "recomputed_cost_usd": _decimal_text(recomputed_cost),
            "browser_actions": browser_actions,
            "wall_seconds_raw": str(status.get("wall_seconds")),
            "unreconciled_provider_attempts": budget.get("unreconciled_provider_attempts"),
        },
    }


def build_pair_diff(
    manifest: Mapping[str, Any],
    reactive: Mapping[str, Any],
    simulative: Mapping[str, Any],
    archive_files: Mapping[str, bytes],
) -> dict[str, object]:
    """Recompute the T08 pair comparison from retained resolved records."""

    runtime = _mapping(manifest.get("runtime"), context="run manifest runtime")
    provider = _mapping(manifest.get("provider"), context="run manifest provider")
    reactive_reconstruction = _mapping(
        reactive.get("reconstruction"), context="reactive reconstruction"
    )
    simulative_reconstruction = _mapping(
        simulative.get("reconstruction"), context="simulative reconstruction"
    )
    conditions = _mapping(manifest.get("conditions"), context="run manifest conditions")
    reactive_config = _mapping(conditions.get("reactive"), context="reactive configuration")
    simulative_config = _mapping(conditions.get("simulative"), context="simulative configuration")
    reactive_command = _sequence(
        reactive_config.get("docker_argv"), context="reactive Docker command"
    )
    simulative_command = _sequence(
        simulative_config.get("docker_argv"), context="simulative Docker command"
    )

    def field_value(record: Mapping[str, Any], field: str) -> object:
        wrapped = _mapping(record.get(field), context=f"reconstruction field {field}")
        return wrapped.get("value")

    def condition_equality(
        field: str,
        reactive_value: object,
        simulative_value: object,
        *evidence_refs: str,
        basis: str = "condition-owned-records",
    ) -> dict[str, object]:
        if reactive_value != simulative_value:
            raise T08EvidenceError(f"paired condition equality drifted: {field}")
        return {
            "field": field,
            "status": "equal",
            "value": reactive_value,
            "comparison_basis": basis,
            "evidence_refs": list(evidence_refs),
        }

    def shared_equality(
        field: str,
        value: object,
        *evidence_refs: str,
        basis: str = "shared-immutable-binding",
    ) -> dict[str, object]:
        return {
            "field": field,
            "status": "equal",
            "value": value,
            "comparison_basis": basis,
            "evidence_refs": list(evidence_refs),
        }

    def flag_value(command: list[Any], flag: str) -> str:
        indices = [index for index, value in enumerate(command) if value == flag]
        if len(indices) != 1 or indices[0] + 1 >= len(command):
            raise T08EvidenceError(f"paired command requires one value for {flag}")
        return _string(command[indices[0] + 1], context=f"command flag {flag}")

    reactive_environment = field_value(reactive_reconstruction, "environment_identity")
    simulative_environment = field_value(simulative_reconstruction, "environment_identity")
    reactive_task = {
        "query": field_value(reactive_reconstruction, "task_query"),
        "max_steps": field_value(reactive_reconstruction, "maximum_browser_steps"),
        "seed": flag_value(reactive_command, "--seed"),
    }
    simulative_task = {
        "query": field_value(simulative_reconstruction, "task_query"),
        "max_steps": field_value(simulative_reconstruction, "maximum_browser_steps"),
        "seed": flag_value(simulative_command, "--seed"),
    }
    reactive_tools = {
        "agent": flag_value(reactive_command, "--agent"),
        "browser": "chromium",
        "network": flag_value(reactive_command, "--network"),
    }
    simulative_tools = {
        "agent": flag_value(simulative_command, "--agent"),
        "browser": "chromium",
        "network": flag_value(simulative_command, "--network"),
    }

    equalities: list[dict[str, object]] = [
        shared_equality(
            "frozen_git_commit",
            manifest.get("git_commit"),
            "remote_archive:run-manifest.json",
        ),
        shared_equality(
            "sira_commit",
            manifest.get("sira_commit"),
            "remote_archive:run-manifest.json",
        ),
        condition_equality(
            "task",
            reactive_task,
            simulative_task,
            "remote_archive:evidence/reactive/sira-output",
            "remote_archive:evidence/simulative/sira-output",
            "remote_archive:run-manifest.json",
            basis="condition-owned-records-and-shared-binding",
        ),
        condition_equality(
            "python_version",
            _mapping(
                field_value(reactive_reconstruction, "python_runtime"),
                context="reactive Python runtime",
            ).get("version"),
            _mapping(
                field_value(simulative_reconstruction, "python_runtime"),
                context="simulative Python runtime",
            ).get("version"),
            "remote_archive:evidence/reactive/runtime-environment.json",
            "remote_archive:evidence/simulative/runtime-environment.json",
        ),
        shared_equality(
            "dependencies",
            {
                "uv_lock_sha256": runtime.get("uv_lock_sha256"),
                "installed_package_manifest_sha256": runtime.get(
                    "installed_package_manifest_sha256"
                ),
            },
            "remote_archive:run-manifest.json",
        ),
        condition_equality(
            "container_image",
            field_value(reactive_reconstruction, "container_image"),
            field_value(simulative_reconstruction, "container_image"),
            "remote_archive:evidence/reactive/container-inspect.json",
            "remote_archive:evidence/simulative/container-inspect.json",
            "remote_archive:run-manifest.json",
            basis="condition-owned-records-and-shared-binding",
        ),
        shared_equality(
            "browser_runtime",
            {
                "playwright_version": runtime.get("playwright_version"),
                "chromium_revision": runtime.get("chromium_revision"),
                "chromium_executable_sha256": runtime.get("chromium_executable_sha256"),
            },
            "remote_archive:run-manifest.json",
        ),
        condition_equality(
            "model_snapshot",
            flag_value(reactive_command, "--model"),
            flag_value(simulative_command, "--model"),
            "remote_archive:run-manifest.json#conditions.reactive.docker_argv",
            "remote_archive:run-manifest.json#conditions.simulative.docker_argv",
        ),
        condition_equality(
            "model_role_routing",
            field_value(reactive_reconstruction, "model_revision_by_role"),
            field_value(simulative_reconstruction, "model_revision_by_role"),
            "remote_archive:evidence/reactive/runtime-environment.json",
            "remote_archive:evidence/simulative/runtime-environment.json",
        ),
        condition_equality(
            "instrumentation_and_evidence_code",
            {
                "condition_runtime_adaptation_sha256": _mapping(
                    reactive_environment, context="reactive environment"
                ).get("runtime_adaptation_sha256"),
                "runtime_adaptation_sha256": runtime.get("runtime_adaptation_sha256"),
                "runtime_preflight_sha256": runtime.get("runtime_preflight_sha256"),
                "runner_sha256": runtime.get("runner_sha256"),
            },
            {
                "condition_runtime_adaptation_sha256": _mapping(
                    simulative_environment, context="simulative environment"
                ).get("runtime_adaptation_sha256"),
                "runtime_adaptation_sha256": runtime.get("runtime_adaptation_sha256"),
                "runtime_preflight_sha256": runtime.get("runtime_preflight_sha256"),
                "runner_sha256": runtime.get("runner_sha256"),
            },
            "remote_archive:evidence/reactive/runtime-environment.json",
            "remote_archive:evidence/simulative/runtime-environment.json",
            "remote_archive:run-manifest.json",
            basis="condition-owned-records-and-shared-binding",
        ),
        shared_equality(
            "cost_calculation",
            {
                "input_per_million_usd": _decimal_text(INPUT_RATE),
                "cached_input_per_million_usd": _decimal_text(CACHED_INPUT_RATE),
                "output_per_million_usd": _decimal_text(OUTPUT_RATE),
            },
            "repository:experiments/EXP-0001-sira-simulative-vs-reactive/pricing.yaml",
            "repository:src/giclab/harness/sira_gate_a.py@frozen-commit",
            basis="shared-recomputation-method",
        ),
        condition_equality(
            "environment",
            reactive_environment,
            simulative_environment,
            "remote_archive:evidence/reactive/runtime-environment.json",
            "remote_archive:evidence/simulative/runtime-environment.json",
        ),
        condition_equality(
            "tools",
            reactive_tools,
            simulative_tools,
            "remote_archive:run-manifest.json#conditions.reactive.docker_argv",
            "remote_archive:run-manifest.json#conditions.simulative.docker_argv",
            "remote_archive:evidence/reactive/container-inspect.json",
            "remote_archive:evidence/simulative/container-inspect.json",
        ),
        condition_equality(
            "maximum_browser_steps",
            field_value(reactive_reconstruction, "maximum_browser_steps"),
            field_value(simulative_reconstruction, "maximum_browser_steps"),
            "remote_archive:evidence/reactive/sira-output",
            "remote_archive:evidence/simulative/sira-output",
            "remote_archive:run-manifest.json",
            basis="condition-owned-records-and-shared-binding",
        ),
        shared_equality(
            "execution_host_class",
            {
                "instance_type": provider.get("instance_type"),
                "region": provider.get("region"),
                "provider_image_id": provider.get("provider_image_id"),
            },
            "remote_archive:run-manifest.json",
        ),
    ]
    command_fields = {
        5: "container_name",
        35: "attempt_root",
        41: "condition_label",
        56: "gate_mode",
        60: "job_name",
        64: "upstream_mode",
    }
    if len(reactive_command) != len(simulative_command):
        raise T08EvidenceError("paired Docker commands have different lengths")
    command_differences = [
        {
            "field": command_fields.get(index),
            "index": index,
            "reactive": left,
            "simulative": right,
        }
        for index, (left, right) in enumerate(
            zip(reactive_command, simulative_command, strict=True)
        )
        if left != right
    ]
    if any(item["field"] is None for item in command_differences) or {
        cast(int, item["index"]) for item in command_differences
    } != set(command_fields):
        raise T08EvidenceError("paired Docker commands drift outside approved fields")
    command_diff = {
        "schema_version": SCHEMA_VERSION,
        "approved_difference_fields": sorted(command_fields.values()),
        "command_length": len(reactive_command),
        "differences": command_differences,
        "matched": True,
    }
    retained_command_diff = _json_object(
        archive_files["condition-command-diff.json"], context="retained command diff"
    )
    if command_diff != retained_command_diff:
        raise T08EvidenceError("independent command diff disagrees with retained evidence")

    differing_config_fields = sorted(
        field
        for field in set(reactive_config) | set(simulative_config)
        if reactive_config.get(field) != simulative_config.get(field)
    )
    approved_config_fields = [
        "condition",
        "docker_argv",
        "model_call_attempt_cap",
        "order",
    ]
    if differing_config_fields != sorted(approved_config_fields):
        raise T08EvidenceError("paired condition configuration drifted outside approved fields")
    configuration_diff = {
        "schema_version": SCHEMA_VERSION,
        "approved_difference_fields": approved_config_fields,
        "differences": [
            {
                "field": "condition",
                "reactive": reactive_config["condition"],
                "simulative": simulative_config["condition"],
            },
            {
                "field": "docker_argv",
                "reactive_sha256": sha256_bytes(canonical_json(reactive_command)),
                "simulative_sha256": sha256_bytes(canonical_json(simulative_command)),
            },
            {
                "field": "model_call_attempt_cap",
                "reactive": reactive_config["model_call_attempt_cap"],
                "simulative": simulative_config["model_call_attempt_cap"],
            },
            {
                "field": "order",
                "reactive": reactive_config["order"],
                "simulative": simulative_config["order"],
            },
        ],
        "matched": True,
    }
    retained_configuration_diff = _json_object(
        archive_files["condition-configuration-diff.json"],
        context="retained configuration diff",
    )
    if configuration_diff != retained_configuration_diff:
        raise T08EvidenceError("independent configuration diff disagrees with retained evidence")
    allowed_differences = [
        {
            "field": "run_and_attempt_identity",
            "owner": "identity",
            "reactive": REACTIVE_RUN_ID,
            "simulative": SIMULATIVE_RUN_ID,
        },
        {
            "field": "condition_label_and_order",
            "owner": "treatment-assignment",
            "reactive": {"condition": reactive_config.get("condition"), "order": 1},
            "simulative": {"condition": simulative_config.get("condition"), "order": 2},
        },
        {
            "field": "source_declared_mode_and_planner_configuration",
            "owner": "source-declared-treatment",
            "reactive": _mode_configuration("reactive"),
            "simulative": _mode_configuration("simulative"),
        },
        {
            "field": "condition_owned_output_paths",
            "owner": "evidence-isolation",
            "reactive": "remote_archive:evidence/reactive",
            "simulative": "remote_archive:evidence/simulative",
        },
        {
            "field": "realized_runtime_and_provider_usage",
            "owner": "realized-events",
            "reactive": reactive.get("accounting"),
            "simulative": simulative.get("accounting"),
        },
    ]
    documented_gaps = [
        "per-call provider receipts and token/cost/latency allocation were not retained",
        "the simulative fifth call's exact role is not reconstructable from retained logs",
        (
            "normalized events and regulation-decision records were derived in T08, "
            "not retained in T07"
        ),
        "locale and timezone identity were not explicitly retained for each condition",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "pair_diff_id": "T08-SIRA-SMOKE-PAIR-DIFF-0001",
        "source_run_manifest_sha256": RUN_MANIFEST_SHA256,
        "classification": "matched_pair_valid_with_documented_evidence_gaps",
        "valid": True,
        "command_diff": command_diff,
        "configuration_diff": configuration_diff,
        "equalities": equalities,
        "allowed_differences": allowed_differences,
        "invalidating_differences": [],
        "documented_evidence_gaps": documented_gaps,
        "scientific_interpretation_allowed": False,
    }


def _provider_sensitive_field_report(local_root: Path) -> dict[str, object]:
    affected: list[str] = []
    key_names: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in _EXPECTED_SENSITIVE_PROVIDER_FIELDS:
                    key_names.add(key)
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    for path in sorted(local_root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            document = load_json(path)
        except (OSError, TypeError, ValueError):
            continue
        before = set(key_names)
        visit(document)
        if key_names != before:
            affected.append(f"local_retained:{path.name}")
        elif any(key in json.dumps(document) for key in _EXPECTED_SENSITIVE_PROVIDER_FIELDS):
            # A file can repeat an already-seen key name; record it without reading values.
            affected.append(f"local_retained:{path.name}")
    return {
        "sensitive_key_names": sorted(key_names),
        "affected_artifact_count": len(affected),
        "affected_artifacts": affected,
        "secret_values_emitted": False,
    }


def _accounting_reconciliation(
    reactive: Mapping[str, Any], simulative: Mapping[str, Any]
) -> dict[str, object]:
    left = _mapping(reactive.get("accounting"), context="reactive accounting")
    right = _mapping(simulative.get("accounting"), context="simulative accounting")

    def integer_sum(field: str) -> int:
        return _integer(left.get(field), context=f"reactive {field}") + _integer(
            right.get(field), context=f"simulative {field}"
        )

    wall = Decimal(_string(left.get("wall_seconds_raw"), context="reactive wall")) + Decimal(
        _string(right.get("wall_seconds_raw"), context="simulative wall")
    )
    cost = Decimal(
        _string(left.get("recomputed_cost_usd"), context="reactive recomputed cost")
    ) + Decimal(_string(right.get("recomputed_cost_usd"), context="simulative cost"))
    return {
        "price_record": {
            "record_id": "PRICE-OPENAI-GPT4O-2026-08-08",
            "record_sha256_at_frozen_commit": (
                "60df592cecf4c64eac8be0ec07d6599d3dcd0d06bab02835a3ab726beb89b437"
            ),
            "binding_provenance": "derived",
            "runtime_rates_match_record": True,
            "run_bundle_binds_price_record_hash": False,
            "rates_per_million_tokens": {
                "input": _decimal_text(INPUT_RATE),
                "cached_input": _decimal_text(CACHED_INPUT_RATE),
                "output": _decimal_text(OUTPUT_RATE),
            },
        },
        "formula": (
            "((input_tokens-cached_input_tokens)*2.50 + "
            "cached_input_tokens*1.25 + output_tokens*10.00) / 1,000,000"
        ),
        "rounding": (
            "Exact decimal arithmetic is authoritative; display values use decimal strings. "
            "Raw JSON binary-float spellings are retained separately."
        ),
        "reactive": left,
        "simulative": right,
        "aggregate": {
            "model_calls": integer_sum("model_calls"),
            "input_tokens": integer_sum("input_tokens"),
            "cached_input_tokens": integer_sum("cached_input_tokens"),
            "output_tokens": integer_sum("output_tokens"),
            "total_tokens": integer_sum("total_tokens"),
            "recomputed_cost_usd": _decimal_text(cost),
            "browser_actions": integer_sum("browser_actions"),
            "wall_seconds_raw": _decimal_text(wall),
            "wall_seconds_display_3dp": str(wall.quantize(Decimal("0.001"))),
            "unreconciled_provider_attempts": integer_sum("unreconciled_provider_attempts"),
        },
        "per_call_usage": evidence_field(
            None,
            "unavailable",
            note="No raw per-call provider usage receipt was retained.",
        ),
        "retry_reconciliation": {
            "condition_retries": evidence_field(
                0,
                "observed",
                "remote_archive:run-manifest.json",
            ),
            "transport_retries": evidence_field(
                0,
                "derived",
                "repository:src/giclab/harness/sira_gate_a_runtime.py@frozen-commit",
            ),
            "parser_retry_count": evidence_field(
                0,
                "inferred",
                "remote_archive:evidence/reactive/provider-budget.json",
                "remote_archive:evidence/simulative/provider-budget.json",
                note=(
                    "Observed call counts match the successful one-step paths and retained logs "
                    "contain no parser failure, but calls were not tagged with retry_kind."
                ),
            ),
        },
    }


def _evidence_inventory() -> list[dict[str, object]]:
    return [
        {
            "artifact": "authorization_and_run_manifest",
            "classification": "present-valid",
            "notes": (
                "Run manifest is hash-verified; the authorization reference is retained in the "
                "versioned compute manifest, but the full authorization payload is absent from "
                "the run bundle."
            ),
        },
        {
            "artifact": "exact_commands_and_configurations",
            "classification": "present-valid",
            "notes": "Resolved Docker argv and both pair-diff records are retained.",
        },
        {
            "artifact": "source_and_environment_identity",
            "classification": "present-valid",
            "notes": "Commit/tree/image/Python/package/browser hashes are retained.",
        },
        {
            "artifact": "raw_session_json",
            "classification": "present-valid",
            "notes": "Exactly one strict JSON session is retained per condition.",
        },
        {
            "artifact": "text_logs_stdout_stderr",
            "classification": "present-valid",
            "notes": "Agent/debug/runtime logs plus condition/container streams are retained.",
        },
        {
            "artifact": "screenshots",
            "classification": "present-valid",
            "notes": "One embedded JPEG pre-action screenshot is retained per condition.",
        },
        {
            "artifact": "post_action_observation_or_result",
            "classification": "missing-nonblocking",
            "notes": "The one-step smoke records a requested action but no structured result.",
        },
        {
            "artifact": "normalized_events",
            "classification": "missing-nonblocking",
            "notes": "No T07 stream exists; T08 derives the canonical six-event view per run.",
        },
        {
            "artifact": "artifact_records",
            "classification": "present-valid",
            "notes": "The 138-entry remote evidence hash manifest supplies artifact records.",
        },
        {
            "artifact": "token_and_model_call_records",
            "classification": "present-valid",
            "notes": "Condition aggregates are valid; per-call receipts are missing-nonblocking.",
        },
        {
            "artifact": "browser_action_counts",
            "classification": "present-valid",
            "notes": (
                "The runtime ledger count is derived from session history. One requested action "
                "is retained per condition; actual performance is inferred from normal exit "
                "because no structured post-action result exists."
            ),
        },
        {
            "artifact": "wall_time",
            "classification": "present-valid",
            "notes": "Monotonic condition wall values and container timestamps are retained.",
        },
        {
            "artifact": "cost_records",
            "classification": "present-valid",
            "notes": "Condition aggregates reproduce exactly; per-call cost is unavailable.",
        },
        {
            "artifact": "regulation_decision_records",
            "classification": "missing-nonblocking",
            "notes": "T08 derives source-classified assignment records from immutable commands.",
        },
        {
            "artifact": "pair_equivalence_record",
            "classification": "present-valid",
            "notes": "Command/config diffs are retained and independently recomputed in T08.",
        },
        {
            "artifact": "cleanup_record",
            "classification": "present-valid",
            "notes": (
                "Runtime, provider, firewall, secret-removal, and archive evidence is retained."
            ),
        },
        {
            "artifact": "deterministic_evaluator_output",
            "classification": "not-applicable",
            "notes": "The open-query smoke has no scientific evaluator and forbids interpretation.",
        },
    ]


def _h2k_assessment() -> dict[str, object]:
    return {
        "classification": "partially_sufficient",
        "infrastructure_evidence_only": True,
        "fields": {
            "decision_source": "derived-present",
            "assigned_mode": "derived-present",
            "available_modes": "derived-present",
            "selected_mode": "derived-present",
            "policy_config_revision": "derived-present",
            "causal_parent_events": "unavailable",
            "model_and_tool_costs": "observed-condition-aggregate-only",
            "downstream_action": "observed-requested-action",
            "realized_outcome": "unavailable",
            "override_or_fallback": "source-unavailable",
        },
        "boundary": (
            "Useful for schema and lineage validation, but insufficient for learned regulation, "
            "internalization, causal-controller comparison, or a training-ready corpus."
        ),
    }


def _cleanup_assessment(
    *,
    local_root: Path,
    external_report: Mapping[str, int],
) -> dict[str, object]:
    disposition = load_json(local_root / "run-disposition.json")
    provider = _mapping(disposition.get("provider"), context="run disposition provider")
    cleanup = _mapping(disposition.get("cleanup"), context="run disposition cleanup")
    remote_cleanup = load_json(local_root / "remote-evidence/cleanup.json")
    remote_secret_scan = load_json(local_root / "remote-evidence/secret-scan.json")
    local_secret_scan = load_json(local_root / "local-secret-scan.json")
    firewall_before = local_root / "preflight-firewall-rulesets-global.json"
    firewall_after = local_root / "posttermination-firewall-rulesets-global.json"
    if firewall_before.read_bytes() != firewall_after.read_bytes():
        raise T08EvidenceError("global firewall bytes changed across T07")
    sensitive = _provider_sensitive_field_report(local_root)
    if sensitive["sensitive_key_names"] != sorted(_EXPECTED_SENSITIVE_PROVIDER_FIELDS):
        raise T08EvidenceError("expected retained provider access fields were not detected")
    if (
        provider.get("terminal_absent") is not True
        or provider.get("account_instance_count") != 0
        or cleanup.get("provider_instances_remaining") != 0
        or cleanup.get("owned_containers_remaining") != 0
        or cleanup.get("owned_regional_rulesets_remaining") != 0
        or remote_cleanup.get("remote_secret_removed") is not True
        or remote_secret_scan.get("passed") is not True
        or local_secret_scan.get("passed") is not True
    ):
        raise T08EvidenceError("cleanup evidence does not support provider/runtime closeout")
    return {
        "classification": "cleanup_verified_with_nonmaterial_gap",
        "exact_instance_identity": evidence_field(
            provider.get("instance_id"),
            "observed",
            "local_retained:run-disposition.json",
        ),
        "launch_timestamp": evidence_field(
            provider.get("launched_at_utc"),
            "observed",
            "local_retained:run-disposition.json",
        ),
        "termination_timestamp": evidence_field(
            None,
            "unavailable",
            note=(
                "The exact provider transition timestamp is absent; terminal absence was later "
                "observed."
            ),
        ),
        "terminal_absence_verified_at": evidence_field(
            provider.get("terminal_absence_verified_at_utc"),
            "observed",
            "local_retained:run-disposition.json",
        ),
        "provider_terminal_absent": True,
        "running_account_instances": 0,
        "owned_containers": 0,
        "owned_regional_rulesets": 0,
        "global_firewall_unchanged": True,
        "global_firewall_sha256": sha256_file(firewall_before),
        "temporary_model_secret_removed": True,
        "api_key_secret_scans_passed": True,
        "ephemeral_provider_access_material": {
            **sensitive,
            "current_validity": "invalidated-by-provider-instance-termination",
            "classification": "private-retention-gap",
        },
        "credential_rotation_required": False,
        "external_archive": {
            **external_report,
            "source_destination_hashes_match": True,
            "manifest_sha256": EXTERNAL_MANIFEST_SHA256,
        },
        "nonmaterial_gaps": [
            "exact provider termination transition timestamp unavailable",
            (
                "private raw provider responses retain an ephemeral Jupyter access token/URL "
                "outside the historical API-key value scan; the terminated instance makes it "
                "inactive, and no value is emitted by T08"
            ),
        ],
    }


def adjudicate(
    *,
    repository_root: Path,
    local_root: Path,
    external_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build sanitized T08 adjudication and pair-diff documents from retained evidence."""

    repository_root = repository_root.resolve(strict=True)
    local_root = local_root.resolve(strict=True)
    external_root = external_root.resolve(strict=True)
    if not local_root.is_dir() or not external_root.is_dir():
        raise T08EvidenceError("retained evidence roots must be directories")

    tracked_summary_path = (
        repository_root / "docs/harness/evidence/T07_PRAGMATIC_RETRY2_POSTRUN.json"
    )
    if sha256_file(tracked_summary_path) != TRACKED_SUMMARY_SHA256:
        raise T08EvidenceError("tracked T07 post-run summary SHA-256 drifted")
    archive_path = local_root / REMOTE_ARCHIVE_RELATIVE
    archive_files = _archive_members(archive_path)
    archive_report = verify_archive_manifest(archive_files)

    outer_manifest_path = local_root / LOCAL_MANIFEST_RELATIVE
    if sha256_file(outer_manifest_path) != LOCAL_MANIFEST_SHA256:
        raise T08EvidenceError("local evidence manifest SHA-256 drifted")
    local_report = verify_filesystem_manifest(
        local_root,
        load_json(outer_manifest_path),
        context="local retained evidence manifest",
    )
    external_manifest_path = external_root / EXTERNAL_MANIFEST_NAME
    if sha256_file(external_manifest_path) != EXTERNAL_MANIFEST_SHA256:
        raise T08EvidenceError("external evidence manifest SHA-256 drifted")
    external_manifest = load_json(external_manifest_path)
    external_report = verify_filesystem_manifest(
        external_root,
        external_manifest,
        context="external sealed evidence manifest",
    )
    if external_manifest.get("source_destination_hashes_match") is not True:
        raise T08EvidenceError("external manifest does not attest source/destination equality")
    external_entries = _sequence(external_manifest.get("files"), context="external files")
    for raw in external_entries:
        entry = _mapping(raw, context="external file entry")
        relative = _safe_relative_path(entry.get("path"), context="external file path")
        local_path = local_root.joinpath(*PurePosixPath(relative).parts)
        if sha256_file(local_path) != entry.get("sha256"):
            raise T08EvidenceError(f"local/external retained source differs: {relative}")

    required_outer_archive_equalities = {
        "run-manifest.json": "frozen-manifest/run-manifest.json",
        "evidence/reactive/condition-status.json": "reactive-summary/condition-status.json",
        "evidence/simulative/condition-status.json": "simulative-summary/condition-status.json",
        "evidence/reactive/provider-budget.json": "reactive-summary/provider-budget.json",
        "evidence/simulative/provider-budget.json": "simulative-summary/provider-budget.json",
        "evidence/reactive/runtime-cleanup.json": "reactive-summary/runtime-cleanup.json",
        "evidence/simulative/runtime-cleanup.json": "simulative-summary/runtime-cleanup.json",
        "evidence/reactive/runtime-environment.json": "reactive-summary/runtime-environment.json",
        (
            "evidence/simulative/runtime-environment.json"
        ): "simulative-summary/runtime-environment.json",
    }
    for archive_relative, local_relative in required_outer_archive_equalities.items():
        if archive_files.get(archive_relative) != (local_root / local_relative).read_bytes():
            raise T08EvidenceError(f"archive/local summary differs: {archive_relative}")

    manifest_encoded = archive_files.get("run-manifest.json")
    if manifest_encoded is None or sha256_bytes(manifest_encoded) != RUN_MANIFEST_SHA256:
        raise T08EvidenceError("run manifest identity drifted")
    manifest = _json_object(manifest_encoded, context="run manifest")
    if (
        manifest.get("git_commit") != FROZEN_GICLAB_COMMIT
        or manifest.get("sira_commit") != SIRA_COMMIT
        or manifest.get("sira_tree") != SIRA_TREE
        or manifest.get("model_snapshot") != MODEL_SNAPSHOT
        or manifest.get("run_identities")
        != {
            "host": HOST_RUN_ID,
            "reactive": REACTIVE_RUN_ID,
            "simulative": SIMULATIVE_RUN_ID,
        }
    ):
        raise T08EvidenceError("run manifest immutable identity drifted")
    if sha256_bytes(archive_files["evidence/reactive/condition-status.json"]) != (
        REACTIVE_STATUS_SHA256
    ):
        raise T08EvidenceError("reactive status SHA-256 drifted")
    if sha256_bytes(archive_files["evidence/simulative/condition-status.json"]) != (
        SIMULATIVE_STATUS_SHA256
    ):
        raise T08EvidenceError("simulative status SHA-256 drifted")

    setup = _json_object(archive_files["setup-complete.json"], context="setup complete")
    browser_preflight = _json_object(
        archive_files["setup-attempt-03/browser-preflight/browser-preflight.json"],
        context="browser preflight",
    )
    packages = archive_files["setup-attempt-03/browser-preflight/installed-packages.txt"].decode(
        "utf-8"
    )
    package_lines = [line for line in packages.splitlines() if line]
    if (
        setup.get("setup_attempt") != 3
        or setup.get("python_version") != "3.11.14"
        or setup.get("sira_commit") != SIRA_COMMIT
        or setup.get("model") != MODEL_SNAPSHOT
        or browser_preflight.get("browser_actions") != 1
        or len(package_lines) != 96
    ):
        raise T08EvidenceError("setup/runtime identity evidence drifted")

    reactive_docs = _condition_documents(archive_files, "reactive")
    simulative_docs = _condition_documents(archive_files, "simulative")
    reactive = _condition_reconstruction(
        mode="reactive",
        manifest=manifest,
        documents=reactive_docs,
        archive_files=archive_files,
    )
    simulative = _condition_reconstruction(
        mode="simulative",
        manifest=manifest,
        documents=simulative_docs,
        archive_files=archive_files,
    )
    pair_diff = build_pair_diff(manifest, reactive, simulative, archive_files)
    accounting = _accounting_reconciliation(reactive, simulative)
    aggregate = _mapping(accounting.get("aggregate"), context="aggregate accounting")
    expected_aggregate = {
        "model_calls": 9,
        "input_tokens": 10073,
        "cached_input_tokens": 0,
        "output_tokens": 1515,
        "total_tokens": 11588,
        "recomputed_cost_usd": "0.0403325",
        "browser_actions": 2,
        "unreconciled_provider_attempts": 0,
    }
    for field, expected in expected_aggregate.items():
        if aggregate.get(field) != expected:
            raise T08EvidenceError(f"aggregate accounting drifted: {field}")

    compute = load_yaml(repository_root / "manifests/compute.yaml")
    compute_entries = _sequence(compute.get("entries"), context="compute entries")
    compute_record = next(
        (
            _mapping(entry, context="compute entry")
            for entry in compute_entries
            if isinstance(entry, dict) and entry.get("id") == "CMP-0003"
        ),
        None,
    )
    if compute_record is None or compute_record.get("status") != "completed":
        raise T08EvidenceError("CMP-0003 compute closeout record is unavailable")
    cleanup = _cleanup_assessment(local_root=local_root, external_report=external_report)

    evidence_gaps = [
        "full T07 authorization payload absent from the run bundle",
        "per-call provider receipts, token/cost allocation, and latency absent",
        "normalized event stream and regulation-decision artifacts absent from T07",
        "structured post-action result and task completion absent",
        "exact provider termination transition timestamp absent",
        "container locale/timezone identity absent",
        (
            "private provider-response artifacts retain an inactive ephemeral Jupyter access "
            "credential outside the historical API-key value scan"
        ),
    ]
    adjudication: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "adjudication_id": "T08-SIRA-SMOKE-EVIDENCE-ADJUDICATION-0001",
        "source_run": {
            "host_run_id": HOST_RUN_ID,
            "reactive_run_id": REACTIVE_RUN_ID,
            "simulative_run_id": SIMULATIVE_RUN_ID,
            "frozen_giclab_commit": FROZEN_GICLAB_COMMIT,
            "sira_commit": SIRA_COMMIT,
            "run_manifest_sha256": RUN_MANIFEST_SHA256,
        },
        "identity_verification": {
            "authorization_reference": evidence_field(
                compute_record.get("authorization_reference"),
                "observed",
                "repository:manifests/compute.yaml#CMP-0003",
                note="The complete authorization payload is unavailable in the run bundle.",
            ),
            "frozen_giclab_commit": evidence_field(
                FROZEN_GICLAB_COMMIT,
                "observed",
                "remote_archive:run-manifest.json",
            ),
            "sira_commit": evidence_field(
                SIRA_COMMIT,
                "observed",
                "remote_archive:run-manifest.json",
            ),
            "sira_tree": evidence_field(
                SIRA_TREE,
                "observed",
                "remote_archive:run-manifest.json",
            ),
            "run_manifest": evidence_field(
                {"bytes": len(manifest_encoded), "sha256": RUN_MANIFEST_SHA256},
                "observed",
                "remote_archive:run-manifest.json",
            ),
            "container_image": evidence_field(
                _mapping(manifest.get("runtime"), context="run manifest runtime").get(
                    "built_image_id"
                ),
                "observed",
                "remote_archive:run-manifest.json",
                "remote_archive:setup-attempt-03/image-inspect.json",
            ),
            "python": evidence_field(
                {
                    "version": setup.get("python_version"),
                    "executable_sha256": setup.get("python_executable_sha256"),
                },
                "observed",
                "remote_archive:setup-complete.json",
            ),
            "dependency_runtime": evidence_field(
                {
                    "uv_lock_sha256": setup.get("uv_lock_sha256"),
                    "installed_package_count": len(package_lines),
                    "installed_package_manifest_sha256": setup.get(
                        "installed_package_manifest_sha256"
                    ),
                    "playwright_version": setup.get("playwright_version"),
                    "chromium_revision": setup.get("chromium_revision"),
                },
                "observed",
                "remote_archive:setup-complete.json",
                "remote_archive:setup-attempt-03/browser-preflight/installed-packages.txt",
            ),
            "model_snapshot": evidence_field(
                MODEL_SNAPSHOT,
                "observed",
                "remote_archive:run-manifest.json",
                "remote_archive:setup-attempt-03/model-preflight/model-availability.json",
            ),
            "condition_status_hashes": evidence_field(
                {
                    "reactive": REACTIVE_STATUS_SHA256,
                    "simulative": SIMULATIVE_STATUS_SHA256,
                },
                "observed",
                "remote_archive:evidence-manifest.json",
            ),
            "local_and_external_manifests": evidence_field(
                {
                    "remote_manifest_sha256": REMOTE_MANIFEST_SHA256,
                    "remote_manifest": archive_report,
                    "local_manifest_sha256": LOCAL_MANIFEST_SHA256,
                    "local_manifest": local_report,
                    "external_manifest_sha256": EXTERNAL_MANIFEST_SHA256,
                    "external_manifest": external_report,
                },
                "observed",
                "remote_archive:evidence-manifest.json",
                "local_retained:LOCAL_SHA256SUMS.json",
                "sealed_external:FINAL_SHA256SUMS.json",
            ),
            "source_destination_equality": evidence_field(
                True,
                "observed",
                "sealed_external:FINAL_SHA256SUMS.json",
            ),
            "tracked_postrun_summary": evidence_field(
                {"sha256": TRACKED_SUMMARY_SHA256},
                "observed",
                "repository:docs/harness/evidence/T07_PRAGMATIC_RETRY2_POSTRUN.json",
            ),
        },
        "conditions": {"reactive": reactive, "simulative": simulative},
        "pair_contract": {
            "valid": True,
            "classification": pair_diff["classification"],
            "pair_diff_id": pair_diff["pair_diff_id"],
            "invalidating_differences": [],
        },
        "accounting_reconciliation": accounting,
        "artifact_execution": {"reactive": "passed", "simulative": "passed"},
        "task_completion": {
            "reactive": "not_observed",
            "simulative": "not_observed",
        },
        "evidence": {
            "complete_for_smoke": True,
            "gaps": evidence_gaps,
            "inventory": _evidence_inventory(),
        },
        "h2k_trace_sufficiency": _h2k_assessment(),
        "cleanup": cleanup,
        "scientific_interpretation_allowed": False,
        "pilot": {
            "protocol_preparation_eligible": True,
            "execution_authorized": False,
            "plan_id": "PLAN-EXP0001-PILOT",
            "sample_tasks": 2,
            "paired_condition_attempts": 4,
            "budgets": {
                "max_model_calls": 4620,
                "max_model_tokens": 4_000_000,
                "max_browser_actions": 120,
                "max_wall_seconds": 14_400,
                "max_openai_cost_usd": "40.00",
                "max_lambda_a10_hours": "4.00",
                "max_lambda_cost_usd_at_retained_rate": "5.16",
                "max_total_cost_usd_at_retained_rate": "45.16",
            },
        },
        "terminal_state": "smoke_evidence_validated_pilot_planning_eligible",
        "offline_actions": {
            "lambda_or_cloud_request": False,
            "cloud_mutation": False,
            "model_or_provider_request": False,
            "browser_action": False,
            "sira_condition_execution": False,
            "training": False,
            "pilot_execution": False,
            "scientific_interpretation": False,
        },
    }
    return adjudication, pair_diff


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--adjudication-output", type=Path, required=True)
    parser.add_argument("--pair-diff-output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the offline adjudicator and write only caller-selected output files."""

    args = _parser().parse_args(argv)
    adjudication, pair_diff = adjudicate(
        repository_root=args.repository_root,
        local_root=args.local_root,
        external_root=args.external_root,
    )
    for path, document in (
        (args.adjudication_output, adjudication),
        (args.pair_diff_output, pair_diff),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
