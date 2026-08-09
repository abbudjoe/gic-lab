"""Secret-safe supervisor for a separately authorized T07 Gate L1 inventory.

Importing this module performs no I/O.  The concrete transport issues only the
eight GETs in the hash-bound plan, never follows redirects, and never exposes a
response body or authorization header through an error. Success also requires the
guarded durable archive contract. Tests inject fake transport/archive boundaries;
Gate L0 never invokes either concrete boundary or reads a secret.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import os
import select
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypeAlias, cast

from giclab.validation import validate_instance

from .lambda_archive import (
    ArchivedInventoryArtifact,
    DurableInventoryArchiver,
    InventoryArchiver,
)
from .lambda_cloud import (
    LAMBDA_BRANCH,
    MAX_INVENTORY_TOTAL_WALL_SECONDS,
    MAX_INVENTORY_WALL_SECONDS,
    ComputeCandidate,
    InstanceSelectionError,
    InventoryRequest,
    InventoryRunBinding,
    LambdaCloudContractError,
    ReadOnlyInventoryPlan,
    canonical_inventory_bytes,
    inventory_document,
    load_inventory_plan,
    parse_inventory_responses,
    secret_free_child_environment,
    select_compute_candidate,
)

SocketAddress: TypeAlias = tuple[str, int] | tuple[str, int, int, int]
AddressInfo: TypeAlias = tuple[int, int, int, str, SocketAddress]


@dataclass(frozen=True, slots=True)
class InventoryHttpResponse:
    status_code: int
    body: bytes


class InventoryTransport(Protocol):
    """Minimal injectable boundary for one exact inventory GET."""

    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> InventoryHttpResponse: ...


class ProcessDeadline(Protocol):
    """A separately running watchdog capable of killing a stalled supervisor."""

    def close(self) -> None: ...


ProcessDeadlineFactory: TypeAlias = Callable[[int], ProcessDeadline]


@dataclass(slots=True)
class SubprocessDeadlineWatchdog:
    """Secret-free helper process enforcing a hard monotonic parent deadline."""

    process: subprocess.Popen[bytes]
    control_descriptor: int
    closed: bool = False

    @classmethod
    def arm(cls, seconds: int) -> SubprocessDeadlineWatchdog:
        if type(seconds) is not int or seconds not in {
            MAX_INVENTORY_TOTAL_WALL_SECONDS,
            MAX_INVENTORY_WALL_SECONDS,
        }:
            raise LambdaCloudContractError("inventory process deadline is not an approved cap")
        read_descriptor, write_descriptor = os.pipe()
        ready_read_descriptor, ready_write_descriptor = os.pipe()
        command = [
            sys.executable,
            "-m",
            "giclab.harness.lambda_inventory",
            "_deadline-watchdog",
            str(read_descriptor),
            str(ready_write_descriptor),
            str(os.getpid()),
            str(seconds),
        ]
        # The watchdog needs no inherited configuration. In particular, it never
        # receives the provider credential or either forbidden fallback secret.
        safe_environment = secret_free_child_environment()
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                pass_fds=(read_descriptor, ready_write_descriptor),
                env=safe_environment,
            )
        except (OSError, subprocess.SubprocessError):
            os.close(read_descriptor)
            os.close(write_descriptor)
            os.close(ready_read_descriptor)
            os.close(ready_write_descriptor)
            raise LambdaCloudContractError(
                "inventory hard-deadline watchdog failed to arm"
            ) from None
        os.close(read_descriptor)
        os.close(ready_write_descriptor)
        try:
            readable, _, _ = select.select((ready_read_descriptor,), (), (), 2)
            ready = os.read(ready_read_descriptor, 1) if readable else b""
        except (OSError, ValueError):
            ready = b""
        finally:
            os.close(ready_read_descriptor)
        if ready != b"R" or process.poll() is not None:
            process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)
            os.close(write_descriptor)
            raise LambdaCloudContractError("inventory hard-deadline watchdog failed to arm")
        return cls(process=process, control_descriptor=write_descriptor)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(OSError):
            os.write(self.control_descriptor, b"\x00")
        os.close(self.control_descriptor)
        try:
            return_code = self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                raise LambdaCloudContractError(
                    "inventory hard-deadline watchdog did not terminate"
                ) from None
            raise LambdaCloudContractError(
                "inventory hard-deadline watchdog required forced cleanup"
            ) from None
        if return_code != 0:
            raise LambdaCloudContractError("inventory hard-deadline watchdog failed")


def _deadline_watchdog_main(arguments: Sequence[str]) -> int:
    """Wait for disarm or SIGKILL the exact parent at the approved deadline."""

    if len(arguments) != 4:
        return 2
    try:
        read_descriptor, ready_descriptor, target_pid, seconds = (int(value) for value in arguments)
    except ValueError:
        return 2
    if (
        read_descriptor < 0
        or ready_descriptor < 0
        or target_pid != os.getppid()
        or seconds not in {MAX_INVENTORY_TOTAL_WALL_SECONDS, MAX_INVENTORY_WALL_SECONDS}
    ):
        return 2
    deadline = time.monotonic() + seconds
    try:
        if os.write(ready_descriptor, b"R") != 1:
            return 2
        os.close(ready_descriptor)
        ready_descriptor = -1
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(target_pid, signal.SIGKILL)
                return 124
            readable, _, _ = select.select((read_descriptor,), (), (), remaining)
            if readable:
                # A byte means orderly disarm; EOF means the parent already exited.
                os.read(read_descriptor, 1)
                return 0
    except (OSError, ValueError):
        return 2
    finally:
        with contextlib.suppress(OSError):
            os.close(read_descriptor)
        if ready_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(ready_descriptor)


@contextlib.contextmanager
def _armed_process_deadline(factory: ProcessDeadlineFactory, seconds: int) -> Iterator[None]:
    watchdog = factory(seconds)
    try:
        yield
    finally:
        watchdog.close()


@dataclass(frozen=True, slots=True)
class RepositoryState:
    branch: str
    commit: str
    clean: bool


@dataclass(frozen=True, slots=True)
class SealedInventoryArtifact:
    path: Path
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class InventoryRunResult:
    run_id: str
    authorization_reference: str
    artifact: SealedInventoryArtifact
    archive: ArchivedInventoryArtifact
    copy_record: SealedInventoryArtifact
    selection_state: str
    candidate: ComputeCandidate | None
    blocked_reason: str | None
    provider_calls: int


def _bounded_resolve(
    *, host: str, port: int, deadline: float, clock: Callable[[], float]
) -> tuple[AddressInfo, ...]:
    """Resolve without allowing an unbounded libc resolver call on the main thread."""

    values: list[AddressInfo] = []
    failed = False
    complete = threading.Event()

    def resolve() -> None:
        nonlocal failed
        try:
            raw = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            values.extend(cast(list[AddressInfo], raw))
        except OSError:
            failed = True
        finally:
            complete.set()

    worker = threading.Thread(target=resolve, name="t07-l1-dns", daemon=True)
    worker.start()
    remaining = deadline - clock()
    if remaining <= 0 or not complete.wait(remaining):
        raise LambdaCloudContractError("inventory DNS resolution exceeded its wall budget")
    if failed or not values:
        raise LambdaCloudContractError("inventory DNS resolution failed")
    return tuple(values)


class _ResolvedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        addresses: Sequence[AddressInfo],
        *,
        deadline: float,
        clock: Callable[[], float],
        context: ssl.SSLContext,
    ) -> None:
        initial_remaining = deadline - clock()
        super().__init__(
            "cloud.lambda.ai",
            443,
            timeout=max(initial_remaining, 0.001),
            context=context,
        )
        self._addresses = tuple(addresses)
        self._t07_context = context
        self._deadline = deadline
        self._clock = clock

    def connect(self) -> None:
        last_failure = False
        for family, socket_type, protocol, _, socket_address in self._addresses:
            remaining = self._deadline - self._clock()
            if remaining <= 0:
                raise TimeoutError("Lambda API connection deadline expired")
            raw_socket = socket.socket(family, socket_type, protocol)
            self.sock = raw_socket
            try:
                raw_socket.settimeout(remaining)
                raw_socket.connect(socket_address)
                remaining = self._deadline - self._clock()
                if remaining <= 0:
                    raise TimeoutError("Lambda API TLS deadline expired")
                raw_socket.settimeout(remaining)
                self.sock = self._t07_context.wrap_socket(
                    raw_socket,
                    server_hostname="cloud.lambda.ai",
                )
                if self._clock() > self._deadline:
                    raise TimeoutError("Lambda API TLS deadline expired")
                return
            except OSError:
                last_failure = True
                raw_socket.close()
                self.sock = None
        if last_failure:
            raise OSError("all resolved Lambda API addresses failed")
        raise OSError("no resolved Lambda API address")


class LambdaHttpsInventoryTransport:
    """Non-redirecting HTTPS transport fixed to Lambda's production API host."""

    def __init__(
        self,
        *,
        ssl_context: ssl.SSLContext | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ssl_context = ssl_context or ssl.create_default_context()
        self._clock = clock

    def fetch(
        self,
        request: InventoryRequest,
        *,
        credential: str,
        timeout_seconds: float,
    ) -> InventoryHttpResponse:
        if not credential or "\r" in credential or "\n" in credential:
            raise LambdaCloudContractError("LAMBDA_API_KEY is missing or malformed")
        if timeout_seconds <= 0 or timeout_seconds > MAX_INVENTORY_WALL_SECONDS:
            raise LambdaCloudContractError("inventory request timeout is outside its budget")
        deadline = self._clock() + timeout_seconds
        addresses = _bounded_resolve(
            host="cloud.lambda.ai",
            port=443,
            deadline=deadline,
            clock=self._clock,
        )
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise LambdaCloudContractError("inventory request exceeded its wall budget")
        connection = _ResolvedHTTPSConnection(
            addresses,
            deadline=deadline,
            clock=self._clock,
            context=self._ssl_context,
        )

        def expire_connection() -> None:
            active_socket = connection.sock
            if active_socket is not None:
                with contextlib.suppress(OSError):
                    active_socket.shutdown(socket.SHUT_RDWR)
            connection.close()

        watchdog = threading.Timer(remaining, expire_connection)
        watchdog.daemon = True
        watchdog.start()
        try:
            connection.request(
                "GET",
                request.path,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {credential}",
                    "User-Agent": "giclab-t07-gate-l1/1",
                },
            )
            response = connection.getresponse()
            # Redirects are never followed. All non-200 statuses are a categorical
            # failure; response headers, reason phrases, and bodies stay unreported.
            if response.status != 200:
                raise LambdaCloudContractError(f"{request.request_id} returned a non-200 status")
            chunks: list[bytes] = []
            observed_bytes = 0
            while True:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    raise LambdaCloudContractError(f"{request.request_id} exceeded its wall budget")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read(min(65_536, request.max_response_bytes + 1 - observed_bytes))
                if not chunk:
                    break
                chunks.append(chunk)
                observed_bytes += len(chunk)
                if observed_bytes > request.max_response_bytes:
                    raise LambdaCloudContractError(
                        f"{request.request_id} response exceeds its byte cap"
                    )
            body = b"".join(chunks)
            if self._clock() > deadline:
                raise LambdaCloudContractError(f"{request.request_id} exceeded its wall budget")
            return InventoryHttpResponse(status_code=response.status, body=body)
        except LambdaCloudContractError:
            raise
        except (OSError, http.client.HTTPException, ssl.SSLError):
            raise LambdaCloudContractError(f"{request.request_id} transport failed") from None
        finally:
            watchdog.cancel()
            connection.close()


