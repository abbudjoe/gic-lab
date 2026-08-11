#!/usr/bin/env python3
"""Future Jupyter-only T07 Gate L2M qualification driver.

The file is inert until a later plan and current-turn authorization supply all required
arguments. It never calls Lambda, SSH, a browser, a model, or SiRA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType, ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docker_inspector import CommandBudget

DOCKER = "/usr/bin/docker"
BUSYBOX = "busybox@sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0"
MANIFEST_DIGEST = "sha256:7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0"
CONFIG_DIGEST = "sha256:db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4"
LAYER_DIGEST = "sha256:436a1b1fd078ee8e117111472724c2827077657189af7a781829d0825d48d2ab"
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RUN_ID = re.compile(r"^RUN-T07-L2M-[A-Z0-9._-]{3,64}$")
ALIAS = re.compile(r"^l2m-(?:decision|marker)-[a-f0-9]{12}$")
WORK_WALL_SECONDS = 270
TOTAL_WALL_SECONDS = 300
FIXTURE_WALL_SECONDS = 30
CREATE_OUTCOME_POLL_OBSERVATIONS = 5
CREATE_OUTCOME_STABLE_ABSENCE_OBSERVATIONS = 3
CREATE_OUTCOME_POLL_INTERVAL_SECONDS = 1
PUBLIC_METADATA_OBSERVATION_SHA256 = (
    "56a1ba759d4fc5ac6eba2ee85c5bff2a08d0d71f538793f3de5732bb80d0b1a5"
)
PUBLIC_METADATA_RETRIEVED_AT_UTC = "2026-08-11T06:15:19.646016Z"
PUBLIC_METADATA_MAX_AGE_SECONDS = 86_400
PUBLIC_METADATA_URL = f"https://registry-1.docker.io/v2/library/busybox/manifests/{MANIFEST_DIGEST}"
BOOTSTRAP_SOURCE = """import hashlib,os,stat,sys
p=sys.argv[2]
fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
try:
 s=os.fstat(fd)
 if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>1048576: raise SystemExit(90)
 b=bytearray()
 while len(b)<=1048576:
  c=os.read(fd,min(65536,1048577-len(b)))
  if not c: break
  b.extend(c)
 if len(b)!=s.st_size or hashlib.sha256(b).hexdigest()!=sys.argv[1]: raise SystemExit(91)
 cap=object()
 g={'__name__':'__t07_l2m_verified_driver__','__file__':p,'__t07_l2m_bootstrap_capability__':cap}
 exec(compile(bytes(b),p,'exec'),g)
 if g.get('_VERIFIED_BOOTSTRAP_CAPABILITY') is not cap: raise SystemExit(92)
 raise SystemExit(g['main'](sys.argv[3:],_bootstrap_capability=cap))
