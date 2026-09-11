"""Explicit offline image inputs; no daemon, loader command, or live selector.

Hash order: tracked generator/config template -> archive members -> archive ->
environment binding. The candidate digest is an input, never a self reference.
The archive is a parser fixture, not a claim of Docker importability or bootability.
"""

from __future__ import annotations

import io
import json
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from giclab.harness.t09_candidate_inputs import (
    EXECUTION_PATH,
    CandidateInputError,
    CandidateSourceSnapshot,
    canonical,
    decode,
    read_member,
    sha,
    validate_candidate_package,
)

FIXTURE_ID: Final = "T09-OFFLINE-IMAGE-ENVIRONMENT-FIXTURE-1"
GENERATOR: Final = "src/giclab/harness/t09_environment_fixture.py"
CHANNEL: Final = "tests/control/retained_candidate_effects.py"
TEMPLATE: Final = (
    "experiments/EXP-0001-sira-simulative-vs-reactive/contracts/"
    "T09_PILOT_HISTORICAL_RUNTIME_EVIDENCE.json"
)
ARCHIVE: Final = "offline-image.tar"
MAX_BYTES: Final = 1_048_576
_BINDING_SENTINEL = object()
COMMAND_PROBE_PATH: Final = "command-inputs/timeout-metadata-only"
COMMAND_PROBE_BYTES: Final = b"offline timeout file identity; execution is forbidden\n"

IMAGE_SOURCE_PATHS: Final = {
    "/opt/giclab/fixtures/static.html": "containers/sira-smoke/fixtures/static.html",
    "/opt/giclab/container_entrypoint.py": "containers/sira-smoke/container_entrypoint.py",
    "/opt/giclab/model_preflight.py": "containers/sira-smoke/bounded/model_preflight.py",
    "/opt/giclab/browser_preflight.py": "containers/sira-smoke/bounded/browser_preflight.py",
    "/opt/giclab/runtime_preflight.py": "containers/sira-smoke/pragmatic/runtime_preflight.py",
    "/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py": (
        "src/giclab/harness/sira_gate_a_runtime.py"
    ),
}


def image_file_inputs(source: CandidateSourceSnapshot) -> dict[str, bytes]:
    """Exact synthetic filesystem inputs, separate from historical image files.

    The import-only upstream stand-in cannot execute a condition. Runtime/model
    effects are supplied separately through the retained admission harness.
    """
    files = {
        "image-files/" + runtime.lstrip("/"): read_member(source.root, path)
        for runtime, path in IMAGE_SOURCE_PATHS.items()
    }
    files["image-files/opt/sira/scripts/run_web_agent.py"] = (
        b"from datetime import datetime\n"
        b"from pathlib import Path\n"
        b"directory = Path('logs')\n"
        b"directory.mkdir(mode=0o700)\n"
        b"log = directory / ('sira_' + datetime.now().strftime('%Y-%m-%d') + '.log')\n"
        b"with log.open('xb'):\n    pass\n"
        b"log.chmod(0o600)\n"
        b"def unavailable(*args, **kwargs):\n"
        b"    raise RuntimeError('offline import fixture cannot execute a condition')\n"
        b"main = make_agent = make_llm = run_episode = unavailable\n"
    )
    files["image-files/opt/giclab/installed-packages.txt"] = (
        b"# synthetic metadata inputs; no image dependencies installed\n"
        + b"".join(value for _, value in sorted(overlay_inputs(source).items()))
    )
    # This is a typed simulated file observation, never an executable launcher.
    # The retained Python probes execute the real pinned local interpreter and
    # report that interpreter independently.
    files["image-files/opt/sira/.venv/bin/python"] = (
        b"offline simulated image interpreter identity; not executable\n"
    )
    files["image-files/opt/ms-playwright/chromium-1084/chrome-linux/chrome"] = (
        b"offline simulated chromium identity; not executable\n"
    )
    return files