def inspect_repository_state(repository_root: Path, *, expected_commit: str) -> RepositoryState:
    """Fail closed unless the exact Gate L0 branch/commit is clean."""

    root = repository_root.resolve(strict=True)
    total_output_bytes = 0

    def git(*arguments: str) -> str:
        nonlocal total_output_bytes
        result = subprocess.run(
            ["/usr/bin/git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env=secret_free_child_environment(),
        )
        total_output_bytes += len(result.stdout.encode()) + len(result.stderr.encode())
        if total_output_bytes > 65_536:
            raise LambdaCloudContractError("repository state output exceeded its byte cap")
        return result.stdout.strip()

    try:
        state = RepositoryState(
            branch=git("branch", "--show-current"),
            commit=git("rev-parse", "HEAD"),
            clean=git("status", "--porcelain=v1", "--untracked-files=normal") == "",
        )
    except (OSError, subprocess.SubprocessError):
        raise LambdaCloudContractError("repository state inspection failed") from None
    if state.branch != LAMBDA_BRANCH:
        raise LambdaCloudContractError("inventory repository branch drifted")
    if state.commit != expected_commit:
        raise LambdaCloudContractError("inventory repository commit drifted")
    if not state.clean:
        raise LambdaCloudContractError("inventory repository is not clean")
    return state


def _ensure_private_directory_chain(root: Path, relative_parent: Path) -> Path:
    if relative_parent.is_absolute() or ".." in relative_parent.parts:
        raise LambdaCloudContractError("inventory artifact directory escapes repository root")
    current = root
    for component in relative_parent.parts:
        current = current / component
        try:
            status = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            status = current.lstat()
        if current.is_symlink() or not current.is_dir():
            raise LambdaCloudContractError("inventory artifact directory is not a real directory")
        if status.st_uid != os.getuid():
            raise LambdaCloudContractError("inventory artifact directory is not user-owned")
    return current


def seal_inventory_artifact(
    repository_root: Path,
    *,
    relative_path: str,
    encoded: bytes,
    max_bytes: int,
) -> SealedInventoryArtifact:
    """Create one redacted file without overwrite, then fsync file and directory."""

    if len(encoded) > max_bytes:
        raise LambdaCloudContractError("inventory artifact exceeds its retained-output cap")
    root = repository_root.resolve(strict=True)
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.name in {"", ".", ".."}:
        raise LambdaCloudContractError("inventory artifact path is not confined")
    parent = _ensure_private_directory_chain(root, relative.parent)
    target = parent / relative.name
    if target.exists() or target.is_symlink():
        raise LambdaCloudContractError("inventory artifact target already exists")
    temporary = parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    linked = False
    try:
        descriptor = os.open(temporary, flags, 0o600)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written < 1:
                raise LambdaCloudContractError("inventory artifact write made no progress")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary, target, follow_symlinks=False)
        linked = True
        temporary.unlink()
        directory_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError:
        raise LambdaCloudContractError("inventory artifact seal failed") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink(missing_ok=True)
        if linked and not target.exists():
            raise LambdaCloudContractError("inventory artifact disappeared during seal")
    observed = target.read_bytes()
    if observed != encoded:
        raise LambdaCloudContractError("inventory artifact verification failed")
    return SealedInventoryArtifact(
        path=target,
        sha256=hashlib.sha256(observed).hexdigest(),
        bytes=len(observed),
    )


