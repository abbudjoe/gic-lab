"""Interactive, user-mutation-only supervisor for an authorized T07 Gate L2M run.

The module is inert on import.  It never automates a browser or cloud mutation: the
only provider transport it can construct is the reviewed in-process GET observer.
Every effecting action is represented by a fresh private user checkpoint.  The
committed plan is unauthorized, so this entry point fails before credential access
unless a separate non-pending authorization binding is supplied.
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import os
import re
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from .lambda_cloud import secret_free_child_environment
from .lambda_l2m_checkpoints import (
    USER_CHECKPOINT_TYPES,
    CheckpointBinding,
    CheckpointContractError,
    PrivateCheckpointReader,
    ValidatedHumanDecision,
    validate_human_decision,
)
from .lambda_l2m_observer import (
    BUNDLE_MANIFEST_SHA256,
    MAX_USER_CHECKPOINT_SECONDS,
    InstanceMatchState,
    L2MContractError,
    L2MReadOnlyObserverEngine,
    LambdaHttpsL2MObserverTransport,
    ManualPhase,
    ObservedDocument,
    ObserverJournal,
    ObserverOperation,
    ObserverPhase,
    QualificationEvidenceBinding,
    ReadOnlyObserverTransport,
    RulesetMatchState,
    ValidatedQualification,
    classify_ruleset,
    seal_and_copy_observer_evidence_to_approved_external,
)
from .lambda_l23_manual_plan import (
    AUTHORIZATION_PLACEHOLDER,
    BRANCH,
    CHECKPOINT_SCHEMA_RELATIVE,
    PLAN_ID,
    PLAN_LATEST_SAFE_START_UTC,
    PLAN_RELATIVE,
    RUN_ID,
    TERMINAL_DECISION,
    L23ContractError,
    LoadedPrivateBinding,
    canonical_bytes,
    load_private_binding,
    sha256_bytes,
    validate_execution_storage_preflight,
    validate_public_plan,
)


class L23SupervisorError(ValueError):
    """The manual supervisor could not preserve its exact authority or safety contract."""


class L23QualificationFailed(L23SupervisorError):
    """The one-shot qualification produced validated failure evidence."""


MAX_PLAN_BYTES: Final = 1_048_576
MAX_PRIVATE_CHALLENGE_BYTES: Final = 16_384
MAX_GIT_OUTPUT_BYTES: Final = 65_536
GIT_TIMEOUT_SECONDS: Final = 10
POLL_SECONDS: Final = 0.25
_SHA256: Final = re.compile(r"^[a-f0-9]{64}$")
_COMMIT: Final = re.compile(r"^[a-f0-9]{40}$")
# The public packet uses the explicit ``GATE`` segment.  Fixture tests and older
# L2M records use the shorter form; both are the same bounded T07 authorization
# namespace, while the pending placeholder and malformed prefixes remain rejected.
_AUTHORIZATION: Final = re.compile(r"^AUTH-T07-(?:GATE-)?L2M-[A-Z0-9._-]{3,96}$")


@dataclass(slots=True)
class HeldPrivateDirectory:
    """A no-follow directory capability retained across the manual transaction."""

    path: Path = field(repr=False)
    descriptor: int = field(repr=False)
    device: int
    inode: int
    _closed: bool = False

    @classmethod
    def open(cls, path: Path) -> HeldPrivateDirectory:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        identity = os.fstat(descriptor)
        linked = path.lstat()
        if (
            not stat.S_ISDIR(identity.st_mode)
            or identity.st_uid != os.getuid()
            or stat.S_IMODE(identity.st_mode) & 0o077
            or stat.S_ISLNK(linked.st_mode)
            or (linked.st_dev, linked.st_ino) != (identity.st_dev, identity.st_ino)
        ):
            os.close(descriptor)
            raise L23SupervisorError("private directory capability is unsafe")
        return cls(path.absolute(), descriptor, identity.st_dev, identity.st_ino)

    def verify(self) -> None:
        if self._closed:
            raise L23SupervisorError("private directory capability is closed")
        opened = os.fstat(self.descriptor)
        linked = self.path.lstat()
        if (
            (opened.st_dev, opened.st_ino) != (self.device, self.inode)
            or (linked.st_dev, linked.st_ino) != (self.device, self.inode)
            or stat.S_ISLNK(linked.st_mode)
        ):
            raise L23SupervisorError("private directory path identity changed")

    def stat_leaf(self, name: str) -> os.stat_result:
        if not name or "/" in name or name in {".", ".."}:
            raise L23SupervisorError("private leaf name is unsafe")
        self.verify()
        return os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)

    def close(self) -> None:
        if not self._closed:
            os.close(self.descriptor)
            self._closed = True

    def __enter__(self) -> HeldPrivateDirectory:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def _mapping(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise L23SupervisorError(f"{context} is not an object")
    return value


def _sequence(value: object, *, context: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise L23SupervisorError(f"{context} is not an array")
    return value


def _text(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise L23SupervisorError(f"{context} is unavailable")
    return value


def _read_regular(path: Path, *, max_bytes: int) -> bytes:
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise L23SupervisorError("required supervisor input is unavailable") from None
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size > max_bytes
        ):
            raise L23SupervisorError("required supervisor input identity is unsafe")
        output = bytearray()
        while True:
            chunk = os.read(descriptor, min(65_536, max_bytes + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > max_bytes:
                raise L23SupervisorError("required supervisor input exceeds its cap")
        if len(output) != opened.st_size:
            raise L23SupervisorError("required supervisor input changed while held")
        return bytes(output)
    finally:
        os.close(descriptor)


def _strict_json(encoded: bytes) -> dict[str, object]:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise L23SupervisorError("supervisor JSON contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise L23SupervisorError("supervisor input is not strict JSON") from None
    if not isinstance(value, dict):
        raise L23SupervisorError("supervisor input is not an object")
    return value


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=secret_free_child_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        raise L23SupervisorError("read-only Git preflight failed") from None
    if len(completed.stdout) + len(completed.stderr) > MAX_GIT_OUTPUT_BYTES:
        raise L23SupervisorError("read-only Git preflight exceeded its output cap")
    if completed.returncode != 0:
        raise L23SupervisorError("read-only Git preflight returned failure")
    return completed.stdout.decode("utf-8", "strict").strip()


@dataclass(frozen=True, slots=True)
class SupervisorAuthorization:
    expected_commit: str
    authorization_reference: str
    authorization_sha256: str

    def validate(self) -> None:
        if (
            _COMMIT.fullmatch(self.expected_commit) is None
            or _AUTHORIZATION.fullmatch(self.authorization_reference) is None
            or self.authorization_reference.endswith("-PENDING")
            or self.authorization_reference == AUTHORIZATION_PLACEHOLDER
            or _SHA256.fullmatch(self.authorization_sha256) is None
        ):
            raise L23SupervisorError("fresh supervisor authorization binding is invalid")


@dataclass(frozen=True, slots=True)
class CheckpointContract:
    ordinal: int
    checkpoint_type: str
    checkpoint_id: str
    nonce: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SupervisorPreflight:
    plan: Mapping[str, object]
    plan_sha256: str
    private: LoadedPrivateBinding = field(repr=False)
    checkpoints: Mapping[str, CheckpointContract] = field(repr=False)


@dataclass(slots=True)
class ManualRunRisk:
    """Conservative wrapper state for user actions not yet provider-verified."""

    possible_mutation: bool = False
    unverified_phase: ObserverPhase | None = None

    def arm(self, phase: ObserverPhase | None) -> None:
        self.possible_mutation = True
        self.unverified_phase = phase

    def verified(self) -> None:
        self.possible_mutation = True
        self.unverified_phase = None

    def cleared(self) -> None:
        self.possible_mutation = False
        self.unverified_phase = None


def _verify_implementation_hashes(repository_root: Path, plan: Mapping[str, object]) -> None:
    binding = _mapping(plan.get("implementation_binding"), context="implementation binding")
    for item in _sequence(binding.get("artifacts"), context="implementation artifacts"):
        artifact = _mapping(item, context="implementation artifact")
        relative = Path(_text(artifact.get("path"), context="implementation path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise L23SupervisorError("implementation artifact path is unsafe")
        encoded = _read_regular(repository_root / relative, max_bytes=4_194_304)
        if artifact.get("bytes") != len(encoded) or artifact.get("sha256") != sha256_bytes(encoded):
            raise L23SupervisorError("plan-bound implementation artifact drifted")


def _verify_loaded_module_origins(repository_root: Path) -> None:
    expected = {
        Path(__file__).resolve(): repository_root
        / "src/giclab/harness/lambda_l23_manual_supervisor.py",
        Path(inspect.getsourcefile(validate_public_plan) or "").resolve(): repository_root
        / "src/giclab/harness/lambda_l23_manual_plan.py",
        Path(inspect.getsourcefile(validate_human_decision) or "").resolve(): repository_root
        / "src/giclab/harness/lambda_l2m_checkpoints.py",
        Path(
            inspect.getsourcefile(seal_and_copy_observer_evidence_to_approved_external) or ""
        ).resolve(): repository_root / "src/giclab/harness/lambda_l2m_observer.py",
    }
    if len(expected) != 4 or any(loaded != intended for loaded, intended in expected.items()):
        raise L23SupervisorError("loaded supervisor module origin differs from the repository")


def _validate_plan_start_time(utc_now: Callable[[], datetime]) -> None:
    try:
        latest_safe_start = datetime.fromisoformat(
            PLAN_LATEST_SAFE_START_UTC.replace("Z", "+00:00")
        )
        observed_now = utc_now().astimezone(UTC)
    except (TypeError, ValueError):
        raise L23SupervisorError("manual plan temporal preflight is unavailable") from None
    if observed_now > latest_safe_start:
        raise L23SupervisorError("manual plan expired before its paid-compute safety headroom")


def verify_supervisor_preflight(
    repository_root: Path,
    *,
    plan_path: Path,
    expected_plan_sha256: str,
    authorization: SupervisorAuthorization,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SupervisorPreflight:
    """Complete every repository/private check before a future credential read."""

    authorization.validate()
    root = repository_root.resolve(strict=True)
    _verify_loaded_module_origins(root)
    if root != repository_root.absolute() or plan_path.absolute() != root / PLAN_RELATIVE:
        raise L23SupervisorError("repository or plan path differs from the exact contract")
    encoded = _read_regular(plan_path, max_bytes=MAX_PLAN_BYTES)
    if _SHA256.fullmatch(expected_plan_sha256) is None or sha256_bytes(encoded) != (
        expected_plan_sha256
    ):
        raise L23SupervisorError("manual plan SHA-256 drifted")
    plan = _strict_json(encoded)
    try:
        validate_public_plan(plan, repository_root=root)
    except L23ContractError:
        raise L23SupervisorError("manual plan contract validation failed") from None
    if (
        plan.get("plan_id") != PLAN_ID
        or plan.get("run_id") != RUN_ID
        or plan.get("terminal_decision") != TERMINAL_DECISION
    ):
        raise L23SupervisorError("manual plan identity drifted")
    if (
        _git(root, "branch", "--show-current") != BRANCH
        or _git(root, "rev-parse", "HEAD") != authorization.expected_commit
        or _git(root, "status", "--short")
    ):
        raise L23SupervisorError("manual supervisor requires the exact clean branch and commit")
    implementation = _mapping(plan.get("implementation_binding"), context="implementation binding")
    reviewed = _text(
        implementation.get("reviewed_implementation_commit"), context="reviewed commit"
    )
    _git(root, "merge-base", "--is-ancestor", reviewed, authorization.expected_commit)
    _verify_implementation_hashes(root, plan)
    private = load_private_binding(root)
    validate_execution_storage_preflight(root, private)
    public_private = _mapping(plan.get("private_binding"), context="private plan binding")
    if dict(public_private) != private.seal.public_binding():
        raise L23SupervisorError("manual plan private seal binding drifted")
    _validate_plan_start_time(utc_now)
    checkpoint_rows = _sequence(
        private.parameters.get("checkpoint_bindings"), context="private checkpoints"
    )
    checkpoints: dict[str, CheckpointContract] = {}
    for expected_ordinal, value in enumerate(checkpoint_rows, start=1):
        row = _mapping(value, context="private checkpoint")
        checkpoint_type = _text(row.get("checkpoint_type"), context="checkpoint type")
        contract = CheckpointContract(
            expected_ordinal,
            checkpoint_type,
            _text(row.get("checkpoint_id"), context="checkpoint ID"),
            _text(row.get("checkpoint_nonce"), context="checkpoint nonce"),
        )
        if row.get("ordinal") != expected_ordinal or checkpoint_type in checkpoints:
            raise L23SupervisorError("private checkpoint sequence drifted")
        checkpoints[checkpoint_type] = contract
    expected_templates = _sequence(
        _mapping(plan.get("checkpoints"), context="plan checkpoints").get("templates"),
        context="checkpoint templates",
    )
    if tuple(checkpoints) != USER_CHECKPOINT_TYPES or len(checkpoints) != len(expected_templates):
        raise L23SupervisorError("private checkpoint sequence differs from the plan")
    return SupervisorPreflight(plan, expected_plan_sha256, private, checkpoints)


def _create_private_directory(repository_root: Path, path: Path) -> None:
    """Create one fresh private leaf through held, no-follow parent descriptors."""

    root = repository_root.resolve(strict=True)
    absolute = path.absolute()
    try:
        relative = absolute.relative_to(root)
    except ValueError:
        raise L23SupervisorError("private observer directory escaped the repository") from None
    descriptor = os.open(
        root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        for index, part in enumerate(relative.parts):
            final = index == len(relative.parts) - 1
            try:
                os.mkdir(part, 0o700, dir_fd=descriptor)
            except FileExistsError:
                if final:
                    raise L23SupervisorError(
                        "fresh private observer directory already exists"
                    ) from None
            child = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            observed = os.fstat(child)
            if (
                not stat.S_ISDIR(observed.st_mode)
                or observed.st_uid != os.getuid()
                or stat.S_IMODE(observed.st_mode) & 0o022
            ):
                os.close(child)
                raise L23SupervisorError("private observer hierarchy is unsafe")
            os.close(descriptor)
            descriptor = child
        os.fsync(descriptor)
    except OSError:
        raise L23SupervisorError("fresh private observer directory could not be created") from None
    finally:
        os.close(descriptor)


def _write_private(
    directory: HeldPrivateDirectory,
    name: str,
    document: Mapping[str, object],
) -> None:
    encoded = canonical_bytes(document)
    if len(encoded) > MAX_PRIVATE_CHALLENGE_BYTES:
        raise L23SupervisorError("private checkpoint challenge exceeds its cap")
    directory.verify()
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=directory.descriptor,
    )
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written < 1:
                raise L23SupervisorError("private checkpoint challenge write stalled")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory.descriptor)
    directory.verify()


def _await_checkpoint(
    *,
    checkpoint_root: HeldPrivateDirectory,
    challenge_root: HeldPrivateDirectory,
    binding: CheckpointBinding,
    contract: CheckpointContract,
    details: Mapping[str, object],
    private_action_parameters: Mapping[str, object] | None = None,
    now: Callable[[], datetime],
    monotonic: Callable[[], float],
    sleeper: Callable[[float], None],
) -> tuple[Path, datetime, datetime]:
    not_before = now().astimezone(UTC)
    not_after = not_before + timedelta(seconds=MAX_USER_CHECKPOINT_SECONDS)
    checkpoint_name = f"{contract.ordinal:02d}-{contract.checkpoint_type}.json"
    try:
        checkpoint_root.stat_leaf(checkpoint_name)
    except FileNotFoundError:
        pass
    else:
        raise L23SupervisorError("fresh private checkpoint path already exists")
    _write_private(
        challenge_root,
        checkpoint_name,
        {
            "schema_version": "0.1.0",
            "challenge_not_before_utc": not_before.isoformat().replace("+00:00", "Z"),
            "challenge_not_after_utc": not_after.isoformat().replace("+00:00", "Z"),
            "checkpoint_filename": checkpoint_name,
            "private_action_parameters": dict(private_action_parameters or {}),
            "checkpoint_template": {
                "schema_version": "0.1.0",
                "checkpoint_id": contract.checkpoint_id,
                "checkpoint_type": contract.checkpoint_type,
                "checkpoint_nonce": contract.nonce,
                "run_id": binding.run_id,
                "decision_alias": binding.decision_alias,
                "marker_alias": binding.marker_alias,
                "observed_at_utc": "<CURRENT-UTC-TIMESTAMP-Z>",
                "actor": "user",
                "action_confirmed": True,
                "details": dict(details),
            },
        },
    )
    print(f"T07_L2M_WAITING={contract.checkpoint_type}", flush=True)
    deadline = monotonic() + MAX_USER_CHECKPOINT_SECONDS
    while monotonic() <= deadline:
        try:
            observed = checkpoint_root.stat_leaf(checkpoint_name)
        except FileNotFoundError:
            sleeper(POLL_SECONDS)
            continue
        if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
            raise L23SupervisorError("private checkpoint path is unsafe")
        return checkpoint_root.path / checkpoint_name, not_before, not_after
    raise L23SupervisorError("private checkpoint window expired")


def _checkpoint_details(name: str, *, opaque_hash: str | None = None) -> dict[str, object]:
    simple = {
        "global_firewall_restricted",
        "regional_ruleset_created",
        "cloud_ide_opened",
        "qualification_command_started",
        "qualification_command_completed",
        "termination_confirmed_by_user",
    }
    if name in simple:
        return {name: True}
    if name == "launch_wizard_image_offered":
        return {
            name: True,
            "selected_instance_type": "gpu_1x_a10",
            "selected_region": "us-east-1",
            "selected_image_alias": "img-0032",
            "selected_image_version": "22.4.5-2141",
        }
    if name == "launch_configuration_selected":
        return {name: True, "launch_configuration_sha256": opaque_hash}
    if name == "launch_clicked_once":
        return {
            name: True,
            "approved_image_offered_for_selected_type_region": True,
            "launch_configuration_sha256": opaque_hash,
        }
    if name == "instance_bound":
        return {name: True, "instance_binding_sha256": opaque_hash}
    if name == "qualification_bundle_uploaded":
        return {name: True, "qualification_bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256}
    if name == "qualification_bundle_downloaded":
        return {name: True, "qualification_archive_sha256": opaque_hash}
    if name == "instance_terminal_verified":
        return {
            name: True,
            "terminal_or_absent": True,
            "launch_identity_state": opaque_hash,
        }
    if name == "regional_ruleset_deleted":
        return {name: True, "regional_ruleset_absent": True}
    if name == "global_firewall_restored":
        return {name: True, "global_firewall_semantic_sha256": opaque_hash}
    raise L23SupervisorError("unknown private checkpoint contract")


def _consume_auxiliary(
    engine: L2MReadOnlyObserverEngine,
    preflight: SupervisorPreflight,
    checkpoint_root: HeldPrivateDirectory,
    challenge_root: HeldPrivateDirectory,
    name: str,
    *,
    details: Mapping[str, object],
    private_action_parameters: Mapping[str, object] | None = None,
) -> None:
    path, before, after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints[name],
        details=details,
        private_action_parameters=private_action_parameters,
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    engine.consume_auxiliary_checkpoint(
        path,
        expected_type=name,
        expected_nonce=preflight.checkpoints[name].nonce,
        not_before=before,
        not_after=after,
    )


def _consume_manual(
    engine: L2MReadOnlyObserverEngine,
    preflight: SupervisorPreflight,
    checkpoint_root: HeldPrivateDirectory,
    challenge_root: HeldPrivateDirectory,
    name: str,
    *,
    details: Mapping[str, object],
    observation: ObservedDocument | None = None,
    qualification: ValidatedQualification | None = None,
    private_action_parameters: Mapping[str, object] | None = None,
) -> None:
    path, before, after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints[name],
        details=details,
        private_action_parameters=private_action_parameters,
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    engine.consume_checkpoint(
        path,
        expected_type=name,
        expected_nonce=preflight.checkpoints[name].nonce,
        not_before=before,
        not_after=after,
        observation=observation,
        qualification=qualification,
    )


def _private_human_capability(
    repository_root: Path, private: LoadedPrivateBinding
) -> ValidatedHumanDecision:
    schema_path = repository_root / "schemas/t07-lambda-l2m-human-decision.schema.json"
    schema = _strict_json(_read_regular(schema_path, max_bytes=65_536))
    try:
        return validate_human_decision(
            private.decision,
            schema=schema,
            schema_path=schema_path,
            decision_alias=private.seal.decision_alias,
        )
    except (CheckpointContractError, ValueError):
        raise L23SupervisorError(
            "sealed human decision capability could not be recreated"
        ) from None


def _create_bound_engine(
    *,
    repository_root: Path,
    observer_root: Path,
    checkpoint_root: HeldPrivateDirectory,
    preflight: SupervisorPreflight,
    authorization: SupervisorAuthorization,
    credential_provider: Callable[[], str | None],
    transport: ReadOnlyObserverTransport,
) -> tuple[str, L2MReadOnlyObserverEngine]:
    """Create the observer engine while closing every partial local capability."""

    credential = credential_provider()
    if (
        not isinstance(credential, str)
        or not credential
        or len(credential) > 4_096
        or any(value in credential for value in ("\r", "\n", "\x00"))
    ):
        raise L23SupervisorError("approved credential presence check failed")
    private_parameters = preflight.private.parameters
    private_ruleset = _mapping(
        private_parameters.get("owned_regional_ruleset"), context="private ruleset"
    )
    selected = _mapping(private_parameters.get("selected_resource"), context="selected resource")
    original_global = _mapping(
        private_parameters.get("original_global_firewall"), context="original global firewall"
    )
    binding = CheckpointBinding(
        RUN_ID,
        preflight.private.seal.decision_alias,
        _text(private_ruleset.get("marker_alias"), context="marker alias"),
    )
    reader: PrivateCheckpointReader | None = None
    journal: ObserverJournal | None = None
    try:
        reader = PrivateCheckpointReader.from_schema_path(
            repository_root / CHECKPOINT_SCHEMA_RELATIVE,
            binding=binding,
            consumption_path=observer_root / "checkpoint-consumption.jsonl",
            checkpoint_root_descriptor=checkpoint_root.descriptor,
            checkpoint_root_path=checkpoint_root.path,
        )
        journal = ObserverJournal.create(
            observer_root / "observer-journal.jsonl",
            schema_path=(repository_root / "schemas/t07-lambda-l2m-observer-journal.schema.json"),
        )
        human_decision = _private_human_capability(repository_root, preflight.private)
        engine = L2MReadOnlyObserverEngine(
            run_id=RUN_ID,
            authorization_reference=authorization.authorization_reference,
            authorization_sha256=authorization.authorization_sha256,
            journal=journal,
            checkpoint_reader=reader,
            transport=transport,
            private_marker_name=_text(private_ruleset.get("name"), context="private marker"),
            source_ipv4_cidr=_text(
                private_parameters.get("source_ipv4_cidr"), context="private source network"
            ),
            human_decision=human_decision,
            sealed_original_global_sha256=_text(
                original_global.get("semantic_sha256"), context="global semantic hash"
            ),
            image_selection_checkpoint_sha256=preflight.private.seal.decision_seal_sha256,
            private_selected_image_id=_text(selected.get("raw_image_id"), context="raw image"),
            private_selected_ssh_key_id=_text(
                selected.get("raw_ssh_key_id"), context="raw SSH key"
            ),
            private_selected_ssh_key_fingerprint=_text(
                selected.get("local_public_key_fingerprint"), context="SSH key fingerprint"
            ),
            selected_image_alias=_text(selected.get("image_alias"), context="image alias"),
            selected_image_version=_text(selected.get("image_version"), context="image version"),
            require_l23_auxiliary_checkpoints=True,
        )
    except BaseException:
        if journal is not None:
            with contextlib.suppress(BaseException):
                journal.close()
        if reader is not None:
            with contextlib.suppress(BaseException):
                reader.close()
        raise
    return credential, engine


def _qualification_binding(
    engine: L2MReadOnlyObserverEngine,
) -> QualificationEvidenceBinding:
    if engine.instance_binding_sha256 is None:
        raise L23SupervisorError("qualification lacks an exact instance binding")
    return QualificationEvidenceBinding(
        run_id=engine.run_id,
        decision_alias=engine.checkpoint_reader.binding.decision_alias,
        marker_alias=engine.checkpoint_reader.binding.marker_alias,
        instance_binding_sha256=engine.instance_binding_sha256,
        authorization_reference=engine.authorization_reference,
        authorization_sha256=engine.authorization_sha256,
    )


def _concrete_qualification_argv(
    preflight: SupervisorPreflight,
    engine: L2MReadOnlyObserverEngine,
) -> list[str]:
    template = _sequence(
        preflight.plan.get("qualification_bootstrap_argv"),
        context="qualification bootstrap argv",
    )
    binding = _qualification_binding(engine)
    replacements = {
        "<PRIVATE-DECISION-ALIAS>": binding.decision_alias,
        "<PRIVATE-MARKER-ALIAS>": binding.marker_alias,
        "<PRIVATE-INSTANCE-BINDING-SHA256>": binding.instance_binding_sha256,
        "<FRESH-AUTHORIZATION-REFERENCE>": binding.authorization_reference,
        "<FRESH-AUTHORIZATION-SHA256>": binding.authorization_sha256,
    }
    rendered = [
        replacements.get(_text(value, context="qualification argument"), value)
        for value in template
    ]
    if any(not isinstance(value, str) or "<" in value or ">" in value for value in rendered):
        raise L23SupervisorError("qualification bootstrap contains an unresolved value")
    return [str(value) for value in rendered]


def _wait_for_qualification_archive(
    *,
    inbound_root: HeldPrivateDirectory,
    success_path: Path,
    failure_path: Path,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[str, Path]:
    print("T07_L2M_WAITING=qualification_evidence_archive", flush=True)
    deadline = monotonic() + MAX_USER_CHECKPOINT_SECONDS
    while monotonic() <= deadline:
        present: list[tuple[str, Path]] = []
        for kind, path in (("success", success_path), ("failure", failure_path)):
            if path.parent.absolute() != inbound_root.path:
                raise L23SupervisorError("qualification evidence escaped the held inbound root")
            try:
                identity = inbound_root.stat_leaf(path.name)
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(identity.st_mode) or not stat.S_ISREG(identity.st_mode):
                raise L23SupervisorError("qualification evidence path is unsafe")
            present.append((kind, path))
        if len(present) > 1:
            raise L23SupervisorError("multiple qualification evidence archives are forbidden")
        if present:
            return present[0]
        sleeper(POLL_SECONDS)
    raise L23SupervisorError("qualification evidence archive window expired")


def _rows(value: object, *, context: str) -> list[Mapping[str, object]]:
    return [_mapping(item, context=context) for item in _sequence(value, context=context)]


def _authorized_scope_is_terminal_or_absent(
    engine: L2MReadOnlyObserverEngine,
    observation: ObservedDocument,
) -> bool:
    rows = _rows(observation.data, context="terminal instance rows")
    scope = set(engine.incident_scope_instance_ids())
    observed: dict[str, Mapping[str, object]] = {}
    for row in rows:
        raw_id = row.get("id")
        if not isinstance(raw_id, str):
            engine.enter_wrapper_incident(possible_user_mutation_phase=None)
            raise L23SupervisorError("terminal observation contains an invalid identity")
        observed[raw_id] = row
    if set(observed) - scope:
        engine.enter_wrapper_incident(possible_user_mutation_phase=None)
        raise L23SupervisorError(
            "unattached account instance requires a new private human decision"
        )
    return all(
        observed.get(identifier, {}).get("status") in {"terminated", "preempted"}
        for identifier in scope
        if identifier in observed
    )


def _bind_exact_launch_instance(
    engine: L2MReadOnlyObserverEngine,
    *,
    credential: str,
) -> str:
    """Poll only transient zero and stop immediately on ambiguity or final zero."""

    for poll_index in range(9):
        candidate = engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.INSTANCE_BIND,
            credential=credential,
        )
        match = engine.assess_instance_binding_observation(
            candidate,
            zero_is_terminal=poll_index == 8,
        )
        if match.state is InstanceMatchState.ZERO and poll_index < 8:
            continue
        if match.state is not InstanceMatchState.EXACT_ONE:
            raise L23SupervisorError(
                "instance binding entered incident on zero, multiple, or drift"
            )
        return engine.bind_exact_instance_observation(candidate)
    raise L23SupervisorError("instance did not resolve to exactly one within its GET cap")


def _wait_for_terminal_scope(
    engine: L2MReadOnlyObserverEngine,
    *,
    credential: str,
    phase: ObserverPhase,
) -> ObservedDocument:
    """Return one terminal/absent observation for only the private authorized scope."""

    for _ in range(10):
        candidate = engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=phase,
            credential=credential,
        )
        if _authorized_scope_is_terminal_or_absent(engine, candidate):
            return candidate
    raise L23SupervisorError("incident-scope instances were not terminal within the cap")


def _incident_cleanup(
    engine: L2MReadOnlyObserverEngine,
    preflight: SupervisorPreflight,
    *,
    credential: str,
    checkpoint_root: HeldPrivateDirectory,
    challenge_root: HeldPrivateDirectory,
    risk: ManualRunRisk,
) -> None:
    """Continue only the same-run, user-operated cleanup path when evidence permits it."""

    if engine.stopped:
        raise L23SupervisorError("observer stopped before cleanup could be verified")
    if not engine.lifecycle.incident_active:
        engine.enter_wrapper_incident(
            possible_user_mutation_phase=risk.unverified_phase,
        )
    engine.resume_incident_cleanup()
    private_parameters = preflight.private.parameters
    owned_ruleset = _mapping(
        private_parameters.get("owned_regional_ruleset"), context="owned ruleset"
    )
    original_global = _mapping(
        private_parameters.get("original_global_firewall"), context="original global firewall"
    )
    reader = engine.checkpoint_reader
    if not isinstance(reader, PrivateCheckpointReader):
        raise L23SupervisorError("incident checkpoint reader is not the exact private reader")

    phase = engine.lifecycle.phase
    postlaunch_phases = {
        ManualPhase.LAUNCH_OUTCOME_UNVERIFIED,
        ManualPhase.LAUNCH_CLICKED,
        ManualPhase.INSTANCE_BOUND,
        ManualPhase.CLOUD_IDE_OPENED,
        ManualPhase.QUALIFICATION_STARTED,
        ManualPhase.QUALIFICATION_COMPLETED,
        ManualPhase.BUNDLE_DOWNLOADED,
        ManualPhase.TERMINATION_CONFIRMED,
    }
    if phase is ManualPhase.RULESET_CREATED:
        observed = engine.observe(
            ObserverOperation.LIST_INSTANCES,
            phase=ObserverPhase.INCIDENT,
            credential=credential,
        )
        if _rows(observed.data, context="prelaunch incident instances"):
            raise L23SupervisorError(
                "an unexpected prelaunch instance requires a new human recovery decision"
            )
        engine.assess_instance_binding_observation(
            observed,
            zero_is_terminal=True,
        )
        engine.resume_incident_cleanup()
        engine.commit_terminal_instance_observation(observed)
        phase = engine.lifecycle.phase
    elif phase in postlaunch_phases:
        if phase in {ManualPhase.LAUNCH_OUTCOME_UNVERIFIED, ManualPhase.LAUNCH_CLICKED}:
            initial = engine.observe(
                ObserverOperation.LIST_INSTANCES,
                phase=ObserverPhase.INCIDENT,
                credential=credential,
            )
            match = engine.assess_instance_binding_observation(
                initial,
                zero_is_terminal=True,
            )
            engine.resume_incident_cleanup()
            private_ids = list(engine.incident_scope_instance_ids())
            if match.state is InstanceMatchState.ZERO:
                engine.commit_terminal_instance_observation(initial)
                phase = engine.lifecycle.phase
            else:
                if not private_ids:
                    raise L23SupervisorError(
                        "launch drift has no authorized ruleset-attached cleanup identity"
                    )
                _consume_manual(
                    engine,
                    preflight,
                    checkpoint_root,
                    challenge_root,
                    "termination_confirmed_by_user",
                    details=_checkpoint_details("termination_confirmed_by_user"),
                    private_action_parameters={
                        "private_instance_ids": private_ids,
                        "confirmation_phrase": "erase data on instance",
                        "terminate_every_incident_scope_row": True,
                    },
                )
                phase = engine.lifecycle.phase
        elif phase is not ManualPhase.TERMINATION_CONFIRMED:
            private_ids = list(engine.incident_scope_instance_ids())
            if not private_ids:
                raise L23SupervisorError(
                    "postlaunch incident has no authorized ruleset-attached identity"
                )
            _consume_manual(
                engine,
                preflight,
                checkpoint_root,
                challenge_root,
                "termination_confirmed_by_user",
                details=_checkpoint_details("termination_confirmed_by_user"),
                private_action_parameters={
                    "private_instance_ids": private_ids,
                    "confirmation_phrase": "erase data on instance",
                    "terminate_every_incident_scope_row": True,
                },
            )
            phase = engine.lifecycle.phase

        if phase is ManualPhase.TERMINATION_CONFIRMED:
            terminal = _wait_for_terminal_scope(
                engine,
                credential=credential,
                phase=ObserverPhase.INCIDENT,
            )
            engine.commit_terminal_instance_observation(terminal)

    phase = engine.lifecycle.phase
    if phase in {
        ManualPhase.RULESET_MUTATION_UNVERIFIED,
        ManualPhase.INSTANCE_TERMINAL,
    }:
        if "regional_ruleset_deleted" in reader.consumed_types:
            raise L23SupervisorError("regional cleanup checkpoint was already burned")
        deletion_path, deletion_before, deletion_after = _await_checkpoint(
            checkpoint_root=checkpoint_root,
            challenge_root=challenge_root,
            binding=reader.binding,
            contract=preflight.checkpoints["regional_ruleset_deleted"],
            details=_checkpoint_details("regional_ruleset_deleted"),
            private_action_parameters={
                "ruleset_name": owned_ruleset.get("name"),
                "private_ruleset_id": engine.private_ruleset_id,
                "delete_if_present_and_confirm_absent": True,
            },
            now=engine.utc_now,
            monotonic=time.monotonic,
            sleeper=time.sleep,
        )
        absence = engine.observe(
            ObserverOperation.LIST_RULESETS,
            phase=ObserverPhase.INCIDENT,
            credential=credential,
        )
        ruleset_match = classify_ruleset(
            absence.data,
            private_marker_name=engine.private_marker_name,
            source_ipv4_cidr=engine.source_ipv4_cidr,
        )
        if ruleset_match.state is not RulesetMatchState.ZERO:
            raise L23SupervisorError("owned regional ruleset remains after cleanup action")
        engine.consume_checkpoint(
            deletion_path,
            expected_type="regional_ruleset_deleted",
            expected_nonce=preflight.checkpoints["regional_ruleset_deleted"].nonce,
            not_before=deletion_before,
            not_after=deletion_after,
            observation=absence,
        )

    phase = engine.lifecycle.phase
    if phase in {
        ManualPhase.GLOBAL_MUTATION_UNVERIFIED,
        ManualPhase.GLOBAL_RESTRICTED,
        ManualPhase.RULESET_DELETED,
    }:
        if "global_firewall_restored" in reader.consumed_types:
            raise L23SupervisorError("global restoration checkpoint was already burned")
        restored_path, restored_before, restored_after = _await_checkpoint(
            checkpoint_root=checkpoint_root,
            challenge_root=challenge_root,
            binding=reader.binding,
            contract=preflight.checkpoints["global_firewall_restored"],
            details=_checkpoint_details(
                "global_firewall_restored",
                opaque_hash=engine.sealed_original_global_sha256,
            ),
            private_action_parameters={"restore_rules": original_global.get("rules")},
            now=engine.utc_now,
            monotonic=time.monotonic,
            sleeper=time.sleep,
        )
        restored = engine.observe(
            ObserverOperation.GET_GLOBAL_FIREWALL,
            phase=ObserverPhase.INCIDENT,
            credential=credential,
        )
        engine.consume_checkpoint(
            restored_path,
            expected_type="global_firewall_restored",
            expected_nonce=preflight.checkpoints["global_firewall_restored"].nonce,
            not_before=restored_before,
            not_after=restored_after,
            observation=restored,
        )

    if engine.lifecycle.phase is not ManualPhase.COMPLETE:
        raise L23SupervisorError("manual incident cleanup did not reach the terminal state")
    risk.cleared()
    engine.stop(outcome="cleanup_complete_evidence_incomplete")


def _normal_run(
    engine: L2MReadOnlyObserverEngine,
    preflight: SupervisorPreflight,
    *,
    credential: str,
    checkpoint_root: HeldPrivateDirectory,
    challenge_root: HeldPrivateDirectory,
    inbound_root: HeldPrivateDirectory,
    inbound_success_archive: Path,
    inbound_failure_archive: Path,
    repository_root: Path,
    risk: ManualRunRisk,
) -> Path:
    private_parameters = preflight.private.parameters
    selected = _mapping(private_parameters.get("selected_resource"), context="selected resource")
    owned_ruleset = _mapping(
        private_parameters.get("owned_regional_ruleset"), context="owned ruleset"
    )
    strict_rule = _mapping(private_parameters.get("strict_firewall_rule"), context="strict rule")
    original_global = _mapping(
        private_parameters.get("original_global_firewall"), context="original global firewall"
    )
    engine.begin()
    for operation in (
        ObserverOperation.LIST_IMAGES,
        ObserverOperation.LIST_INSTANCE_TYPES,
        ObserverOperation.LIST_SSH_KEYS,
        ObserverOperation.LIST_INSTANCES,
        ObserverOperation.LIST_RULESETS,
        ObserverOperation.GET_GLOBAL_FIREWALL,
    ):
        engine.observe(operation, phase=ObserverPhase.PREFLIGHT, credential=credential)
    _consume_auxiliary(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "launch_wizard_image_offered",
        details=_checkpoint_details("launch_wizard_image_offered"),
        private_action_parameters={
            "instance_type": selected.get("instance_type"),
            "region": selected.get("region"),
            "image_alias": selected.get("image_alias"),
            "image_family": selected.get("image_family"),
            "image_version": selected.get("image_version"),
            "launch_forbidden": True,
        },
    )
    original_global_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.ORIGINAL_GLOBAL_SEAL,
        credential=credential,
    )
    engine.seal_original_global_firewall(original_global_observation)

    risk.arm(ObserverPhase.GLOBAL_RESTRICTED_VERIFY)
    global_path, global_before, global_after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints["global_firewall_restricted"],
        details=_checkpoint_details("global_firewall_restricted"),
        private_action_parameters={"replacement_rules": [dict(strict_rule)]},
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    global_observation = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTRICTED_VERIFY,
        credential=credential,
    )
    engine.consume_checkpoint(
        global_path,
        expected_type="global_firewall_restricted",
        expected_nonce=preflight.checkpoints["global_firewall_restricted"].nonce,
        not_before=global_before,
        not_after=global_after,
        observation=global_observation,
    )
    risk.verified()

    risk.arm(ObserverPhase.RULESET_BIND)
    ruleset_path, ruleset_before, ruleset_after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints["regional_ruleset_created"],
        details=_checkpoint_details("regional_ruleset_created"),
        private_action_parameters={
            "ruleset_name": owned_ruleset.get("name"),
            "region": owned_ruleset.get("region"),
            "rules": owned_ruleset.get("rules"),
        },
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    ruleset_observation = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_BIND,
        credential=credential,
    )
    engine.consume_checkpoint(
        ruleset_path,
        expected_type="regional_ruleset_created",
        expected_nonce=preflight.checkpoints["regional_ruleset_created"].nonce,
        not_before=ruleset_before,
        not_after=ruleset_after,
        observation=ruleset_observation,
    )
    risk.verified()
    launch_configuration_sha256 = engine.launch_configuration_binding_sha256()
    _consume_auxiliary(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "launch_configuration_selected",
        details=_checkpoint_details(
            "launch_configuration_selected", opaque_hash=launch_configuration_sha256
        ),
        private_action_parameters={
            "instance_type": selected.get("instance_type"),
            "region": selected.get("region"),
            "image_alias": selected.get("image_alias"),
            "image_family": selected.get("image_family"),
            "image_version": selected.get("image_version"),
            "ssh_key_name": selected.get("ssh_key_name"),
            "regional_ruleset_name": owned_ruleset.get("name"),
            "persistent_filesystem": None,
            "launch_forbidden_until_armed": True,
        },
    )
    engine.arm_launch_window()
    _consume_manual(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "launch_clicked_once",
        details=_checkpoint_details("launch_clicked_once", opaque_hash=launch_configuration_sha256),
        private_action_parameters={"maximum_launch_clicks": 1},
    )

    _bind_exact_launch_instance(engine, credential=credential)
    _consume_manual(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "cloud_ide_opened",
        details=_checkpoint_details("cloud_ide_opened"),
        private_action_parameters={
            "private_instance_id": engine.private_instance_id,
            "access_mode": "cloud-ide-jupyter-only",
            "ssh_forbidden": True,
            "additional_ports_forbidden": True,
        },
    )
    _consume_auxiliary(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "qualification_bundle_uploaded",
        details=_checkpoint_details("qualification_bundle_uploaded"),
        private_action_parameters={
            "source_directory": str(
                repository_root / "containers/sira-smoke/lambda/manual-console"
            ),
            "destination_directory": "/home/ubuntu/t07-l2m-bundle",
            "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
        },
    )
    qualification_argv = _concrete_qualification_argv(preflight, engine)
    _consume_manual(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "qualification_command_started",
        details=_checkpoint_details("qualification_command_started"),
        private_action_parameters={
            "argument_array": qualification_argv,
            "shell_command_forbidden": True,
            "maximum_executions": 1,
        },
    )
    _consume_manual(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "qualification_command_completed",
        details=_checkpoint_details("qualification_command_completed"),
        private_action_parameters={
            "accepted_terminal_prefixes": [
                "T07_L2M_QUALIFICATION=success",
                "T07_L2M_QUALIFICATION=failed",
            ],
            "rerun_forbidden": True,
        },
    )
    download_path, download_before, download_after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints["qualification_bundle_downloaded"],
        details=_checkpoint_details(
            "qualification_bundle_downloaded",
            opaque_hash="<SHA256-OF-DOWNLOADED-EVIDENCE-ARCHIVE>",
        ),
        private_action_parameters={
            "success_destination": str(inbound_success_archive),
            "failure_destination": str(inbound_failure_archive),
            "download_exactly_one": True,
        },
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    archive_kind, inbound_archive = _wait_for_qualification_archive(
        inbound_root=inbound_root,
        success_path=inbound_success_archive,
        failure_path=inbound_failure_archive,
    )
    evidence_binding = _qualification_binding(engine)
    if archive_kind == "failure":
        failure = engine.validate_qualification_failure(
            inbound_archive,
            expected_bundle_manifest_sha256=BUNDLE_MANIFEST_SHA256,
            expected_binding=evidence_binding,
            archive_directory_descriptor=inbound_root.descriptor,
        )
        # The user action happened before validation; bind its already-present
        # checkpoint to the validated failure archive without inviting a rerun.
        engine.resume_incident_cleanup()
        engine.consume_auxiliary_checkpoint(
            download_path,
            expected_type="qualification_bundle_downloaded",
            expected_nonce=preflight.checkpoints["qualification_bundle_downloaded"].nonce,
            not_before=download_before,
            not_after=download_after,
            expected_archive_sha256=failure.archive_sha256,
        )
        raise L23QualificationFailed("qualification produced failure evidence; rerun forbidden")
    qualification = engine.validate_qualification(
        inbound_archive,
        schema_path=repository_root / "schemas/t07-lambda-l2m-host-evidence.schema.json",
        expected_bundle_manifest_sha256=BUNDLE_MANIFEST_SHA256,
        expected_binding=evidence_binding,
        archive_directory_descriptor=inbound_root.descriptor,
    )
    engine.consume_auxiliary_checkpoint(
        download_path,
        expected_type="qualification_bundle_downloaded",
        expected_nonce=preflight.checkpoints["qualification_bundle_downloaded"].nonce,
        not_before=download_before,
        not_after=download_after,
        expected_archive_sha256=qualification.archive_sha256,
    )
    engine.commit_validated_qualification(qualification)
    _consume_manual(
        engine,
        preflight,
        checkpoint_root,
        challenge_root,
        "termination_confirmed_by_user",
        details=_checkpoint_details("termination_confirmed_by_user"),
        private_action_parameters={
            "private_instance_ids": [engine.private_instance_id],
            "confirmation_phrase": "erase data on instance",
            "terminate_all_listed": True,
        },
    )
    terminal_observation = _wait_for_terminal_scope(
        engine,
        credential=credential,
        phase=ObserverPhase.TERMINATION_VERIFY,
    )
    engine.commit_terminal_instance_observation(terminal_observation)
    ruleset_delete_path, ruleset_delete_before, ruleset_delete_after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints["regional_ruleset_deleted"],
        details=_checkpoint_details("regional_ruleset_deleted"),
        private_action_parameters={
            "ruleset_name": owned_ruleset.get("name"),
            "private_ruleset_id": engine.private_ruleset_id,
        },
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    ruleset_absence = engine.observe(
        ObserverOperation.LIST_RULESETS,
        phase=ObserverPhase.RULESET_ABSENCE,
        credential=credential,
    )
    engine.consume_checkpoint(
        ruleset_delete_path,
        expected_type="regional_ruleset_deleted",
        expected_nonce=preflight.checkpoints["regional_ruleset_deleted"].nonce,
        not_before=ruleset_delete_before,
        not_after=ruleset_delete_after,
        observation=ruleset_absence,
    )
    restored_path, restored_before, restored_after = _await_checkpoint(
        checkpoint_root=checkpoint_root,
        challenge_root=challenge_root,
        binding=engine.checkpoint_reader.binding,
        contract=preflight.checkpoints["global_firewall_restored"],
        details=_checkpoint_details(
            "global_firewall_restored", opaque_hash=engine.sealed_original_global_sha256
        ),
        private_action_parameters={"restore_rules": original_global.get("rules")},
        now=engine.utc_now,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )
    restored = engine.observe(
        ObserverOperation.GET_GLOBAL_FIREWALL,
        phase=ObserverPhase.GLOBAL_RESTORE,
        credential=credential,
    )
    engine.consume_checkpoint(
        restored_path,
        expected_type="global_firewall_restored",
        expected_nonce=preflight.checkpoints["global_firewall_restored"].nonce,
        not_before=restored_before,
        not_after=restored_after,
        observation=restored,
    )
    risk.cleared()
    engine.stop(outcome="passed")
    return inbound_archive


def execute_authorized_manual_observer(
    repository_root: Path,
    *,
    plan_path: Path,
    plan_sha256: str,
    authorization: SupervisorAuthorization,
    credential_provider: Callable[[], str | None],
    transport: ReadOnlyObserverTransport,
) -> None:
    """Run the exact user/observer transaction after a separately bound authorization."""

    preflight = verify_supervisor_preflight(
        repository_root,
        plan_path=plan_path,
        expected_plan_sha256=plan_sha256,
        authorization=authorization,
    )
    root = repository_root.resolve(strict=True)
    private_parameters = preflight.private.parameters
    external = _mapping(private_parameters.get("external_archive"), context="external archive")
    checkpoint_root_path = root / _text(
        private_parameters.get("checkpoint_root_relative"), context="checkpoint root"
    )
    observer_root = root / Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "observer-v1"
    if checkpoint_root_path.exists() or observer_root.exists():
        raise L23SupervisorError("fresh manual run or checkpoint root already exists")
    _create_private_directory(root, checkpoint_root_path)
    _create_private_directory(root, observer_root)
    challenge_root = observer_root / "challenges"
    inbound_root = root / Path("artifacts/t07/lambda/gate-l2m") / RUN_ID / "inbound"
    _create_private_directory(root, challenge_root)
    _create_private_directory(root, inbound_root)
    held_roots = contextlib.ExitStack()
    try:
        checkpoint_root = held_roots.enter_context(HeldPrivateDirectory.open(checkpoint_root_path))
        challenge_root_held = held_roots.enter_context(HeldPrivateDirectory.open(challenge_root))
        inbound_root_held = held_roots.enter_context(HeldPrivateDirectory.open(inbound_root))
        credential, engine = _create_bound_engine(
            repository_root=root,
            observer_root=observer_root,
            checkpoint_root=checkpoint_root,
            preflight=preflight,
            authorization=authorization,
            credential_provider=credential_provider,
            transport=transport,
        )
    except BaseException:
        held_roots.close()
        raise
    inbound_success_archive = inbound_root / "t07-l2m-output-0001-evidence.zip"
    inbound_failure_archive = inbound_root / "t07-l2m-output-0001-failure-evidence.zip"
    qualification_path: Path | None = None
    risk = ManualRunRisk()
    try:
        qualification_path = _normal_run(
            engine,
            preflight,
            credential=credential,
            checkpoint_root=checkpoint_root,
            challenge_root=challenge_root_held,
            inbound_root=inbound_root_held,
            inbound_success_archive=inbound_success_archive,
            inbound_failure_archive=inbound_failure_archive,
            repository_root=root,
            risk=risk,
        )
    except BaseException:
        # Continue only the typed cleanup path in the same process.  If that control
        # plane is unavailable, burn the run, retain incomplete evidence, and require
        # the runbook's human cleanup plus a separately reviewed recovery run.
        cleanup_complete = False
        if risk.possible_mutation and not engine.stopped:
            try:
                _incident_cleanup(
                    engine,
                    preflight,
                    credential=credential,
                    checkpoint_root=checkpoint_root,
                    challenge_root=challenge_root_held,
                    risk=risk,
                )
                cleanup_complete = True
                print(
                    "T07_L2M_DISPOSITION=cleanup_complete_evidence_incomplete",
                    flush=True,
                )
            except BaseException:
                if not engine.stopped:
                    with contextlib.suppress(BaseException):
                        engine.abort_for_separately_authorized_manual_cleanup(
                            possible_user_mutation_phase=risk.unverified_phase
                        )
                print(
                    "T07_L2M_DISPOSITION=manual_incident_cleanup_required_run_burned",
                    flush=True,
                )
        elif not engine.stopped:
            engine.stop(outcome="manual_stop")
        archive_identity = _text(
            external.get("observer_archive_identity"), context="observer archive identity"
        )
        try:
            try:
                seal_and_copy_observer_evidence_to_approved_external(
                    engine,
                    repository_root=root,
                    archive_id=archive_identity,
                    qualification_archive_path=None,
                )
            except L2MContractError:
                print("T07_L2M_ARCHIVE=local_source_retained_external_incomplete", flush=True)
            if cleanup_complete:
                print("T07_L2M_CLEANUP=terminal_ruleset_absent_global_restored", flush=True)
        finally:
            held_roots.close()
        raise
    archive_identity = _text(
        external.get("observer_archive_identity"), context="observer archive identity"
    )
    try:
        seal_and_copy_observer_evidence_to_approved_external(
            engine,
            repository_root=root,
            archive_id=archive_identity,
            qualification_archive_path=qualification_path,
        )
    finally:
        held_roots.close()
    print("T07_L2M_DISPOSITION=host_qualification_complete", flush=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    authorization = SupervisorAuthorization(
        args.expected_commit,
        args.authorization_reference,
        args.authorization_sha256,
    )
    try:
        execute_authorized_manual_observer(
            args.repository_root,
            plan_path=args.plan,
            plan_sha256=args.plan_sha256,
            authorization=authorization,
            credential_provider=lambda: os.environ.get("LAMBDA_API_KEY"),
            transport=LambdaHttpsL2MObserverTransport(),
        )
    except (L23ContractError, L23SupervisorError, L2MContractError, OSError, ValueError):
        print("giclab-l2m-supervisor: stopped; inspect private sealed evidence", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