def overlay_inputs(source: CandidateSourceSnapshot) -> dict[str, bytes]:
    """Serialized package metadata observations, never installed dependencies."""
    execution = json.loads(read_member(source.root, EXECUTION_PATH))
    evaluator_path = execution["contract_bindings"]["evaluator"]["path"]
    evaluator = json.loads(read_member(source.root, evaluator_path))
    inventory = evaluator["materialization"]["dependency_license_inventory"]
    result = {}
    for item in inventory:
        package, _license = item.split("|")
        name, version = package.split("==")
        if any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.+"
            for c in name + version
        ):
            raise CandidateInputError("fixture dependency metadata path is unsafe")
        path = f"overlay-inputs/{name.replace('-', '_')}-{version}.dist-info/METADATA"
        if path in result:
            raise CandidateInputError("fixture dependency metadata is duplicated")
        result[path] = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
    if not result or sum(map(len, result.values())) > MAX_BYTES:
        raise CandidateInputError("fixture dependency metadata cap exceeded")
    return result


def _inputs(source: CandidateSourceSnapshot) -> tuple[bytes, dict[str, object]]:
    template = read_member(source.root, TEMPLATE)
    config = json.loads(template)["image_inspect_projection"]["Config"]
    encoded_config = canonical(
        {
            "architecture": "amd64",
            "os": "linux",
            "config": config,
            "rootfs": {"type": "layers", "diff_ids": []},
            "history": [],
        }
    )
    config_name = sha(encoded_config) + ".json"
    members = {
        config_name: encoded_config,
        "manifest.json": canonical([{"Config": config_name, "RepoTags": [], "Layers": []}]),
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, value in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size = len(value)
            info.mode = 0o400
            info.mtime = info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(value))
    data = stream.getvalue()
    if len(data) > MAX_BYTES:
        raise CandidateInputError("offline environment archive exceeds its input cap")
    document: dict[str, object] = {
        "schema_version": "1.0.0",
        "fixture_id": FIXTURE_ID,
        "revision": 5,
        "classification": "synthetic-environment-orchestration-only",
        "audience": "explicit-offline-candidate-harness",
        "candidate_binding_sha256": source.digest,
        "qualification_fixture": source.document()["qualification_fixture"],
        "generator_sha256": source.source_sha256(source.root, GENERATOR),
        "environment_implementation_sha256": source.source_sha256(source.root, CHANNEL),
        "template_config_source_sha256": sha(template),
        "selected_branch": "retained-archive-load",
        "staged_archive_relative_path": "environment-staging/offline-image.tar",
        "command_model": {
            "image_shapes": [
                ["docker", "info"],
                ["docker", "image", "inspect", "--format", "{{.Id}}", "<bound-id-or-tag>"],
                ["docker", "load", "--input", "<held-descriptor>"],
                ["docker", "tag", "<bound-image-id>", "<bound-transaction-tag>"],
                ["docker", "image", "inspect", "<bound-image-id>"],
                ["docker", "image", "rm", "--force", "<bound-image-id>"],
            ],
            "required_order": "both-absent-before-single-load-inspect-retag-inspect",
            "failure_cleanup": "remove-only-exact-loaded-image-then-observe-absence",
            "unknown_command": "reject-before-execution",
            "shell": False,
            "container_roles": {
                "core-suppression-preflight": (
                    "retained-core-suite-simulated-resource-and-signal-channel"
                ),
                "browser-lifecycle-preflight": (
                    "retained-browser-probe-stateful-page-process-channel"
                ),
                "utility-secret-channel-probe": "retained-canary-script-local-file-observations",
                "utility-evaluator-overlay-sync": "copy-bound-metadata-no-package-manager",
                "utility-evaluator-package-freeze": "read-copied-metadata",
                "utility-evaluator-package-revalidation": "read-copied-metadata",
                "utility-sha256sum": "hash-bound-image-file-bytes",
                "utility-final-image-runtime-preflight": "execute-retained-local-runtime-probe",
                "utility-provider-accounting-preflight": "execute-retained-accounting-regressions",
                "utility-offline-preflight": "execute-retained-preflight-on-bound-fixture-inputs",
                "utility-qualified-real-regression": (
                    "execute-retained-regression-on-staged-fixture"
                ),
            },
            "container_shapes": "exact-argv-in-hash-bound-environment-implementation",
            "container_ownership": "exact-plan-host-role-name-cidfile-and-transaction-mounts",
            "model_browser_condition_execution": "not-implemented-by-image-channel",
        },
        "archive": {"path": ARCHIVE, "format": "ustar", "bytes": len(data), "sha256": sha(data)},
        "members": [
            {"path": name, "bytes": len(value), "sha256": sha(value)}
            for name, value in sorted(members.items())
        ],
        "overlay_input_members": [
            {"path": path, "bytes": len(value), "sha256": sha(value)}
            for path, value in sorted(overlay_inputs(source).items())
        ],
        "overlay_classification": "serialized-test-package-metadata-no-installation",
        "image_file_members": [
            {
                "path": path,
                "runtime_path": "/" + path.removeprefix("image-files/"),
                "source_path": IMAGE_SOURCE_PATHS.get("/" + path.removeprefix("image-files/")),
                "bytes": len(value),
                "sha256": sha(value),
            }
            for path, value in sorted(image_file_inputs(source).items())
        ],
        "image_file_classification": "candidate-sources-and-synthetic-environment-files",
        "command_probe_input": {
            "runtime_path": "/usr/bin/timeout",
            "path": COMMAND_PROBE_PATH,
            "bytes": len(COMMAND_PROBE_BYTES),
            "sha256": sha(COMMAND_PROBE_BYTES),
            "mode": "0500",
            "executed": False,
            "classification": "command-rendering-filesystem-observation-only",
        },
        "process_observations": {
            "core_limits": [0, 0],
            "abort_signal": "SIGABRT",
            "playwright_version": "1.39.0",
            "chromium_revision": "1084",
            "browser_version": "offline-simulated-browser",
            "browser_title": "GIC Lab offline fixture",
            "real_core_kernel_qualification": False,
            "real_browser_qualification": False,
        },
        "simulated_daemon_identity": {
            "image_id": "sha256:" + sha(encoded_config),
            "config_sha256": sha(encoded_config),
            "derivation": "sha256-of-fixture-config-bytes",
            "observed_real_docker_image": False,
        },
        "limits": {
            "input_bytes": MAX_BYTES,
            "command_output_bytes": MAX_BYTES,
            "command_seconds": 300,
        },
        "real_image_actions": 0,
        "real_provider_model_browser_actions": 0,
        "live_qualification": False,
        "scientific_authority": False,
        "download_or_build_fallback": "forbidden",
    }
    return data, document