finally: os.close(fd)
"""

_VERIFIED_BOOTSTRAP_CAPABILITY = globals().pop("__t07_l2m_bootstrap_capability__", None)


class QualificationError(RuntimeError):
    pass


class QualificationFailed(QualificationError):
    def __init__(self, archive: Path, sha256: str, *, cleanup_incident: bool) -> None:
        super().__init__("qualification failed with sealed evidence")
        self.archive = archive
        self.sha256 = sha256
        self.cleanup_incident = cleanup_incident


class QualificationTerminationGuard:
    """Route interactive/session termination through the typed cleanup path."""

    _SIGNALS = (signal.SIGINT, signal.SIGHUP, signal.SIGTERM)

    def __init__(self) -> None:
        self._old_handlers = {value: signal.getsignal(value) for value in self._SIGNALS}
        self._closed = False
        self._interrupted_once = False
        try:
            for value in self._SIGNALS:
                signal.signal(value, self._interrupted)
        except (OSError, ValueError):
            self.close()
            raise QualificationError("qualification termination guard is unavailable") from None

    def _interrupted(self, signum: int, frame: FrameType | None) -> None:
        del signum, frame
        if self._interrupted_once:
            return
        self._interrupted_once = True
        raise QualificationError("qualification interrupted; emergency cleanup required")

    def close(self) -> None:
        if self._closed:
            return
        for value, handler in self._old_handlers.items():
            signal.signal(value, handler)
        self._closed = True


class QualificationAlarm:
    """One process-level hard wall that can be shortened for bounded subphases."""

    def __init__(self, absolute_deadline_monotonic: float) -> None:
        self._created = time.monotonic()
        self._old_handler = signal.getsignal(signal.SIGALRM)
        self._old_timer = signal.getitimer(signal.ITIMER_REAL)
        self._closed = False
        signal.signal(signal.SIGALRM, self._expired)
        self.arm(absolute_deadline_monotonic)

    @staticmethod
    def _expired(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        raise QualificationError("qualification hard deadline exceeded")

    def arm(self, absolute_deadline_monotonic: float) -> None:
        remaining = absolute_deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise QualificationError("qualification hard deadline exceeded")
        signal.setitimer(signal.ITIMER_REAL, remaining)

    def close(self) -> None:
        if self._closed:
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._old_handler)
        previous_remaining, previous_interval = self._old_timer
        if previous_remaining > 0:
            elapsed = time.monotonic() - self._created
            signal.setitimer(
                signal.ITIMER_REAL,
                max(0.001, previous_remaining - elapsed),
                previous_interval,
            )
        self._closed = True


def _check_deadline(absolute_deadline_monotonic: float) -> None:
    if time.monotonic() >= absolute_deadline_monotonic:
        raise QualificationError("qualification hard deadline exceeded")


def _bounded_sleep(seconds: float, *, absolute_deadline_monotonic: float) -> None:
    remaining = absolute_deadline_monotonic - time.monotonic()
    if seconds <= 0 or remaining < seconds:
        raise QualificationError("qualification hard deadline exceeded")
    time.sleep(seconds)
    _check_deadline(absolute_deadline_monotonic)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _strict_json(encoded: bytes, *, context: str) -> object:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise QualificationError(f"{context} contains a duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(encoded, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise QualificationError(f"{context} is not strict JSON") from None


def validate_public_metadata_record(
    encoded: bytes,
    *,
    now_utc: datetime | None = None,
) -> tuple[str, int]:
    """Require one recent, manifest-bound OCI observation before any Docker call."""

    if hashlib.sha256(encoded).hexdigest() != PUBLIC_METADATA_OBSERVATION_SHA256:
        raise QualificationError("public metadata observation identity drifted")
    document = _strict_json(encoded, context="public metadata observation")
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "gate",
        "revalidated_at_utc",
        "account_requests",
        "authenticated_account_requests",
        "public_registry_anonymous_token_requests",
        "public_registry_metadata_requests",
        "public_registry_metadata_bytes",
        "installation_payload_or_image_layer_downloads",
        "sources",
        "openapi_operation_extracts",
        "findings",
    }:
        raise QualificationError("public metadata observation contract drifted")
    for key in (
        "account_requests",
        "authenticated_account_requests",
        "installation_payload_or_image_layer_downloads",
    ):
        if type(document.get(key)) is not int or document[key] != 0:
            raise QualificationError("public metadata observation used a forbidden request")
    if (
        document.get("public_registry_anonymous_token_requests") != 1
        or document.get("public_registry_metadata_requests") != 2
        or document.get("public_registry_metadata_bytes") != 1_069
    ):
        raise QualificationError("public metadata observation request accounting drifted")
    if (
        document.get("schema_version") != "0.1.0"
        or document.get("gate") != "T07-L2.2"
        or document.get("revalidated_at_utc") != PUBLIC_METADATA_RETRIEVED_AT_UTC
        or not isinstance(document.get("sources"), list)
    ):
        raise QualificationError("public metadata observation contract drifted")
    try:
        observed_at = datetime.fromisoformat(
            PUBLIC_METADATA_RETRIEVED_AT_UTC.replace("Z", "+00:00")
        )
    except ValueError:
        raise QualificationError("public metadata observation timestamp is invalid") from None
    current = datetime.now(timezone.utc) if now_utc is None else now_utc  # noqa: UP017 -- Python 3.10
    if current.tzinfo is None or current.utcoffset() is None:
        raise QualificationError("public metadata trusted clock is not timezone-aware")
    age = (
        current.astimezone(timezone.utc)  # noqa: UP017 -- Python 3.10
        - observed_at.astimezone(timezone.utc)  # noqa: UP017 -- Python 3.10
    ).total_seconds()
    if age < 0 or age > PUBLIC_METADATA_MAX_AGE_SECONDS:
        raise QualificationError("public metadata observation is not current")

    observations = [
        item
        for item in document["sources"]
        if isinstance(item, dict) and item.get("kind") == "public-oci-metadata"
    ]
    if len(observations) != 1:
        raise QualificationError("public metadata OCI observation is not unique")
    observation = observations[0]
    expected = {
        "kind": "public-oci-metadata",
        "url": PUBLIC_METADATA_URL,
        "registry_auth_mode": "anonymous-bearer",
        "platform": "linux/amd64",
        "manifest_bytes": 610,
        "manifest_sha256": MANIFEST_DIGEST.removeprefix("sha256:"),
        "config_digest": CONFIG_DIGEST,
        "config_url": (f"https://registry-1.docker.io/v2/library/busybox/blobs/{CONFIG_DIGEST}"),
        "config_bytes": 459,
        "config_sha256": CONFIG_DIGEST.removeprefix("sha256:"),
        "config_os": "linux",
        "config_architecture": "amd64",
        "layer_digest": LAYER_DIGEST,
        "layer_bytes": 2_211_507,
        "layers_downloaded": 0,
    }
    if observation != expected:
        raise QualificationError("public metadata OCI identity drifted")
    return PUBLIC_METADATA_RETRIEVED_AT_UTC, int(age)


def write_exclusive(
    path: Path,
    value: object,
    *,
    absolute_deadline_monotonic: float | None = None,
) -> None:
    write_bytes_exclusive(
        path,
        canonical(value) + b"\n",
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    )


def write_bytes_exclusive(
    path: Path,
    encoded: bytes,
    *,
    absolute_deadline_monotonic: float | None = None,
) -> None:
    if absolute_deadline_monotonic is not None:
        _check_deadline(absolute_deadline_monotonic)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            if absolute_deadline_monotonic is not None:
                _check_deadline(absolute_deadline_monotonic)
            written = os.write(descriptor, view)
            if written <= 0:
                raise QualificationError("evidence write failed")
            view = view[written:]
        os.fsync(descriptor)
        if absolute_deadline_monotonic is not None:
            _check_deadline(absolute_deadline_monotonic)
    finally:
        os.close(descriptor)


def _read_regular_no_follow(path: Path, *, maximum_bytes: int = 16_777_216) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        identity = os.fstat(descriptor)
        if (
            not stat.S_ISREG(identity.st_mode)
            or identity.st_nlink != 1
            or identity.st_size > maximum_bytes
        ):
            raise QualificationError("bundle file identity is unsafe")
        encoded = bytearray()
        while len(encoded) <= maximum_bytes:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
        if len(encoded) != identity.st_size:
            raise QualificationError("bundle file size changed during verification")
        return bytes(encoded)
    finally:
        os.close(descriptor)


def _read_regular_from_held_directory(
    directory_descriptor: int,
    name: str,
    *,
    maximum_bytes: int = 16_777_216,
) -> bytes:
    if Path(name).parts != (name,):
        raise QualificationError("bundle file name is unsafe")
    descriptor = -1
    try:
        before = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_uid != os.getuid()
            or opened.st_size > maximum_bytes
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise QualificationError("bundle file identity is unsafe")
        encoded = bytearray()
        while len(encoded) <= maximum_bytes:
            chunk = os.read(descriptor, min(65_536, maximum_bytes + 1 - len(encoded)))
            if not chunk:
                break
            encoded.extend(chunk)
        after = os.fstat(descriptor)
        linked = os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
        if (
            len(encoded) != opened.st_size
            or (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
            )
            or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise QualificationError("bundle file changed while held")
        return bytes(encoded)
    except OSError:
        raise QualificationError("bundle file could not be read safely") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _staged_fixture_record(path: Path, encoded: bytes) -> dict[str, object]:
    identity = path.lstat()
    if (
        not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
        or identity.st_uid != os.getuid()
        or stat.S_IMODE(identity.st_mode) != 0o400
        or _read_regular_no_follow(path, maximum_bytes=1_048_576) != encoded
    ):
        raise QualificationError("staged fixture identity drifted")
    identity_document = {
        "bytes": identity.st_size,
        "device": identity.st_dev,
        "inode": identity.st_ino,
        "mode": stat.S_IMODE(identity.st_mode),
    }
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "identity_sha256": hashlib.sha256(canonical(identity_document)).hexdigest(),
    }


def _materialize_verified_fixture(output: Path, encoded: bytes) -> tuple[Path, dict[str, object]]:
    path = output / "adversarial-containment.sh"
    write_bytes_exclusive(path, encoded)
    os.chmod(path, 0o400, follow_symlinks=False)
    record = _staged_fixture_record(path, encoded)
    parent_descriptor = os.open(
        output,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    return path, record


def _verify_staged_fixture(
    path: Path,
    encoded: bytes,
    expected_record: dict[str, object],
) -> None:
    if _staged_fixture_record(path, encoded) != expected_record:
        raise QualificationError("staged fixture identity changed")


def _remove_staged_fixture(
    path: Path,
    encoded: bytes,
    expected_record: dict[str, object],
) -> None:
    _verify_staged_fixture(path, encoded, expected_record)
    path.unlink()
    parent_descriptor = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)


def verify_bundle(root: Path, *, expected_manifest_sha256: str) -> tuple[str, dict[str, bytes]]:
    root_descriptor = -1
    try:
        root_before = root.lstat()
        root_descriptor = os.open(
            root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        root_opened = os.fstat(root_descriptor)
        root_linked = root.lstat()
        if (
            not stat.S_ISDIR(root_opened.st_mode)
            or root_opened.st_uid != os.getuid()
            or (root_before.st_dev, root_before.st_ino) != (root_opened.st_dev, root_opened.st_ino)
            or (root_linked.st_dev, root_linked.st_ino) != (root_opened.st_dev, root_opened.st_ino)
        ):
            raise QualificationError("bundle root identity is unsafe")
        encoded = _read_regular_from_held_directory(root_descriptor, "manifest.json")
        observed_manifest_sha256 = hashlib.sha256(encoded).hexdigest()
        if observed_manifest_sha256 != expected_manifest_sha256:
            raise QualificationError("bundle manifest identity drifted")
        manifest = _strict_json(encoded, context="bundle manifest")
        expected_names = {
            "adversarial-containment.sh",
            "docker_inspector.py",
            "evidence_packager.py",
            "host_facts.py",
            "public-source-observations-l2-2.json",
            "qualification_driver.py",
        }
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != "0.1.0"
            or manifest.get("bundle_id") != "BUNDLE-T07-L2M-JUPYTER-HOST-QUALIFICATION-V1"
            or manifest.get("python_contract") != "3.10"
            or manifest.get("busybox_reference") != BUSYBOX
            or not isinstance(manifest.get("files"), list)
        ):
            raise QualificationError("bundle manifest contract drifted")
        observed_names: set[str] = set()
        payloads: dict[str, bytes] = {}
        for item in manifest["files"]:
            if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
                raise QualificationError("bundle manifest file identity is invalid")
            name = item.get("path")
            if (
                not isinstance(name, str)
                or Path(name).parts != (name,)
                or name not in expected_names
                or name in observed_names
            ):
                raise QualificationError("bundle manifest path is invalid")
            payload = _read_regular_from_held_directory(root_descriptor, name)
            if len(payload) != item.get("bytes") or hashlib.sha256(payload).hexdigest() != item.get(
                "sha256"
            ):
                raise QualificationError("bundle hash verification failed")
            observed_names.add(name)
            payloads[name] = payload
        if observed_names != expected_names:
            raise QualificationError("bundle manifest is incomplete")
        approved_inert_repository_records = {
            "T07_L2M_HUMAN_DECISION_TEMPLATE.json",
            "image-candidate-decision.json",
        }
        allowed_root_names = expected_names | approved_inert_repository_records | {"manifest.json"}
        for name in os.listdir(root_descriptor):
            identity = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
            if (
                name not in allowed_root_names
                or not stat.S_ISREG(identity.st_mode)
                or identity.st_nlink != 1
                or identity.st_uid != os.getuid()
            ):
                raise QualificationError("unapproved bundle root content is forbidden")
        root_current = root.lstat()
        if (root_current.st_dev, root_current.st_ino) != (
            root_opened.st_dev,
            root_opened.st_ino,
        ):
            raise QualificationError("bundle root changed while held")
        return observed_manifest_sha256, payloads
    except OSError:
        raise QualificationError("bundle root could not be verified safely") from None
    finally:
        if root_descriptor >= 0:
            os.close(root_descriptor)


def _load_verified_module(name: str, encoded: bytes) -> ModuleType:
    module_name = f"_t07_l2m_verified_{name}"
    module = ModuleType(module_name)
    module.__file__ = f"<verified:{name}.py>"
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(compile(encoded, module.__file__, "exec"), module.__dict__)
    except Exception:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def qualification_bootstrap_arguments(
    *,
    python_executable: str,
    driver_path: Path,
    expected_driver_sha256: str,
    driver_arguments: list[str],
) -> list[str]:
    """Render the future isolated, hash-first Jupyter qualification argv."""

    if python_executable != "/usr/bin/python3" or SHA256.fullmatch(expected_driver_sha256) is None:
        raise QualificationError("qualification bootstrap identity is invalid")
    if not driver_path.is_absolute() or driver_path.name != "qualification_driver.py":
        raise QualificationError("qualification driver path is invalid")
    if any("\x00" in value for value in driver_arguments):
        raise QualificationError("qualification bootstrap argument is invalid")
    return [
        python_executable,
        "-I",
        "-S",
        "-c",
        BOOTSTRAP_SOURCE,
        expected_driver_sha256,
        str(driver_path),
        *driver_arguments,
    ]


def create_arguments(*, name: str, fixture: Path, run_id: str, marker_alias: str) -> list[str]:
    return [
        DOCKER,
        "create",
        "--pull=never",
        "--name",
        name,
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--ipc",
        "private",
        "--cgroupns",
        "private",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16777216",
        "--tmpfs",
        "/run:rw,noexec,nosuid,nodev,size=16777216",
        "--shm-size",
        "16777216",
        "--cpus",
        "1.0",
        "--memory",
        "536870912",
        "--memory-swap",
        "536870912",
        "--pids-limit",
        "64",
        "--restart",
        "no",
        "--init",
        "--log-driver",
        "local",
        "--log-opt",
        "max-size=1m",
        "--log-opt",
        "max-file=1",
        "--label",
        f"giclab.t07.run={run_id}",
        "--label",
        f"giclab.t07.marker={marker_alias}",
        "--mount",
        f"type=bind,src={fixture},dst=/opt/t07/adversarial-containment.sh,readonly",
        BUSYBOX,
        "/bin/sh",
        "/opt/t07/adversarial-containment.sh",
    ]


def _residue_count(
    budget: CommandBudget,
    resource: str,
    run_id: str,
    *,
    cleanup: bool = False,
    absolute_deadline_monotonic: float,
) -> int:
    if resource == "container":
        args = [DOCKER, "ps", "-aq", "--filter", f"label=giclab.t07.run={run_id}"]
    elif resource == "network":
        args = [DOCKER, "network", "ls", "-q", "--filter", f"label=giclab.t07.run={run_id}"]
    elif resource == "volume":
        args = [DOCKER, "volume", "ls", "-q", "--filter", f"label=giclab.t07.run={run_id}"]
    else:
        raise QualificationError("residue resource is invalid")
    return len(
        [
            line
            for line in budget.run(
                args,
                timeout_seconds=15,
                cleanup=cleanup,
                absolute_deadline_monotonic=absolute_deadline_monotonic,
            ).splitlines()
            if line
        ]
    )


def _owned_container_ids(
    budget: CommandBudget,
    *,
    name: str,
    run_id: str,
    marker_alias: str,
    absolute_deadline_monotonic: float,
) -> list[str]:
    output = budget.run(
        [
            DOCKER,
            "ps",
            "-aq",
            "--filter",
            f"name=^{name}$",
            "--filter",
            f"label=giclab.t07.run={run_id}",
            "--filter",
            f"label=giclab.t07.marker={marker_alias}",
        ],
        timeout_seconds=15,
        cleanup=True,
        absolute_deadline_monotonic=absolute_deadline_monotonic,
    )
    identities = [line.decode("ascii", "strict") for line in output.splitlines() if line]
    if any(re.fullmatch(r"[a-f0-9]{64}", identity) is None for identity in identities):
        raise QualificationError("outcome-unknown container identity is malformed")
    return identities


def execute(args: argparse.Namespace) -> tuple[Path, str]:
    guard = QualificationTerminationGuard()
    try:
        return _execute_guarded(args)
    finally:
        guard.close()


def _execute_guarded(args: argparse.Namespace) -> tuple[Path, str]:
    if (
        RUN_ID.fullmatch(args.run_id) is None
        or ALIAS.fullmatch(args.decision_alias) is None
        or ALIAS.fullmatch(args.marker_alias) is None
    ):
        raise QualificationError("qualification identity is invalid")
    if (
        SHA256.fullmatch(args.instance_binding_sha256) is None
        or SHA256.fullmatch(args.authorization_sha256) is None
    ):
        raise QualificationError("qualification binding hash is invalid")
    if not args.authorization_reference.startswith(
        "AUTH-T07-L2M-"
    ) or args.authorization_reference.endswith("PENDING"):
        raise QualificationError("qualification requires a non-pending authorization")
    if SHA256.fullmatch(args.bundle_manifest_sha256) is None:
        raise QualificationError("qualification bundle hash is invalid")
    started = time.monotonic()
    total_deadline = started + TOTAL_WALL_SECONDS
    work_deadline = started + WORK_WALL_SECONDS
    alarm = QualificationAlarm(total_deadline)
    try:
        root = Path(__file__).absolute().parent
        bundle_sha256, verified_payloads = verify_bundle(
            root, expected_manifest_sha256=args.bundle_manifest_sha256
        )
        public_registry_metadata_reverified_at_utc, public_metadata_age_seconds = (
            validate_public_metadata_record(
                verified_payloads["public-source-observations-l2-2.json"]
            )
        )
        docker_module = _load_verified_module(
            "docker_inspector", verified_payloads["docker_inspector.py"]
        )
        packager_module = _load_verified_module(
            "evidence_packager", verified_payloads["evidence_packager.py"]
        )
        host_module = _load_verified_module("host_facts", verified_payloads["host_facts.py"])
        RuntimeCommandBudget = docker_module.CommandBudget
        initial_runtime_observation = docker_module.initial_runtime_observation
        inspect_container = docker_module.inspect_container
        validate_containment_inspect = docker_module.validate_containment_inspect
        sanitize_image_inspect = docker_module.sanitize_image_inspect
        process_structure_report = docker_module.process_structure_report
        fixture_marker_report = docker_module.fixture_marker_report
        package_evidence = packager_module.package_evidence
        package_failure_evidence = packager_module.package_failure_evidence
        require_remote_capacity = packager_module.require_remote_capacity
        validate_remote_retention = packager_module.validate_remote_retention
        max_remote_source_bytes = packager_module.MAX_SOURCE_BYTES
        collect_host_facts = host_module.collect_host_facts
        scan_owned_runtime_residue = host_module.scan_owned_runtime_residue
        validate_host_facts = host_module.validate_host_facts

        output = Path(args.output_dir).resolve()
        success_archive = output.parent / f"{output.name}-evidence.zip"
        failure_root = output.parent / f"{output.name}-failure-staging"
        failure_archive = output.parent / f"{output.name}-failure-evidence.zip"
        require_remote_capacity(output.parent)
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
        fixture_payload = verified_payloads["adversarial-containment.sh"]
        fixture, fixture_record = _materialize_verified_fixture(output, fixture_payload)
        validate_remote_retention(
            success_root=output,
            success_archive=success_archive,
            failure_root=failure_root,
            failure_archive=failure_archive,
        )
        fixture_removed = False
        docker_config = output / ".docker-config"
        docker_config.mkdir(mode=0o700)
        docker_config_removed = False
        budget = RuntimeCommandBudget(docker_config_dir=docker_config)
        alarm.arm(work_deadline)
    except BaseException:
        alarm.close()
        raise
    container_id: str | None = None
    created_container_id: str | None = None
    container_id_sha256: str | None = None
    name: str | None = None
    inspect_documents: list[object] = []
    log_events: list[dict[str, object]] = []
    private_runtime: dict[str, object] = {}
    failure_stage = "host_contract"
    runtime_touched = False
    create_outcome_unknown = False
    try:
        host = collect_host_facts()
        validate_host_facts(host)
        failure_stage = "runtime_observation"
        runtime_touched = True
        runtime, private_runtime = initial_runtime_observation(
            budget,
            absolute_deadline_monotonic=work_deadline,
        )
        if runtime["initial_container_count"] != 0:
            raise QualificationError("qualification host has preexisting containers")
        failure_stage = "image_pull"
        budget.run(
            [DOCKER, "pull", "--platform", "linux/amd64", BUSYBOX],
            timeout_seconds=120,
            absolute_deadline_monotonic=work_deadline,
        )
        image_raw = budget.run(
            [DOCKER, "image", "inspect", BUSYBOX],
            timeout_seconds=15,
            absolute_deadline_monotonic=work_deadline,
        )
        image_record = sanitize_image_inspect(
            image_raw,
            expected_reference=BUSYBOX,
            expected_config_digest=CONFIG_DIGEST,
        )
        image_record_sha256 = hashlib.sha256(canonical(image_record)).hexdigest()
        name = (
            "t07-l2m-" + hashlib.sha256((args.run_id + args.marker_alias).encode()).hexdigest()[:16]
        )
        create_argv = create_arguments(
            name=name, fixture=fixture, run_id=args.run_id, marker_alias=args.marker_alias
        )
        failure_stage = "container_create"
        _verify_staged_fixture(fixture, fixture_payload, fixture_record)
        create_outcome_unknown = True
        created = (
            budget.run(
                create_argv,
                timeout_seconds=30,
                absolute_deadline_monotonic=work_deadline,
            )
            .decode("ascii", "strict")
            .strip()
        )
        if not re.fullmatch(r"[a-f0-9]{64}", created):
            raise QualificationError("Docker did not return one immutable container ID")
        create_outcome_unknown = False
        container_id = created
        created_container_id = created
        _verify_staged_fixture(fixture, fixture_payload, fixture_record)
        container_id_sha256 = hashlib.sha256(created.encode()).hexdigest()
        create_argv_sha256 = hashlib.sha256(canonical(create_argv)).hexdigest()
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "container_created",
                "container_id_sha256": container_id_sha256,
                "create_argv_sha256": create_argv_sha256,
            }
        )
        failure_stage = "containment_inspect"
        before = inspect_container(
            budget,
            container_id,
            absolute_deadline_monotonic=work_deadline,
        )
        inspect_documents.append(before)
        validate_containment_inspect(
            before,
            fixture=fixture,
            run_id=args.run_id,
            marker_alias=args.marker_alias,
            expected_image_id=CONFIG_DIGEST,
        )
        fixture_started = time.monotonic()
        fixture_deadline = min(work_deadline, fixture_started + FIXTURE_WALL_SECONDS)
        alarm.arm(fixture_deadline)
        failure_stage = "container_start"
        budget.run(
            [DOCKER, "start", container_id],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        _bounded_sleep(2, absolute_deadline_monotonic=fixture_deadline)
        failure_stage = "process_evidence"
        top = budget.run(
            [DOCKER, "top", container_id, "-eo", "pid,ppid,sid,stat,comm"],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        pre_stop_process = process_structure_report(top)
        if (
            pre_stop_process["process_count"] < 60
            or pre_stop_process["max_parent_depth"] < 2
            or pre_stop_process["distinct_sid_count"] < 2
            or pre_stop_process["reparented_session_leader_count"] < 1
        ):
            raise QualificationError("adversarial process structure is insufficient")
        fixture_log = budget.run(
            [DOCKER, "logs", "--tail", "256", container_id],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        marker_report = fixture_marker_report(fixture_log)
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "pre_stop_process_evidence",
                "process_count": pre_stop_process["process_count"],
                "report_sha256": pre_stop_process["structural_sha256"],
                "pid_limit_observed": marker_report["pid_limit_observed"],
            }
        )
        failure_stage = "term_survival"
        budget.run(
            [DOCKER, "kill", "--signal", "TERM", container_id],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        _bounded_sleep(1, absolute_deadline_monotonic=fixture_deadline)
        after_term = inspect_container(
            budget,
            container_id,
            absolute_deadline_monotonic=fixture_deadline,
        )
        inspect_documents.append(after_term)
        state = after_term.get("State")
        if not isinstance(state, dict) or state.get("Running") is not True:
            raise QualificationError("adversarial fixture did not survive TERM")
        post_term_top = budget.run(
            [DOCKER, "top", container_id, "-eo", "pid,ppid,sid,stat,comm"],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        post_term_process = process_structure_report(post_term_top)
        if (
            post_term_process["process_count"] < 3
            or post_term_process["max_parent_depth"] < 2
            or post_term_process["distinct_sid_count"] < 2
        ):
            raise QualificationError("TERM-ignoring descendant structure was not proven")
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "term_survived",
                "container_id_sha256": container_id_sha256,
                "process_count": post_term_process["process_count"],
                "report_sha256": post_term_process["structural_sha256"],
            }
        )
        failure_stage = "kill_terminal"
        budget.run(
            [DOCKER, "kill", "--signal", "KILL", container_id],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        budget.run(
            [DOCKER, "wait", container_id],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        terminal = inspect_container(
            budget,
            container_id,
            absolute_deadline_monotonic=fixture_deadline,
        )
        inspect_documents.append(terminal)
        terminal_state = terminal.get("State")
        if not isinstance(terminal_state, dict) or terminal_state.get("Running") is not False:
            raise QualificationError("container terminal state was not proven")
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "kill_terminal",
                "container_id_sha256": container_id_sha256,
            }
        )
        failure_stage = "container_remove"
        budget.run(
            [DOCKER, "rm", container_id],
            timeout_seconds=15,
            absolute_deadline_monotonic=fixture_deadline,
        )
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "container_removed",
                "container_id_sha256": container_id_sha256,
            }
        )
        container_id = None
        alarm.arm(work_deadline)
        failure_stage = "residue_verification"
        residue = {
            "container": _residue_count(
                budget,
                "container",
                args.run_id,
                absolute_deadline_monotonic=work_deadline,
            ),
            "network": _residue_count(
                budget,
                "network",
                args.run_id,
                absolute_deadline_monotonic=work_deadline,
            ),
            "volume": _residue_count(
                budget,
                "volume",
                args.run_id,
                absolute_deadline_monotonic=work_deadline,
            ),
        }
        if any(residue.values()):
            raise QualificationError("owned runtime residue remains")
        failure_stage = "process_residue_verification"
        residue_scan: dict[str, object] | None = None
        for _ in range(5):
            residue_scan = scan_owned_runtime_residue(created_container_id)
            if (
                residue_scan["matched_process_count"] == 0
                and residue_scan["matched_cgroup_count"] == 0
            ):
                break
            _bounded_sleep(1, absolute_deadline_monotonic=work_deadline)
        if (
            residue_scan is None
            or residue_scan["matched_process_count"] != 0
            or residue_scan["matched_cgroup_count"] != 0
        ):
            raise QualificationError("owned process or cgroup residue remains")
        _remove_staged_fixture(fixture, fixture_payload, fixture_record)
        fixture_removed = True
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "residue_verified",
                "container": residue["container"],
                "network": residue["network"],
                "volume": residue["volume"],
            }
        )
        fixture_elapsed = max(1, math.ceil(time.monotonic() - fixture_started))
        if fixture_elapsed > FIXTURE_WALL_SECONDS:
            raise QualificationError("containment fixture wall-time cap exceeded")
        failure_stage = "qualification_wall"
        _check_deadline(work_deadline)
        elapsed = max(1, math.ceil(time.monotonic() - started))
        if elapsed > WORK_WALL_SECONDS:
            raise QualificationError("qualification total wall-time cap exceeded")
        evidence = {
            "schema_version": "0.1.0",
            "run_id": args.run_id,
            "authorization_reference": args.authorization_reference,
            "authorization_sha256": args.authorization_sha256,
            "decision_alias": args.decision_alias,
            "marker_alias": args.marker_alias,
            "instance_binding_sha256": args.instance_binding_sha256,
            "bundle_manifest_sha256": bundle_sha256,
            "host": host,
            "runtime": runtime,
            "busybox": {
                "image_reference": BUSYBOX,
                "manifest_digest": MANIFEST_DIGEST,
                "config_digest": CONFIG_DIGEST,
                "layer_digest": LAYER_DIGEST,
                "layer_bytes": 2211507,
                "platform": "linux/amd64",
                "config_metadata_platform_proven": True,
                "public_metadata_observation_sha256": PUBLIC_METADATA_OBSERVATION_SHA256,
                "public_registry_metadata_reverified_at_utc": (
                    public_registry_metadata_reverified_at_utc
                ),
                "public_registry_metadata_reverified_before_qualification": True,
                "public_metadata_binding_validated_during_qualification": True,
                "public_metadata_age_seconds": public_metadata_age_seconds,
                "public_registry_metadata_request_during_qualification": False,
                "pull_count": 1,
                "image_record_sha256": image_record_sha256,
            },
            "containment": {
                "container_id_sha256": container_id_sha256,
                "create_argv_sha256": create_argv_sha256,
                "fixture_sha256": fixture_record["sha256"],
                "fixture_identity_sha256": fixture_record["identity_sha256"],
                "network_none": True,
                "private_pid_namespace": True,
                "private_cgroup_namespace": True,
                "private_ipc_namespace": True,
                "privileged": False,
                "cap_drop_all": True,
                "no_new_privileges": True,
                "read_only_root": True,
                "restart_policy": "no",
                "cpu_limit_millis": 1000,
                "memory_bytes": 536870912,
                "memory_swap_bytes": 536870912,
                "pid_limit": 64,
                "tmpfs_bytes_each": 16777216,
                "shm_bytes": 16777216,
                "workload_wall_seconds": fixture_elapsed,
                "term_sent": True,
                "kill_escalated": True,
                "terminal_proven": True,
                "removed": True,
                "owned_container_residue_count": residue["container"],
                "owned_network_residue_count": residue["network"],
                "owned_volume_residue_count": residue["volume"],
                "background_process_residue_count": 0,
                "owned_cgroup_residue_count": 0,
                "residue_scan_sha256": residue_scan["scan_sha256"],
                "residue_scanned_process_count": residue_scan["scanned_process_count"],
                "residue_scanned_cgroup_entries": residue_scan["scanned_cgroup_entries"],
                "pre_stop_process_count": pre_stop_process["process_count"],
                "pre_stop_max_parent_depth": pre_stop_process["max_parent_depth"],
                "pre_stop_distinct_sid_count": pre_stop_process["distinct_sid_count"],
                "pre_stop_reparented_session_leader_count": pre_stop_process[
                    "reparented_session_leader_count"
                ],
                "post_term_process_count": post_term_process["process_count"],
                "post_term_max_parent_depth": post_term_process["max_parent_depth"],
                "post_term_distinct_sid_count": post_term_process["distinct_sid_count"],
                "pid_limit_observed": True,
                "term_ignoring_descendants_proven": True,
                "process_structure_sha256": hashlib.sha256(
                    canonical(
                        {
                            "fixture_markers": marker_report,
                            "post_term": post_term_process,
                            "pre_stop": pre_stop_process,
                        }
                    )
                ).hexdigest(),
            },
            "prohibitions": {
                "ssh_operations": 0,
                "model_calls": 0,
                "browser_actions": 0,
                "sira_executions": 0,
                "scientific_executions": 0,
                "apt_operations": 0,
                "runtime_updates": 0,
                "secrets_accessed": 0,
            },
        }
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "qualification_passed",
                "elapsed_seconds": elapsed,
            }
        )
        failure_stage = "evidence_write"
        success_payloads = {
            "host-evidence.json": canonical(evidence) + b"\n",
            "container-inspect.json": canonical(
                {
                    "documents": inspect_documents,
                    "fixture_markers": marker_report,
                    "fixture": fixture_record,
                    "image": image_record,
                    "post_term_process": post_term_process,
                    "pre_stop_process": pre_stop_process,
                    "residue_scan": residue_scan,
                    "runtime": private_runtime,
                }
            )
            + b"\n",
            "qualification-log.jsonl": b"".join(canonical(event) + b"\n" for event in log_events),
        }
        if sum(len(value) for value in success_payloads.values()) > max_remote_source_bytes:
            raise QualificationError("success evidence sources exceed their cap")
        for name, encoded in success_payloads.items():
            write_bytes_exclusive(
                output / name,
                encoded,
                absolute_deadline_monotonic=work_deadline,
            )
        validate_remote_retention(
            success_root=output,
            success_archive=success_archive,
            failure_root=failure_root,
            failure_archive=failure_archive,
        )
        failure_stage = "evidence_package"
        docker_config.rmdir()
        docker_config_removed = True
        _, archive_sha256 = package_evidence(
            output,
            success_archive,
            absolute_deadline_monotonic=work_deadline,
            clock=time.monotonic,
        )
        validate_remote_retention(
            success_root=output,
            success_archive=success_archive,
            failure_root=failure_root,
            failure_archive=failure_archive,
        )
        _check_deadline(work_deadline)
        alarm.close()
        return success_archive, archive_sha256
    except BaseException:
        try:
            alarm.arm(total_deadline)
        except Exception:
            alarm.close()
            raise
        # `docker create` can succeed server-side while its CLI response is lost,
        # times out, or is malformed.  Observe a bounded quiescence window for only
        # the deterministic-name and dual-label identity.  A late exact match is
        # validated and thereafter mutated only by immutable ID.  No appearance by
        # the deadline remains outcome-unknown and can never claim complete cleanup.
        create_outcome_observations = 0
        create_outcome_resolution = (
            "unresolved_no_match" if create_outcome_unknown else "not_applicable"
        )
        create_outcome_quiescence_proven = not create_outcome_unknown
        if create_outcome_unknown and container_id is None and runtime_touched and name is not None:
            try:
                for observation_index in range(CREATE_OUTCOME_POLL_OBSERVATIONS):
                    recovered_ids = _owned_container_ids(
                        budget,
                        name=name,
                        run_id=args.run_id,
                        marker_alias=args.marker_alias,
                        absolute_deadline_monotonic=total_deadline,
                    )
                    create_outcome_observations += 1
                    if len(recovered_ids) == 1:
                        recovered_id = recovered_ids[0]
                        recovered_inspect = inspect_container(
                            budget,
                            recovered_id,
                            cleanup=True,
                            absolute_deadline_monotonic=total_deadline,
                        )
                        validate_containment_inspect(
                            recovered_inspect,
                            fixture=fixture,
                            run_id=args.run_id,
                            marker_alias=args.marker_alias,
                            expected_image_id=CONFIG_DIGEST,
                        )
                        inspect_documents.append(recovered_inspect)
                        container_id = recovered_id
                        created_container_id = recovered_id
                        container_id_sha256 = hashlib.sha256(recovered_id.encode()).hexdigest()
                        create_outcome_resolution = "recovered_pending_stable_absence"
                        break
                    if recovered_ids:
                        create_outcome_resolution = "ambiguous"
                        break
                    if observation_index + 1 < CREATE_OUTCOME_POLL_OBSERVATIONS:
                        _bounded_sleep(
                            CREATE_OUTCOME_POLL_INTERVAL_SECONDS,
                            absolute_deadline_monotonic=total_deadline,
                        )
            except Exception:
                container_id = None
                create_outcome_resolution = "ambiguous"
        cleanup: dict[str, object] = {
            "container_id_sha256": container_id_sha256,
            "kill_attempted": container_id is not None,
            "kill_succeeded": container_id is None,
            "remove_attempted": container_id is not None,
            "remove_succeeded": container_id is None,
            "container_residue_count": None if runtime_touched else 0,
            "network_residue_count": None if runtime_touched else 0,
            "volume_residue_count": None if runtime_touched else 0,
            "docker_config_removed": False,
            "fixture_removed": False,
            "process_residue_count": 0 if created_container_id is None else None,
            "cgroup_residue_count": 0 if created_container_id is None else None,
            "residue_scan_sha256": None,
            "residue_scanned_process_count": None,
            "residue_scanned_cgroup_entries": None,
            "create_outcome_unknown": create_outcome_unknown,
            "create_outcome_observations": create_outcome_observations,
            "create_outcome_resolution": create_outcome_resolution,
            "create_outcome_quiescence_proven": create_outcome_quiescence_proven,
        }
        if container_id is not None:
            try:
                budget.run(
                    [DOCKER, "kill", "--signal", "KILL", container_id],
                    timeout_seconds=15,
                    cleanup=True,
                    absolute_deadline_monotonic=total_deadline,
                )
                cleanup["kill_succeeded"] = True
            except Exception:
                cleanup["kill_succeeded"] = False
            try:
                budget.run(
                    [DOCKER, "rm", "--force", container_id],
                    timeout_seconds=15,
                    cleanup=True,
                    absolute_deadline_monotonic=total_deadline,
                )
                cleanup["remove_succeeded"] = True
            except Exception:
                cleanup["remove_succeeded"] = False
        if (
            create_outcome_unknown
            and container_id is not None
            and name is not None
            and cleanup["remove_succeeded"] is True
        ):
            stable_absence_observations = 0
            try:
                for observation_index in range(CREATE_OUTCOME_STABLE_ABSENCE_OBSERVATIONS):
                    remaining_ids = _owned_container_ids(
                        budget,
                        name=name,
                        run_id=args.run_id,
                        marker_alias=args.marker_alias,
                        absolute_deadline_monotonic=total_deadline,
                    )
                    create_outcome_observations += 1
                    if remaining_ids:
                        create_outcome_resolution = "late_residue"
                        break
                    stable_absence_observations += 1
                    if observation_index + 1 < CREATE_OUTCOME_STABLE_ABSENCE_OBSERVATIONS:
                        _bounded_sleep(
                            CREATE_OUTCOME_POLL_INTERVAL_SECONDS,
                            absolute_deadline_monotonic=total_deadline,
                        )
                if stable_absence_observations == CREATE_OUTCOME_STABLE_ABSENCE_OBSERVATIONS:
                    create_outcome_quiescence_proven = True
                    create_outcome_resolution = "recovered_and_stably_absent"
            except Exception:
                create_outcome_resolution = "quiescence_failed"
            cleanup["create_outcome_observations"] = create_outcome_observations
            cleanup["create_outcome_resolution"] = create_outcome_resolution
            cleanup["create_outcome_quiescence_proven"] = create_outcome_quiescence_proven
        if runtime_touched:
            for resource in ("container", "network", "volume"):
                try:
                    cleanup[f"{resource}_residue_count"] = _residue_count(
                        budget,
                        resource,
                        args.run_id,
                        cleanup=True,
                        absolute_deadline_monotonic=total_deadline,
                    )
                except Exception:
                    cleanup[f"{resource}_residue_count"] = None
        failure_residue_scan: dict[str, object] | None = None
        if created_container_id is not None:
            try:
                for attempt in range(5):
                    failure_residue_scan = scan_owned_runtime_residue(created_container_id)
                    if (
                        failure_residue_scan["matched_process_count"] == 0
                        and failure_residue_scan["matched_cgroup_count"] == 0
                    ):
                        break
                    if attempt < 4:
                        _bounded_sleep(1, absolute_deadline_monotonic=total_deadline)
                if failure_residue_scan is None:
                    raise QualificationError("failure residue scan produced no evidence")
                cleanup["process_residue_count"] = failure_residue_scan["matched_process_count"]
                cleanup["cgroup_residue_count"] = failure_residue_scan["matched_cgroup_count"]
                cleanup["residue_scan_sha256"] = failure_residue_scan["scan_sha256"]
                cleanup["residue_scanned_process_count"] = failure_residue_scan[
                    "scanned_process_count"
                ]
                cleanup["residue_scanned_cgroup_entries"] = failure_residue_scan[
                    "scanned_cgroup_entries"
                ]
            except Exception:
                cleanup["process_residue_count"] = None
                cleanup["cgroup_residue_count"] = None
        if docker_config_removed:
            cleanup["docker_config_removed"] = True
        else:
            try:
                docker_config.rmdir()
                cleanup["docker_config_removed"] = True
            except OSError:
                cleanup["docker_config_removed"] = False
        if fixture_removed:
            cleanup["fixture_removed"] = True
        else:
            try:
                _remove_staged_fixture(fixture, fixture_payload, fixture_record)
                cleanup["fixture_removed"] = True
            except (OSError, QualificationError):
                cleanup["fixture_removed"] = False
        cleanup_complete = (
            cleanup["remove_succeeded"] is True
            and cleanup["container_residue_count"] == 0
            and cleanup["network_residue_count"] == 0
            and cleanup["volume_residue_count"] == 0
            and cleanup["process_residue_count"] == 0
            and cleanup["cgroup_residue_count"] == 0
            and cleanup["docker_config_removed"] is True
            and cleanup["fixture_removed"] is True
            and cleanup["create_outcome_quiescence_proven"] is True
        )
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "qualification_failed",
                "failure_stage": failure_stage,
            }
        )
        log_events.append(
            {
                "sequence": len(log_events) + 1,
                "event": "emergency_cleanup_observed",
                "cleanup_complete": cleanup_complete,
                "cleanup": cleanup,
            }
        )
        try:
            require_remote_capacity(output.parent)
            validate_remote_retention(
                success_root=output,
                success_archive=success_archive,
                failure_root=failure_root,
                failure_archive=failure_archive,
            )
            failure_root.mkdir(mode=0o700, parents=False, exist_ok=False)
            failure_payloads = {
                "qualification-failure.json": canonical(
                    {
                        "schema_version": "0.1.0",
                        "run_id": args.run_id,
                        "authorization_reference": args.authorization_reference,
                        "authorization_sha256": args.authorization_sha256,
                        "decision_alias": args.decision_alias,
                        "marker_alias": args.marker_alias,
                        "instance_binding_sha256": args.instance_binding_sha256,
                        "bundle_manifest_sha256": bundle_sha256,
                        "sanitized_failure_stage": failure_stage,
                        "cleanup": cleanup,
                        "cleanup_complete": cleanup_complete,
                        "provider_termination_required": True,
                    }
                )
                + b"\n",
                "container-inspect.json": canonical(
                    {
                        "documents": inspect_documents,
                        "residue_scan": failure_residue_scan,
                        "runtime": private_runtime,
                    }
                )
                + b"\n",
                "qualification-log.jsonl": b"".join(
                    canonical(event) + b"\n" for event in log_events
                ),
            }
            if sum(len(value) for value in failure_payloads.values()) > max_remote_source_bytes:
                raise QualificationError("failure evidence sources exceed their cap")
            for name, encoded in failure_payloads.items():
                write_bytes_exclusive(
                    failure_root / name,
                    encoded,
                    absolute_deadline_monotonic=total_deadline,
                )
            validate_remote_retention(
                success_root=output,
                success_archive=success_archive,
                failure_root=failure_root,
                failure_archive=failure_archive,
            )
            _, failure_sha256 = package_failure_evidence(
                failure_root,
                failure_archive,
                absolute_deadline_monotonic=total_deadline,
                clock=time.monotonic,
            )
            validate_remote_retention(
                success_root=output,
                success_archive=success_archive,
                failure_root=failure_root,
                failure_archive=failure_archive,
            )
            _check_deadline(total_deadline)
        finally:
            alarm.close()
        raise QualificationFailed(
            failure_archive,
            failure_sha256,
            cleanup_incident=not cleanup_complete,
        ) from None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--run-id", required=True)
    result.add_argument("--decision-alias", required=True)
    result.add_argument("--marker-alias", required=True)
    result.add_argument("--instance-binding-sha256", required=True)
    result.add_argument("--authorization-reference", required=True)
    result.add_argument("--authorization-sha256", required=True)
    result.add_argument("--bundle-manifest-sha256", required=True)
    result.add_argument("--output-dir", required=True)
    return result


def _main_impl(argv: list[str] | None = None) -> int:
    try:
        archive, digest = execute(parser().parse_args(argv))
    except QualificationFailed as failure:
        incident = "true" if failure.cleanup_incident else "false"
        print(
            "T07_L2M_QUALIFICATION=failed "
            f"archive={failure.archive.name} sha256={failure.sha256} "
            f"cleanup_incident={incident}",
            flush=True,
        )
        return 1
    except BaseException:
        print(
            "T07_L2M_QUALIFICATION=failed evidence_archive=unavailable "
            "cleanup_incident=true provider_termination_required=true",
            flush=True,
        )
        return 1
    print(f"T07_L2M_QUALIFICATION=success archive={archive.name} sha256={digest}", flush=True)
    return 0


def main(
    argv: list[str] | None = None,
    *,
    _bootstrap_capability: object | None = None,
) -> int:
    """Enter only through the hash-first isolated bootstrap."""

    if (
        __name__ != "__t07_l2m_verified_driver__"
        or _VERIFIED_BOOTSTRAP_CAPABILITY is None
        or _bootstrap_capability is not _VERIFIED_BOOTSTRAP_CAPABILITY
    ):
        print("T07_L2M_QUALIFICATION=refused bootstrap_verification=required", flush=True)
        return 126
    return _main_impl(argv)


if __name__ == "__main__":
    raise SystemExit(main())