def execute_authorized_inventory(
    *,
    repository_root: Path,
    plan_path: Path,
    plan_sha256: str,
    run_binding: InventoryRunBinding,
    credential: str,
    transport: InventoryTransport,
    archiver: InventoryArchiver,
    watchdog_factory: ProcessDeadlineFactory = SubprocessDeadlineWatchdog.arm,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> InventoryRunResult:
    """Execute one L1 plan under an authoritative whole-process deadline."""

    with _armed_process_deadline(watchdog_factory, MAX_INVENTORY_TOTAL_WALL_SECONDS):
        return _execute_inventory_within_total_deadline(
            repository_root=repository_root,
            plan_path=plan_path,
            plan_sha256=plan_sha256,
            run_binding=run_binding,
            credential=credential,
            transport=transport,
            archiver=archiver,
            watchdog_factory=watchdog_factory,
            clock=clock,
            sleeper=sleeper,
            utc_now=utc_now,
        )


def _execute_inventory_within_total_deadline(
    *,
    repository_root: Path,
    plan_path: Path,
    plan_sha256: str,
    run_binding: InventoryRunBinding,
    credential: str,
    transport: InventoryTransport,
    archiver: InventoryArchiver,
    watchdog_factory: ProcessDeadlineFactory,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
    utc_now: Callable[[], datetime],
) -> InventoryRunResult:
    """Run inside the already armed hard total deadline."""

    if not credential or "\r" in credential or "\n" in credential:
        raise LambdaCloudContractError("LAMBDA_API_KEY is missing or malformed")
    total_started = clock()

    def check_total_wall() -> None:
        if clock() - total_started > plan.max_total_wall_seconds:
            raise LambdaCloudContractError("inventory total wall budget expired")

    inspect_repository_state(repository_root, expected_commit=run_binding.repository_commit)
    plan: ReadOnlyInventoryPlan = load_inventory_plan(plan_path, expected_sha256=plan_sha256)
    check_total_wall()
    prepared_archive = archiver.prepare(
        repository_root,
        plan=plan,
        plan_sha256=plan_sha256,
        run_binding=run_binding,
    )
    try:
        check_total_wall()
        provider_started = clock()
        previous_request_started: float | None = None
        responses: dict[str, bytes] = {}
        for request in plan.requests:
            if previous_request_started is not None:
                spacing_remaining = plan.request_start_spacing_seconds - (
                    clock() - previous_request_started
                )
                if spacing_remaining > 0:
                    if clock() - provider_started + spacing_remaining > plan.max_wall_seconds:
                        raise LambdaCloudContractError("inventory provider wall budget expired")
                    sleeper(spacing_remaining)
            elapsed = clock() - provider_started
            remaining = plan.max_wall_seconds - elapsed
            if remaining <= 0:
                raise LambdaCloudContractError("inventory provider wall budget expired")
            previous_request_started = clock()
            response = transport.fetch(request, credential=credential, timeout_seconds=remaining)
            if response.status_code != 200:
                raise LambdaCloudContractError(f"{request.request_id} returned a non-200 status")
            if len(response.body) > request.max_response_bytes:
                raise LambdaCloudContractError(
                    f"{request.request_id} response exceeds its byte cap"
                )
            responses[request.request_id] = response.body
        if clock() - provider_started > plan.max_wall_seconds:
            raise LambdaCloudContractError("inventory provider wall budget expired")
        check_total_wall()
        inventory = parse_inventory_responses(responses, plan)
        candidate: ComputeCandidate | None = None
        selection_failure: InstanceSelectionError | None = None
        try:
            candidate = select_compute_candidate(inventory)
        except InstanceSelectionError as exc:
            selection_failure = exc
        observed_at = utc_now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        document = inventory_document(
            inventory,
            candidate,
            observed_at_utc=observed_at,
            inventory_plan_sha256=plan_sha256,
            run_binding=run_binding,
            selection_failure=selection_failure,
        )
        schema_errors = validate_instance(
            document, repository_root / "schemas/t07-lambda-inventory.schema.json"
        )
        if schema_errors:
            raise LambdaCloudContractError("redacted inventory artifact failed schema validation")
        encoded = canonical_inventory_bytes(document)
        if credential.encode() in encoded:
            raise LambdaCloudContractError("secret canary reached redacted inventory output")
        check_total_wall()
        artifact = seal_inventory_artifact(
            repository_root,
            relative_path=plan.output_relative_path,
            encoded=encoded,
            max_bytes=plan.max_retained_output_bytes,
        )
        check_total_wall()
        with _armed_process_deadline(watchdog_factory, plan.max_archive_wall_seconds):
            archived = prepared_archive.archive(
                artifact.path,
                artifact_sha256=artifact.sha256,
                artifact_bytes=artifact.bytes,
            )
        if credential.encode() in archived.local_verification_record:
            raise LambdaCloudContractError("secret canary reached archive verification output")
        copy_record = seal_inventory_artifact(
            repository_root,
            relative_path=plan.copy_record_relative_path,
            encoded=archived.local_verification_record,
            max_bytes=plan.max_local_record_bytes,
        )
        free_bytes = os.statvfs(repository_root).f_bavail * os.statvfs(repository_root).f_frsize
        if free_bytes < plan.local_retained_floor_bytes:
            raise LambdaCloudContractError("Mac mini retained-free floor failed after Gate L1")
        check_total_wall()
        return InventoryRunResult(
            run_id=run_binding.run_id,
            authorization_reference=run_binding.authorization_reference,
            artifact=artifact,
            archive=archived,
            copy_record=copy_record,
            selection_state="selected" if candidate is not None else "blocked",
            candidate=candidate,
            blocked_reason=(
                selection_failure.code.value if selection_failure is not None else None
            ),
            provider_calls=len(responses),
        )
    finally:
        prepared_archive.close()


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
    """Run the exact future operation; Gate L0 tests never call this entry point."""

    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if raw_arguments[:1] == ["_deadline-watchdog"]:
        return _deadline_watchdog_main(raw_arguments[1:])
    args = _parser().parse_args(raw_arguments)
    try:
        with _armed_process_deadline(
            SubprocessDeadlineWatchdog.arm, MAX_INVENTORY_TOTAL_WALL_SECONDS
        ):
            provider_credential = os.environ.get("LAMBDA_API_KEY")
            if provider_credential is None:
                print("giclab-lambda-inventory: LAMBDA_API_KEY is unavailable", file=sys.stderr)
                return 2
            binding = InventoryRunBinding(
                run_id="RUN-T07-L1-LAMBDA-INVENTORY-0001",
                repository_commit=args.expected_commit,
                authorization_reference=args.authorization_reference,
                authorization_sha256=args.authorization_sha256,
            )
            result = _execute_inventory_within_total_deadline(
                repository_root=args.repository_root,
                plan_path=args.plan,
                plan_sha256=args.plan_sha256,
                run_binding=binding,
                credential=provider_credential,
                transport=LambdaHttpsInventoryTransport(),
                archiver=DurableInventoryArchiver(),
                watchdog_factory=SubprocessDeadlineWatchdog.arm,
                clock=time.monotonic,
                sleeper=time.sleep,
                utc_now=lambda: datetime.now(UTC),
            )
    except (LambdaCloudContractError, OSError, ValueError):
        print(
            "giclab-lambda-inventory: operation stopped; inspect secret-free local controls",
            file=sys.stderr,
        )
        return 1
    output: dict[str, object] = {
        "run_id": result.run_id,
        "authorization_reference": result.authorization_reference,
        "artifact_path": str(result.artifact.path),
        "artifact_sha256": result.artifact.sha256,
        "artifact_bytes": result.artifact.bytes,
        "archive_path": str(result.archive.destination),
        "archive_seal_sha256": result.archive.seal_sha256,
        "archive_copy_record_sha256": result.archive.external_copy_record_sha256,
        "local_copy_record_path": str(result.copy_record.path),
        "local_copy_record_sha256": result.copy_record.sha256,
        "provider_calls": result.provider_calls,
        "selection_state": result.selection_state,
        "blocked_reason": result.blocked_reason,
    }
    if result.candidate is not None:
        output["selected_tuple"] = {
            "instance_type_name": result.candidate.instance_type_name,
            "region_name": result.candidate.region_name,
            "image_id": result.candidate.image_id,
            "price_cents_per_hour": result.candidate.price_cents_per_hour,
            "gpus": result.candidate.gpus,
        }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