@dataclass(frozen=True)
class OfflineEnvironmentBinding:
    """Input capability issued only by the explicit builder/validated loader."""

    root: Path
    binding_bytes: bytes
    _token: object

    @property
    def digest(self) -> str:
        return sha(self.binding_bytes)

    @property
    def archive_path(self) -> Path:
        return self.root / ARCHIVE

    def staged_archive_path(self, artifact_root: Path) -> Path:
        return artifact_root / "environment-staging/offline-image.tar"

    @property
    def image_id(self) -> str:
        return str(self.document()["simulated_daemon_identity"]["image_id"])

    def document(self) -> dict[str, Any]:
        return decode(self.binding_bytes)

    def evidence_schema(
        self, source: CandidateSourceSnapshot, package: Path, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Select only the three image-file identities in the bound full schema.

        This returns a derived in-memory test schema. The tracked historical
        schema and all scientific constraints remain byte-identical.
        """
        self.validate(source, package)
        selected = json.loads(
            read_member(source.root, "schemas/t09-sira-pilot-evidence.schema.json")
        )
        if not isinstance(selected, dict):
            raise CandidateInputError("candidate evidence schema is not an object")
        if schema != selected:
            raise CandidateInputError("candidate evidence schema source differs")
        properties = selected["properties"]["runtime"]["properties"]
        members = {m["runtime_path"]: m["sha256"] for m in self.document()["image_file_members"]}
        for field, runtime_path in {
            "installed_package_manifest_sha256": "/opt/giclab/installed-packages.txt",
            "chromium_executable_sha256": "/opt/ms-playwright/chromium-1084/chrome-linux/chrome",
            "patched_upstream_runner_sha256": "/opt/sira/scripts/run_web_agent.py",
        }.items():
            if set(properties[field]) != {"const"}:
                raise CandidateInputError("candidate image schema role differs")
            properties[field] = {"const": members[runtime_path]}
        return selected

    def validate(self, source: CandidateSourceSnapshot, package: Path) -> None:
        if self._token is not _BINDING_SENTINEL:
            raise CandidateInputError("offline environment lacks its explicit loader binding")
        validate_candidate_package(source, package)
        expected_archive, expected = _inputs(source)
        if self.binding_bytes != canonical(expected):
            raise CandidateInputError("offline environment candidate/source identity drifted")
        archive = read_member(self.root, ARCHIVE)
        if archive != expected_archive:
            raise CandidateInputError("offline environment archive bytes drifted")
        for path, value in overlay_inputs(source).items():
            if read_member(self.root, path) != value:
                raise CandidateInputError("offline environment dependency input drifted")
        for path, value in image_file_inputs(source).items():
            if read_member(self.root, path) != value:
                raise CandidateInputError("offline environment image-file input drifted")
        if (
            read_member(self.root, COMMAND_PROBE_PATH) != COMMAND_PROBE_BYTES
            or self.root.joinpath(COMMAND_PROBE_PATH).stat().st_mode & 0o777 != 0o500
        ):
            raise CandidateInputError("offline command filesystem input drifted")
        expected_names = {
            ARCHIVE,
            "environment.json",
            COMMAND_PROBE_PATH,
            *overlay_inputs(source),
            *image_file_inputs(source),
        }
        observed_names = set()
        for entry in self.root.rglob("*"):
            if entry.is_symlink():
                raise CandidateInputError("offline environment contains a symlink")
            if entry.is_dir():
                continue
            name = entry.relative_to(self.root).as_posix()
            if entry.stat().st_mode & 0o777 != (0o500 if name == COMMAND_PROBE_PATH else 0o400):
                raise CandidateInputError("offline environment input is not sealed read-only")
            observed_names.add(name)
            if len(observed_names) > len(expected_names):
                raise CandidateInputError("offline environment has unexpected members")
        if observed_names != expected_names:
            raise CandidateInputError("offline environment member set drifted")
        # Real archive parsing; no permissive extraction or daemon observation.
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
            members = stream.getmembers()
            if len(members) != 2 or any(not item.isfile() for item in members):
                raise CandidateInputError("offline environment archive members drifted")
            observed = []
            for member in members:
                content = stream.extractfile(member)
                assert content is not None
                value = content.read(MAX_BYTES + 1)
                observed.append({"path": member.name, "bytes": len(value), "sha256": sha(value)})
            if observed != expected["members"]:
                raise CandidateInputError("offline environment member identity drifted")


def build_environment_fixture(
    source: CandidateSourceSnapshot, package: Path, root: Path
) -> OfflineEnvironmentBinding:
    validate_candidate_package(source, package)
    data, document = _inputs(source)
    root.mkdir(mode=0o700, exist_ok=False)
    files = {
        ARCHIVE: data,
        "environment.json": canonical(document),
        **overlay_inputs(source),
        **image_file_inputs(source),
        COMMAND_PROBE_PATH: COMMAND_PROBE_BYTES,
    }
    if sum(map(len, files.values())) > MAX_BYTES:
        raise CandidateInputError("offline environment total input cap exceeded")
    for name, value in files.items():
        (root / name).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(root / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if name == COMMAND_PROBE_PATH:
            (root / name).chmod(0o500)
        else:
            (root / name).chmod(0o400)
    result = OfflineEnvironmentBinding(root, canonical(document), _BINDING_SENTINEL)
    result.validate(source, package)
    return result


def load_environment_fixture(
    root: Path, *, expected_sha256: str, source: CandidateSourceSnapshot, package: Path
) -> OfflineEnvironmentBinding:
    data = read_member(root, "environment.json")
    if sha(data) != expected_sha256:
        raise CandidateInputError("offline environment binding digest drifted")
    result = OfflineEnvironmentBinding(root, data, _BINDING_SENTINEL)
    result.validate(source, package)
    return result
