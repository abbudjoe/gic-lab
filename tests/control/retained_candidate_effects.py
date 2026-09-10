"""Offline transaction adapter; host phases execute in sealed-source subprocesses.

Only environmental provider responses, local carrier copies and Docker observations
are substituted. Unimplemented environmental cases fail before an external call.
This development harness does not yet establish a successful joined transaction.
"""

from __future__ import annotations

import builtins
import contextlib
import importlib.util
import io
import json
import os
import select
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

from giclab.control.effects import (
    CleanupExecutionReceipt,
    ConditionProcessOutcome,
    EvaluatorExecutionOutcome,
    FinalizerExecutionOutcome,
    HostPackageTransferReceipt,
    HostPreflightReceipt,
    HostQualificationReceipt,
    RetainedConditionSource,
    ScientificFreezeReceipt,
    repository_effect_identity,
)
from giclab.control.production import ProductionCategory3World
from giclab.control.remote_bridge import RetainedProcessOwner
from giclab.control.shadow_effects import DeterministicLowLevelEffects
from giclab.harness import t09_pragmatic_provider as provider
from giclab.harness.campaign_output import (
    CampaignWriterRole,
    CleanupOutputBinding,
    CleanupOutputChannel,
    admit_campaign_write,
    campaign_output_scope,
    cleanup_output_inventory,
    observe_campaign_write,
    prepare_campaign_temporary,
    reconcile_cleanup_output,
    replace_campaign_write,
    verify_campaign_write,
)
from giclab.harness.t09_candidate_inputs import (
    canonical,
    load_candidate_source_snapshot,
    sha,
    validate_candidate_package,
)
from giclab.harness.t09_cleanup_state import (
    CleanupTargetKind,
    CleanupTargetState,
    EarlyCleanupJournal,
    TerminalCleanupDisposition,
    cleanup_locator_identity,
)

# A bounded suballocation for this explicit offline fixture transaction, not a
# replacement for the retained 128-MiB derived-output or 64-MiB envelope caps.
# Both real writers consume this grant before growth; exhaustion fails closed.
_FINALIZER_OUTPUT_ALLOCATION_BYTES = 4 * 1024 * 1024
_EXPORT_OUTPUT_ALLOCATION_BYTES = 16 * 1024 * 1024
_EXPORT_CARRIER_RECORD_BYTES = 1024 * 1024

RELATIVE = "tests/control/retained_candidate_effects.py"


class ImageCommandChannel:
    """Small stateful image daemon model; construction performs no operations."""

    def __init__(
        self,
        binding,
        *,
        tag,
        transaction_root,
        fault=None,
        package=None,
        source_inputs=None,
        contract=None,
    ):
        if fault not in {
            None,
            "load-error",
            "timeout",
            "partial",
            "missing",
            "wrong-image",
            "canary-uid",
            "core-limit",
            "browser-version",
            "browser-residue",
        }:
            raise ValueError("unknown image fault")
        self.binding = binding
        self.tag = tag
        self.transaction_root = transaction_root
        self.fault = fault
        self.loaded = False
        self.tagged = False
        self.load_count = 0
        self.removal_count = 0
        self.before_load = set()
        self.events = []
        self.package = package
        self.source_inputs = source_inputs
        self.contract = contract
        self.containers = {}
        self.qualification_binding = None
        self.condition_launch = None
        self.condition_context = None
        self.condition_processes = {}

    def popen(self, argv, **kwargs):
        """Model only an allowlisted container command; execute retained leaf code."""
        if self.contract is None or self.package is None or self.source_inputs is None:
            raise RuntimeError("container channel lacks explicit candidate context")
        if argv[:2] != ["docker", "run"] or not self.loaded:
            raise RuntimeError("container command precedes bound image load")
        if "/usr/local/bin/uv" in argv:
            return self._overlay_command(argv, **kwargs)
        if "/usr/bin/sha256sum" in argv:
            return self._file_hash_command(argv, **kwargs)
        if "/opt/giclab/runtime_preflight.py" in argv:
            return self._runtime_preflight_command(argv, **kwargs)
        if "/opt/giclab/t09_provider_accounting_preflight.py" in argv:
            return self._accounting_probe_command(argv, **kwargs)
        if "/opt/giclab/t09_preflight.py" in argv:
            return self._offline_probe_command(argv, **kwargs)
        if "/opt/giclab/t09_real_evidence_regression.py" in argv:
            return self._regression_command(argv, **kwargs)
        role = "utility-secret-channel-probe"
        name = self.contract.container_prefix + role
        source = self.package / "containers/sira-smoke/pragmatic/t09_secret_preflight.py"
        # Mount locations are independently selected transaction inputs. Parse
        # them, then compare the entire command against the approved shape.
        mounts = [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == "--mount"]
        if len(mounts) != 3:
            raise RuntimeError("unmodeled container command")
        mapped = {}
        for mount in mounts:
            parts = mount.split(",")
            if len(parts) not in {3, 4} or parts[0] != "type=bind":
                raise RuntimeError("container mount is malformed")
            if not parts[1].startswith("src=") or not parts[2].startswith("dst="):
                raise RuntimeError("container mount mapping is malformed")
            path = Path(parts[1][4:])
            if (
                not path.resolve(strict=True).is_relative_to(self.transaction_root)
                and path != source
            ):
                raise RuntimeError("container mount escaped bound inputs")
            mapped[parts[2][4:]] = path
        if set(mapped) != {
            "/opt/giclab/t09_secret_preflight.py",
            "/run/secrets/sira_api_key",
            "/opt/giclab-evidence",
        }:
            raise RuntimeError("container mount roles differ from canary contract")
        secret = mapped["/run/secrets/sira_api_key"]
        evidence = mapped["/opt/giclab-evidence"]
        cidfile = evidence / "secret-channel-probe.container-id"
        expected = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
            "--log-driver",
            "none",
            "--rm",
            "--ulimit",
            "core=0:0",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--user",
            "1000:1000",
            "--mount",
            f"type=bind,src={source},dst=/opt/giclab/t09_secret_preflight.py,readonly",
            "--mount",
            f"type=bind,src={secret},dst=/run/secrets/sira_api_key,readonly",
            "--mount",
            f"type=bind,src={evidence},dst=/opt/giclab-evidence",
            "--entrypoint",
            "/opt/sira/.venv/bin/python",
            self.binding.image_id,
            "/opt/giclab/t09_secret_preflight.py",
            "--secret",
            "/run/secrets/sira_api_key",
            "--output",
            "/opt/giclab-evidence/receipt.json",
        ]
        if argv != expected or name in self.containers or cidfile.exists():
            raise RuntimeError("container command/identity/order differs from canary contract")
        self.source_inputs.source_sha256(self.package, source.relative_to(self.package).as_posix())
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        self.containers[name] = {
            "id": identifier,
            "labels": {
                "giclab.t09.plan": self.contract.plan_id,
                "giclab.t09.host_run": self.contract.host_run_id,
                "giclab.t09.role": role,
            },
        }
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        specification = importlib.util.spec_from_file_location(
            "offline_retained_secret_probe", source
        )
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        original_argv = sys.argv
        original_os = module.os
        module.os = SimpleNamespace(**{key: getattr(os, key) for key in dir(os)})
        module.os.geteuid = lambda: 999 if self.fault == "canary-uid" else 1000
        module.os.getegid = lambda: 1000
        try:
            sys.argv = [
                str(source),
                "--secret",
                str(secret),
                "--output",
                str(evidence / "receipt.json"),
            ]
            code = module.main()
        finally:
            sys.argv = original_argv
            module.os = original_os
        # --rm is a modeled daemon side effect. Retained code must observe
        # absence and journal the exact cidfile identity itself.
        self.containers.pop(name)
        self.events.append(["retained-secret-probe", identifier, code])
        return SimpleNamespace(
            returncode=code,
            communicate=lambda timeout=None: (None, None),
            poll=lambda: code,
            kill=lambda: None,
        )

    def _regression_command(self, argv, **kwargs):
        from giclab.harness.t09_candidate_inputs import EXECUTION_PATH
        from giclab.harness.t09_qualification_fixture import DATASET_PATH, EVALUATOR_ROOT

        if self.qualification_binding is None or argv.count("--cidfile") != 1:
            raise RuntimeError("qualified regression lacks exact fixture/ownership binding")
        role = "utility-qualified-real-regression"
        name = self.contract.container_prefix + role
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        attempt = cidfile.parent
        root = attempt.parent.parent
        if (
            cidfile.name != "qualified-real-regression.container-id"
            or attempt
            != root / self.contract.control_root_name / "qualified-real-evidence-regression"
            or not root.resolve(strict=True).is_relative_to(self.transaction_root)
            or cidfile.exists()
            or name in self.containers
        ):
            raise RuntimeError("qualified regression ownership/mapping drifted")
        source = self.package / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
        finalizer = self.package / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
        archive = (
            self.qualification_binding.archive_path.parent
            / "staged-offline-qualification-fixture.tar.gz"
        )
        disposition = (
            self.package
            / "experiments/EXP-0001-sira-simulative-vs-reactive"
            / "T09_PRAGMATIC_RETRY2_DISPOSITION.json"
        )
        execution = json.loads((self.package / EXECUTION_PATH).read_bytes())
        evaluator = self.package / execution["contract_bindings"]["evaluator"]["path"]
        overlay = root / "qualification-inputs/evaluator-overlay"
        logical_args = [
            "--archive",
            "/opt/giclab-private/v4-attempt.tar.gz",
            "--public-disposition",
            "/opt/giclab-contracts/v4-disposition.json",
            "--finalizer-source",
            "/opt/giclab/t09_evaluate_attempt.py",
            "--finalizer-source-sha256",
            sha(finalizer.read_bytes()),
            "--evaluator-root",
            "/opt/sira/evaluation/fanout",
            "--evaluator-contract",
            "/opt/giclab-contracts/evaluator.json",
            "--dependency-site-packages",
            "/opt/evaluator/.venv/lib/python3.11/site-packages",
            "--dataset",
            "/opt/sira/data/fanout-final-dev.json",
            "--receipt-id",
            "T09-PRAGMATIC-RETRY5-QUALIFIED-IMAGE-REGRESSION-0001",
            "--output",
            "/opt/giclab-output/receipt.json",
        ]
        expected = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
            "--log-driver",
            "none",
            "--rm",
            "--ulimit",
            "core=0:0",
            "--network",
            "none",
            "--read-only",
            "--user",
            "1000:1000",
            "--env",
            "PYTHONPATH=/opt/evaluator/.venv/lib/python3.11/site-packages:/opt/giclab-src",
            "--env",
            "CUDA_VISIBLE_DEVICES=",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--mount",
            f"type=bind,src={self.package / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
            "--mount",
            f"type=bind,src={source},dst=/opt/giclab/t09_real_evidence_regression.py,readonly",
            "--mount",
            f"type=bind,src={finalizer},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
            "--mount",
            f"type=bind,src={archive},dst=/opt/giclab-private/v4-attempt.tar.gz,readonly",
            "--mount",
            f"type=bind,src={disposition},dst=/opt/giclab-contracts/v4-disposition.json,readonly",
            "--mount",
            f"type=bind,src={evaluator},dst=/opt/giclab-contracts/evaluator.json,readonly",
            "--mount",
            f"type=bind,src={overlay},dst=/opt/evaluator,readonly",
            "--mount",
            f"type=bind,src={attempt},dst=/opt/giclab-output",
            "--entrypoint",
            "/opt/sira/.venv/bin/python",
            self.binding.image_id,
            "/opt/giclab/t09_real_evidence_regression.py",
            *logical_args,
        ]
        if argv != expected:
            raise RuntimeError("qualified regression command differs from bound shape")
        self.binding.validate(self.source_inputs, self.package)
        self.qualification_binding.validate(self.package, archive_path=archive)
        self.source_inputs.source_sha256(self.package, source.relative_to(self.package).as_posix())
        spec = importlib.util.spec_from_file_location(
            "offline_retained_qualified_regression", source
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = module._parser().parse_args(logical_args)
        args.archive, args.public_disposition = archive, disposition
        args.finalizer_source, args.evaluator_contract = finalizer, evaluator
        args.evaluator_root, args.dataset = (
            self.package / EVALUATOR_ROOT,
            self.package / DATASET_PATH,
        )
        args.dependency_site_packages = overlay / ".venv/lib/python3.11/site-packages"
        args.output = attempt / "receipt.json"
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        scratch = attempt / "private-scratch"
        scratch.mkdir(mode=0o700)
        module.tempfile = SimpleNamespace(
            TemporaryDirectory=lambda **options: tempfile.TemporaryDirectory(dir=scratch, **options)
        )
        document = module.run(
            args, fixture_binding=self.qualification_binding, fixture_repository=self.package
        )
        self.events.append(["retained-qualified-regression", identifier, sha(canonical(document))])
        result = self._result(argv, kwargs, stdout=canonical(document))
        return SimpleNamespace(
            returncode=0,
            communicate=lambda timeout=None: (result.stdout, result.stderr),
            poll=lambda: 0,
            kill=lambda: None,
        )

    def _offline_probe_command(self, argv, **kwargs):
        from giclab.harness.t09_candidate_inputs import COMMAND_PATH, EXECUTION_PATH
        from giclab.harness.t09_qualification_fixture import DATASET_PATH, EVALUATOR_ROOT

        if self.qualification_binding is None:
            raise RuntimeError("offline probe lacks its explicit qualification archive binding")
        role = "utility-offline-preflight"
        name = self.contract.container_prefix + role
        if argv.count("--cidfile") != 1:
            raise RuntimeError("offline probe lacks exact ownership")
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        attempt = cidfile.parent
        root = attempt.parent.parent
        control = self.contract.control_root_name
        overlay = root / "qualification-inputs/evaluator-overlay"
        if (
            cidfile.name != "offline-preflight.container-id"
            or attempt != root / control / "offline-runtime-preflight"
            or not root.resolve(strict=True).is_relative_to(self.transaction_root)
            or cidfile.exists()
            or name in self.containers
        ):
            raise RuntimeError("offline probe ownership/mapping drifted")
        source = self.package / "containers/sira-smoke/pragmatic/t09_preflight.py"
        finalizer = self.package / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
        raw_fixture = self.package / "tests/fixtures/t09/finalizer-raw-shape"
        execution, commands = self.package / EXECUTION_PATH, self.package / COMMAND_PATH
        runtime_sha = self.source_inputs.source_sha256(
            self.package, "src/giclab/harness/sira_gate_a_runtime.py"
        )
        library_sha = self.source_inputs.source_sha256(
            self.package, "src/giclab/harness/t09_sira_pilot.py"
        )
        logical_args = [
            "--execution-contract",
            "/opt/giclab-contracts/execution.json",
            "--execution-contract-sha256",
            sha(execution.read_bytes()),
            "--command-manifests",
            "/opt/giclab-contracts/commands.json",
            "--command-manifests-sha256",
            sha(commands.read_bytes()),
            "--runtime-adaptation-sha256",
            runtime_sha,
            "--pilot-library-sha256",
            library_sha,
            "--attempt-root",
            f"/opt/giclab-artifacts/{control}/offline-runtime-preflight",
            "--aggregate-ledger",
            f"/opt/giclab-artifacts/{control}/runtime-budget/aggregate-budget.json",
            "--pilot-state",
            f"/opt/giclab-artifacts/{control}/pilot-state.json",
            "--evaluator-root",
            "/opt/sira/evaluation/fanout",
            "--dataset",
            "/opt/sira/data/fanout-final-dev.json",
            "--finalizer-source",
            "/opt/giclab/t09_evaluate_attempt.py",
            "--finalizer-source-sha256",
            sha(finalizer.read_bytes()),
            "--finalizer-raw-fixture",
            "/opt/giclab-finalizer-fixture",
        ]
        expected = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
            "--log-driver",
            "none",
            "--rm",
            "--ulimit",
            "core=0:0",
            "--network",
            "none",
            "--read-only",
            "--user",
            "1000:1000",
            "--env",
            "PYTHONPATH=/opt/evaluator/.venv/lib/python3.11/site-packages:/opt/giclab-src",
            "--env",
            "CUDA_VISIBLE_DEVICES=",
            "--mount",
            f"type=bind,src={root},dst=/opt/giclab-artifacts",
            "--mount",
            f"type=bind,src={self.package / 'src/giclab'},dst=/opt/giclab-src/giclab,readonly",
            "--mount",
            f"type=bind,src={source},dst=/opt/giclab/t09_preflight.py,readonly",
            "--mount",
            f"type=bind,src={finalizer},dst=/opt/giclab/t09_evaluate_attempt.py,readonly",
            "--mount",
            f"type=bind,src={raw_fixture},dst=/opt/giclab-finalizer-fixture,readonly",
            "--mount",
            f"type=bind,src={overlay},dst=/opt/evaluator,readonly",
            "--mount",
            f"type=bind,src={execution},dst=/opt/giclab-contracts/execution.json,readonly",
            "--mount",
            f"type=bind,src={commands},dst=/opt/giclab-contracts/commands.json,readonly",
            "--entrypoint",
            "/opt/sira/.venv/bin/python",
            self.binding.image_id,
            "/opt/giclab/t09_preflight.py",
            *logical_args,
        ]
        if argv != expected:
            raise RuntimeError("offline probe command differs from exact bound shape")
        self.binding.validate(self.source_inputs, self.package)
        self.source_inputs.source_sha256(self.package, source.relative_to(self.package).as_posix())
        spec = importlib.util.spec_from_file_location("offline_retained_fixture_preflight", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = module._parser().parse_args(logical_args)
        args.execution_contract, args.command_manifests = execution, commands
        args.attempt_root = attempt
        args.aggregate_ledger = root / control / "runtime-budget/aggregate-budget.json"
        args.pilot_state = root / control / "pilot-state.json"
        args.evaluator_root, args.dataset = (
            self.package / EVALUATOR_ROOT,
            self.package / DATASET_PATH,
        )
        args.finalizer_source, args.finalizer_raw_fixture = finalizer, raw_fixture
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        document = module.run(
            args,
            source_inputs=self.source_inputs,
            environment_binding=self.binding,
            fixture_binding=self.qualification_binding,
            package=self.package,
        )
        self.events.append(
            ["retained-offline-fixture-preflight", identifier, sha(canonical(document))]
        )
        result = self._result(argv, kwargs, stdout=canonical(document))
        return SimpleNamespace(
            returncode=0,
            communicate=lambda timeout=None: (result.stdout, result.stderr),
            poll=lambda: 0,
            kill=lambda: None,
        )

    def _accounting_probe_command(self, argv, **kwargs):
        role = "utility-provider-accounting-preflight"
        name = self.contract.container_prefix + role
        if argv.count("--cidfile") != 1:
            raise RuntimeError("accounting probe lacks exact ownership")
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        attempt = cidfile.parent
        if (
            cidfile.name != "provider-accounting-preflight.container-id"
            or not attempt.resolve(strict=True).is_relative_to(self.transaction_root)
            or cidfile.exists()
            or name in self.containers
        ):
            raise RuntimeError("accounting probe ownership drifted")
        relative = "containers/sira-smoke/pragmatic/t09_provider_accounting_preflight.py"
        source = self.package / relative
        expected = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
            "--log-driver",
            "none",
            "--rm",
            "--ulimit",
            "core=0:0",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--init",
            "--restart",
            "no",
            "--cpus",
            "2.0",
            "--memory",
            "4g",
            "--memory-swap",
            "4g",
            "--pids-limit",
            "512",
            "--shm-size",
            "1g",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
            "--user",
            "1000:1000",
            "--env",
            "CUDA_VISIBLE_DEVICES=",
            "--env",
            "PYTHONPATH=/opt/giclab-accounting-src",
            "--mount",
            f"type=bind,src={attempt},dst=/giclab/attempt",
            "--mount",
            f"type=bind,src={self.package / 'src'},dst=/opt/giclab-accounting-src,readonly",
            "--mount",
            f"type=bind,src={source},dst=/opt/giclab/t09_provider_accounting_preflight.py,readonly",
            "--entrypoint",
            "/opt/sira/.venv/bin/python",
            self.binding.image_id,
            "/opt/giclab/t09_provider_accounting_preflight.py",
            "--output",
            "/giclab/attempt/receipt.json",
        ]
        if argv != expected:
            raise RuntimeError("accounting probe command differs from bound shape")
        self.binding.validate(self.source_inputs, self.package)
        self.source_inputs.source_sha256(self.package, relative)
        spec = importlib.util.spec_from_file_location("offline_retained_accounting_probe", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        module.run(attempt / "receipt.json")
        self.events.append(
            [
                "retained-accounting-preflight",
                identifier,
                sha((attempt / "receipt.json").read_bytes()),
            ]
        )
        result = self._result(argv, kwargs)
        return SimpleNamespace(
            returncode=0,
            communicate=lambda timeout=None: (result.stdout, result.stderr),
            poll=lambda: 0,
            kill=lambda: None,
        )

    def _runtime_preflight_command(self, argv, **kwargs):
        role = "utility-final-image-runtime-preflight"
        name = self.contract.container_prefix + role
        if argv.count("--cidfile") != 1 or argv.count("--mount") != 1:
            raise RuntimeError("runtime probe command ownership/mount differs")
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        attempt = cidfile.parent
        if (
            cidfile.name != "final-image-runtime-preflight.container-id"
            or not attempt.resolve(strict=True).is_relative_to(self.transaction_root)
            or cidfile.exists()
            or name in self.containers
        ):
            raise RuntimeError("runtime probe ownership escaped its transaction")
        expected = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
            "--log-driver",
            "none",
            "--rm",
            "--ulimit",
            "core=0:0",
            "--network",
            "none",
            "--read-only",
            "--user",
            "1000:1000",
            "--env",
            "CUDA_VISIBLE_DEVICES=",
            "--mount",
            f"type=bind,src={attempt},dst=/giclab/attempt",
            "--entrypoint",
            "/opt/sira/.venv/bin/python",
            self.binding.image_id,
            "/opt/giclab/runtime_preflight.py",
            "--attempt-root",
            "/giclab/attempt",
        ]
        if argv != expected:
            raise RuntimeError("runtime probe command differs from exact contract")
        self.binding.validate(self.source_inputs, self.package)
        relative = "containers/sira-smoke/pragmatic/runtime_preflight.py"
        self.source_inputs.source_sha256(self.package, relative)
        spec = importlib.util.spec_from_file_location(
            "offline_retained_runtime_probe", self.package / relative
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        document = module.run(
            attempt,
            source_inputs=self.source_inputs,
            environment_binding=self.binding,
            package=self.package,
        )
        self.events.append(["retained-runtime-preflight", identifier, sha(canonical(document))])
        result = self._result(argv, kwargs, stdout=canonical(document))
        return SimpleNamespace(
            returncode=0,
            communicate=lambda timeout=None: (result.stdout, result.stderr),
            poll=lambda: 0,
            kill=lambda: None,
        )

    def _file_hash_command(self, argv, **kwargs):
        from giclab.harness.t09_candidate_inputs import read_member

        role = "utility-sha256sum"
        name = self.contract.container_prefix + role
        if argv.count("--cidfile") != 1:
            raise RuntimeError("image file command lacks exact ownership")
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        if (
            cidfile.name != "sha256sum.container-id"
            or not cidfile.parent.resolve(strict=True).is_relative_to(self.transaction_root)
            or cidfile.exists()
            or name in self.containers
        ):
            raise RuntimeError("image file command ownership drifted")
        members = self.binding.document()["image_file_members"]
        interpreter = "/opt/sira/.venv/bin/python"
        paths = [item["runtime_path"] for item in members if item["runtime_path"] != interpreter]
        paths.append(interpreter)
        expected = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
            "--log-driver",
            "none",
            "--rm",
            "--ulimit",
            "core=0:0",
            "--network",
            "none",
            "--read-only",
            "--entrypoint",
            "/usr/bin/sha256sum",
            self.binding.image_id,
            *paths,
        ]
        if argv != expected:
            raise RuntimeError("image file command differs from its bound shape")
        by_path = {item["runtime_path"]: item for item in members}
        output = b""
        for path in paths:
            item = by_path[path]
            value = read_member(self.binding.root, item["path"])
            if len(value) != item["bytes"] or sha(value) != item["sha256"]:
                raise RuntimeError("image file bytes changed before observation")
            output += (sha(value) + "  " + path + "\n").encode()
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        self.events.append(["image-file-hashes", identifier, sha(output)])
        result = self._result(argv, kwargs, stdout=output)
        return SimpleNamespace(
            returncode=0,
            communicate=lambda timeout=None: (result.stdout, result.stderr),
            poll=lambda: 0,
            kill=lambda: None,
        )

    def _overlay_command(self, argv, **kwargs):
        """Model installation as exact metadata files; freeze reads those files."""
        from importlib.metadata import distributions

        from giclab.harness.t09_candidate_inputs import read_member

        labels = [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == "--label"]
        roles = [
            value.removeprefix("giclab.t09.role=")
            for value in labels
            if value.startswith("giclab.t09.role=")
        ]
        allowed = {
            "utility-evaluator-overlay-sync",
            "utility-evaluator-package-freeze",
            "utility-evaluator-package-revalidation",
        }
        if len(roles) != 1 or roles[0] not in allowed or argv.count("--cidfile") != 1:
            raise RuntimeError("environment denied unbound dependency operation")
        role = roles[0]
        name = self.contract.container_prefix + role
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        if cidfile.name != role.removeprefix(
            "utility-"
        ) + ".container-id" or not cidfile.parent.resolve(strict=True).is_relative_to(
            self.transaction_root
        ):
            raise RuntimeError("dependency cidfile escaped its exact role")
        mounts = [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == "--mount"]
        overlay_mounts = [value for value in mounts if ",dst=/opt/evaluator" in value]
        if len(overlay_mounts) != 1:
            raise RuntimeError("dependency overlay mount is missing or duplicated")
        mount = overlay_mounts[0]
        parts = mount.split(",")
        if parts[0] != "type=bind" or not parts[1].startswith("src="):
            raise RuntimeError("dependency mount is malformed")
        overlay = Path(parts[1][4:])
        if not overlay.resolve(strict=True).is_relative_to(self.transaction_root):
            raise RuntimeError("dependency overlay escaped its transaction")
        head = [
            "docker",
            "run",
            "--cidfile",
            str(cidfile),
            "--name",
            name,
            "--label",
            f"giclab.t09.plan={self.contract.plan_id}",
            "--label",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "--label",
            f"giclab.t09.role={role}",
        ]
        if role == "utility-evaluator-overlay-sync":
            suffix = [
                "--rm",
                "--ulimit",
                "core=0:0",
                "--network",
                "bridge",
                "--log-driver",
                "none",
                "--user",
                "1000:1000",
                "--env",
                "UV_PROJECT_ENVIRONMENT=/opt/evaluator/.venv",
                "--env",
                "UV_CACHE_DIR=/opt/evaluator/cache",
                "--env",
                "CUDA_VISIBLE_DEVICES=",
                "--mount",
                f"type=bind,src={self.package},dst=/opt/giclab-project,readonly",
                "--mount",
                f"type=bind,src={overlay},dst=/opt/evaluator",
                "--entrypoint",
                "/usr/local/bin/uv",
                self.binding.image_id,
                "sync",
                "--frozen",
                "--only-group",
                "evaluator",
                "--no-install-project",
                "--project",
                "/opt/giclab-project",
                "--python",
                "/opt/sira/.venv/bin/python",
            ]
        else:
            suffix = [
                "--rm",
                "--ulimit",
                "core=0:0",
                "--network",
                "none",
                "--log-driver",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges=true",
                "--user",
                "1000:1000",
                "--env",
                "HOME=/tmp",
                "--env",
                "UV_CACHE_DIR=/tmp/uv-cache",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=67108864,uid=1000,gid=1000,mode=0700",
                "--mount",
                f"type=bind,src={overlay},dst=/opt/evaluator,readonly",
                "--entrypoint",
                "/usr/local/bin/uv",
                self.binding.image_id,
                "pip",
                "freeze",
                "--python",
                "/opt/evaluator/.venv/bin/python",
            ]
        if argv != head + suffix or name in self.containers or cidfile.exists():
            raise RuntimeError("dependency command differs from bound shell-free contract")
        identifier = sha(
            canonical(
                {"environment": self.binding.digest, "name": name, "ordinal": len(self.events)}
            )
        )
        self.containers[name] = {
            "id": identifier,
            "labels": dict(value.split("=", 1) for value in labels),
        }
        with cidfile.open("xb") as stream:
            stream.write((identifier + "\n").encode())
        cidfile.chmod(0o600)
        site = overlay / ".venv/lib/python3.11/site-packages"
        output = b""
        if role == "utility-evaluator-overlay-sync":
            site.mkdir(mode=0o700, parents=True, exist_ok=False)
            for member in self.binding.document()["overlay_input_members"]:
                data = read_member(self.binding.root, member["path"])
                if len(data) != member["bytes"] or sha(data) != member["sha256"]:
                    raise RuntimeError("dependency fixture input drifted before copy")
                target = site / Path(member["path"]).relative_to("overlay-inputs")
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
                target.chmod(0o600)
        else:
            packages = sorted(
                f"{item.metadata['Name']}=={item.version}"
                for item in distributions(path=[str(site)])
            )
            output = ("\n".join(packages) + "\n").encode()
        self.containers.pop(name)
        self.events.append(["simulated-package-metadata", role, identifier])
        return SimpleNamespace(
            returncode=0,
            communicate=lambda timeout=None: (output, None),
            poll=lambda: 0,
            kill=lambda: None,
        )

    def save_state(self, path):
        if not path.parent.resolve(strict=False).is_relative_to(self.transaction_root):
            raise RuntimeError("environment state escaped transaction")
        document = {
            "environment_sha256": self.binding.digest,
            "loaded": self.loaded,
            "tagged": self.tagged,
            "load_count": self.load_count,
            "removal_count": self.removal_count,
            "before_load": sorted(self.before_load),
            "containers": self.containers,
        }
        data = canonical(document)
        if len(data) > 65536:
            raise RuntimeError("environment state cap exceeded")
        allowance = admit_campaign_write(path, len(data), CampaignWriterRole.PHASE_CONTROL)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_suffix(".next")
        prepare_campaign_temporary(allowance, temporary)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            offset = 0
            while offset < len(data):
                count = os.write(descriptor, memoryview(data)[offset : offset + 65536])
                if count <= 0:
                    raise OSError("environment control state write made no progress")
                observe_campaign_write(allowance, count)
                offset += count
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        replace_campaign_write(allowance, temporary, path)
        verify_campaign_write(allowance, path)

    def load_state(self, path):
        from giclab.harness.t09_candidate_inputs import read_member

        if not path.exists():
            return
        document = json.loads(read_member(path.parent, path.name))
        if (
            set(document)
            != {
                "environment_sha256",
                "loaded",
                "tagged",
                "load_count",
                "removal_count",
                "before_load",
                "containers",
            }
            or document["environment_sha256"] != self.binding.digest
            or type(document["loaded"]) is not bool
            or type(document["tagged"]) is not bool
            or type(document["load_count"]) is not int
            or document["load_count"] not in {0, 1}
            or type(document["removal_count"]) is not int
            or document["removal_count"] not in {0, 1}
            or document["containers"] != {}
        ):
            raise RuntimeError("environment phase state drifted or has unresolved containers")
        before = set(document["before_load"])
        if not before <= {self.binding.image_id, self.tag}:
            raise RuntimeError("environment image observations switched identity")
        self.loaded, self.tagged = document["loaded"], document["tagged"]
        self.load_count, self.removal_count = document["load_count"], document["removal_count"]
        self.before_load = before

    def _result(self, argv, kwargs, code=0, stdout=b"", stderr=b""):
        if len(stdout) + len(stderr) > 1_048_576:
            raise RuntimeError("image model output exceeded its bound")
        values = []
        for key, value in (("stdout", stdout), ("stderr", stderr)):
            target = kwargs.get(key, subprocess.PIPE)
            if hasattr(target, "write"):
                if not Path(target.name).resolve().is_relative_to(self.transaction_root):
                    raise RuntimeError("image output escaped transaction")
                target.write(value)
                values.append(None)
            else:
                if target not in (subprocess.PIPE, subprocess.DEVNULL, None):
                    raise RuntimeError("image output target is not allowlisted")
                values.append(value if target == subprocess.PIPE else None)
        return subprocess.CompletedProcess(argv, code, *values)

    def _create_condition(self, argv, **kwargs):
        """Admit the bound condition command to the local process carrier."""
        if not self.loaded or self.condition_launch is None or argv.count("--name") != 1:
            raise RuntimeError("condition create lacks its bound process channel")
        name = argv[argv.index("--name") + 1]
        labels = [argv[i + 1] for i, item in enumerate(argv[:-1]) if item == "--label"]
        run_labels = [
            item.removeprefix("giclab.t09.run=")
            for item in labels
            if item.startswith("giclab.t09.run=")
        ]
        if len(run_labels) != 1 or run_labels[0] not in self.contract.run_ids:
            raise RuntimeError("condition command run identity is unbound")
        run_id = run_labels[0]
        ordinal = self.contract.run_ids.index(run_id) + 1
        expected_labels = [
            f"giclab.t09.plan={self.contract.plan_id}",
            f"giclab.t09.host_run={self.contract.host_run_id}",
            "giclab.t09.role=condition",
            f"giclab.t09.run={run_id}",
        ]
        if (
            labels != expected_labels
            or name != self.contract.container_prefix + f"{ordinal:02d}"
            or name in self.containers
        ):
            raise RuntimeError("condition command ownership differs")
        options = {
            "--ulimit": "core=0:0",
            "--platform": "linux/amd64",
            "--network": "bridge",
            "--log-driver": "none",
            "--ipc": "private",
            "--cap-drop": "ALL",
            "--security-opt": "no-new-privileges=true",
            "--restart": "no",
            "--cpus": "2.0",
            "--memory": "4g",
            "--memory-swap": "4g",
            "--pids-limit": "512",
            "--shm-size": "1g",
            "--user": "1000:1000",
            "--tmpfs": "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
            "--env": "CUDA_VISIBLE_DEVICES=",
            "--entrypoint": "/opt/sira/.venv/bin/python",
        }
        for key, value in options.items():
            if argv.count(key) != 1 or argv[argv.index(key) + 1] != value:
                raise RuntimeError("condition environment option differs: " + key)
        boundary = argv.index("--entrypoint") + 2
        if argv[boundary] != self.binding.image_id:
            raise RuntimeError("condition selected another image")
        mounts = {}
        for index, item in enumerate(argv[:boundary]):
            if item != "--mount":
                continue
            fields = argv[index + 1].split(",")
            if len(fields) not in (3, 4) or fields[0] != "type=bind":
                raise RuntimeError("condition mount shape differs")
            source = Path(fields[1].removeprefix("src="))
            destination = fields[2].removeprefix("dst=")
            if (
                not source.is_absolute()
                or source.is_symlink()
                or (
                    not source.resolve(strict=True).is_relative_to(self.transaction_root)
                    and not source.resolve(strict=True).is_relative_to(self.package)
                )
                or destination in mounts
                or (len(fields) == 4 and fields[3] != "readonly")
            ):
                raise RuntimeError("condition mount escaped bound source/transaction")
            mounts[destination] = {"source": str(source), "readonly": len(fields) == 4}
        context = self.condition_context
        if context is None or context.run_id != run_id:
            raise RuntimeError("condition command switched its phase input")
        commands = json.loads((self.package / self.contract.command_manifest_path).read_bytes())
        selected = [item for item in commands["manifests"] if item["run_id"] == run_id]
        if len(selected) != 1:
            raise RuntimeError("condition command manifest is ambiguous")
        manifest = selected[0]
        artifact = context.artifact_root
        raw = artifact / manifest["permitted_condition_owned"]["output_root"] / "raw"
        raw_relative = raw.relative_to(artifact).as_posix()
        control = self.contract.control_root_name
        expected_mounts = {
            "/opt/giclab-artifacts": (artifact, True),
            "/opt/giclab-artifacts/" + control + "/runtime-budget": (
                artifact / control / "runtime-budget",
                False,
            ),
            "/opt/giclab-artifacts/" + raw_relative: (raw, False),
            "/giclab/attempt": (raw, False),
            "/opt/giclab-artifacts/" + raw_relative + "/.giclab-supervisor": (
                raw / ".giclab-supervisor",
                True,
            ),
            "/giclab/attempt/.giclab-supervisor": (raw / ".giclab-supervisor", True),
            "/opt/giclab-src/giclab": (self.package / "src/giclab", True),
            "/opt/giclab-contracts/execution.json": (
                self.package / self.contract.execution_contract_path,
                True,
            ),
            "/opt/giclab-contracts/conditions": (
                self.package
                / "experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions",
                True,
            ),
            "/run/secrets/sira_api_key": (context.secret_file, True),
            "/opt/giclab/container_entrypoint.py": (
                self.package / "containers/sira-smoke/container_entrypoint.py",
                True,
            ),
        }
        if mounts != {
            key: {"source": str(path), "readonly": readonly}
            for key, (path, readonly) in expected_mounts.items()
        }:
            raise RuntimeError("condition mount role/path/mode differs from exact binding")
        index = 2
        while index < boundary:
            option = argv[index]
            if option in {"--read-only", "--init"}:
                if argv[:boundary].count(option) != 1:
                    raise RuntimeError("condition containment flag repeated")
                index += 1
            elif option in {*options, "--name", "--label", "--mount"}:
                index += 2
            else:
                raise RuntimeError("unmodeled condition option")
        if "--read-only" not in argv[:boundary] or "--init" not in argv[:boundary]:
            raise RuntimeError("condition containment flag missing")
        command = argv[boundary + 1 :]
        if command[:5] != [
            "/opt/giclab/container_entrypoint.py",
            "--supervised-release",
            "--runtime-assignment",
            "SIRA_API_KEY",
            "--",
        ]:
            raise RuntimeError("condition entrypoint differs")
        declared = manifest["argv"]
        split = declared.index("--")
        private = json.loads(
            (raw / ".giclab-supervisor/condition-admission-binding.json").read_bytes()
        )
        injected = [
            "--gate-admission-mode",
            "duplex-supervisor",
            "--gate-duplex-binding",
            "/giclab/attempt/.giclab-supervisor/condition-admission-binding.json",
            "--gate-duplex-session-id",
            private["binding"]["session_id"],
            "--gate-duplex-frozen-manifest-sha256",
            private["binding"]["frozen_manifest_sha256"],
            "--gate-duplex-transaction-root-identity",
            private["transaction_root_identity"],
        ]
        if command[5:] != [*declared[:split], *injected, *declared[split:]]:
            raise RuntimeError(
                "condition runtime argv differs from frozen command and admission binding"
            )
        identifier = sha(
            canonical({"environment": self.binding.digest, "run": run_id, "argv": argv})
        )
        self.containers[name] = {
            "id": identifier,
            "labels": dict(x.split("=", 1) for x in labels),
            "role": "condition",
            "status": "created",
            "run_id": run_id,
            "mounts": mounts,
            "command": command,
        }
        self.events.append(["condition-process-created", run_id, identifier])
        return self._result(argv, kwargs, stdout=(identifier + "\n").encode())

    def start_condition_process(self, argv, **kwargs):
        matches = [
            entry
            for entry in self.containers.values()
            if argv == ["docker", "start", "--attach", entry["id"]]
        ]
        if len(matches) != 1 or matches[0]["role"] != "condition" or self.condition_launch is None:
            raise RuntimeError("condition start lacks exact owned identity")
        entry = matches[0]
        if entry["status"] != "created":
            raise RuntimeError("condition process start replay")
        entry["status"] = "running"
        process = self.condition_launch(entry, **kwargs)
        self.condition_processes[entry["id"]] = process
        return process

    def _create_probe(self, argv, **kwargs):
        """Exact two qualification container shapes; no daemon is contacted."""
        if not self.loaded or self.contract is None or argv.count("--name") != 1:
            raise RuntimeError("probe create lacks a loaded bound image or exact name")
        name = argv[argv.index("--name") + 1]
        suffix = name.removeprefix(self.contract.container_prefix)
        roles = {
            "core-preflight": "core-suppression-preflight",
            "browser-preflight": "browser-lifecycle-preflight",
        }
        if suffix not in roles or name in self.containers:
            raise RuntimeError("probe create identity is unknown or occupied")
        role = roles[suffix]
        mounts = [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == "--mount"]
        if not mounts or not mounts[0].startswith("type=bind,src="):
            raise RuntimeError("probe create lacks its exact writable root")
        first = mounts[0].split(",")
        if len(first) != 3 or first[2] != "dst=/giclab/attempt":
            raise RuntimeError("probe writable mapping is malformed")
        attempt = Path(first[1][4:]).resolve(strict=True)
        expected_name = "core-suppression-preflight" if suffix == "core-preflight" else suffix
        if (
            attempt.name != expected_name
            or attempt.parent.name != self.contract.control_root_name
            or not attempt.is_relative_to(self.transaction_root)
        ):
            raise RuntimeError("probe writable root differs from transaction")
        labels = {
            "giclab.t09.plan": self.contract.plan_id,
            "giclab.t09.host_run": self.contract.host_run_id,
            "giclab.t09.role": role,
        }
        expected = ["docker", "create", "--ulimit", "core=0:0", "--name", name]
        for key, value in labels.items():
            expected += ["--label", f"{key}={value}"]
        expected += ["--platform", "linux/amd64", "--network", "none", "--log-driver", "none"]
        if suffix == "core-preflight":
            expected += [
                "--ipc",
                "private",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges=true",
                "--init",
                "--restart",
                "no",
                "--cpus",
                "2.0",
                "--memory",
                "4g",
                "--memory-swap",
                "4g",
                "--pids-limit",
                "512",
            ]
        else:
            expected += [
                "--read-only",
                "--init",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges=true",
            ]
        expected += [
            "--shm-size",
            "1g",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=134217728,uid=1000,gid=1000,mode=0700",
            "--user",
            "1000:1000",
            "--env",
            "CUDA_VISIBLE_DEVICES=",
            "--mount",
            f"type=bind,src={attempt},dst=/giclab/attempt",
        ]
        relative = (
            "containers/sira-smoke/pragmatic/t09_core_preflight.py"
            if suffix == "core-preflight"
            else "containers/sira-smoke/bounded/browser_preflight.py"
        )
        runtime = "/opt/giclab/" + (
            "t09_core_preflight.py" if suffix == "core-preflight" else "browser_preflight.py"
        )
        expected += ["--mount", f"type=bind,src={self.package / relative},dst={runtime},readonly"]
        if suffix == "core-preflight":
            expected += [
                "--mount",
                f"type=bind,src={self.package / 'containers/sira-smoke/container_entrypoint.py'},"
                "dst=/opt/giclab/container_entrypoint.py,readonly",
            ]
        expected += ["--entrypoint", "/opt/sira/.venv/bin/python", self.binding.image_id]
        if suffix == "core-preflight":
            expected += [
                "/opt/giclab/container_entrypoint.py",
                "--core-preflight",
                "--",
                "/opt/sira/.venv/bin/python",
            ]
        expected += [runtime]
        if argv != expected:
            raise RuntimeError("probe create command differs from exact bound shape")
        self.binding.validate(self.source_inputs, self.package)
        identifier = sha(canonical({"environment": self.binding.digest, "name": name}))
        self.containers[name] = {
            "id": identifier,
            "labels": labels,
            "status": "created",
            "attempt": str(attempt),
            "source": relative,
            "role": role,
        }
        return self._result(argv, kwargs, stdout=(identifier + "\n").encode())

    def _execute_core_probe(self, entry):
        """Execute retained suite/children/scanner with simulated OS/signal leaves."""
        import contextlib
        import resource
        import signal

        attempt = Path(entry["attempt"])
        source = self.package / entry["source"]
        self.source_inputs.source_sha256(self.package, entry["source"])
        spec = importlib.util.spec_from_file_location("offline_retained_core_probe", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ATTEMPT_ROOT = attempt
        module.TMP_ROOT = attempt / "offline-tmp"
        module.SHM_ROOT = attempt / "offline-shm"
        module.RECEIPT_PATH = attempt / "core-suppression-preflight.json"
        module.TMP_ROOT.mkdir(mode=0o700)
        module.SHM_ROOT.mkdir(mode=0o700)
        limits = None

        def set_limit(kind, value):
            nonlocal limits
            if kind != resource.RLIMIT_CORE or value != (0, 0) or limits is not None:
                raise RuntimeError("unbound core resource mutation")
            limits = tuple(self.binding.document()["process_observations"]["core_limits"])

        def get_limit(kind):
            if kind != resource.RLIMIT_CORE or limits is None:
                raise RuntimeError("unbound core resource observation")
            return (1, 1) if self.fault == "core-limit" else limits

        def child(argv, **options):
            if options.get("timeout") != 30 or argv[:2] != [sys.executable, str(source)]:
                raise RuntimeError("unbound core child operation")
            if argv[2:] in (["--inheritance-child", "1"], ["--inheritance-child", "2"]):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code = module.run(argv[2:])
                return subprocess.CompletedProcess(argv, code, stream.getvalue().encode())
            if argv[2:] == ["--abort-child"] and Path(options["cwd"]) == attempt:
                if get_limit(resource.RLIMIT_CORE) != (0, 0):
                    raise RuntimeError("simulated abort did not inherit core suppression")
                self.events.append(["simulated-signal", "SIGABRT"])
                return subprocess.CompletedProcess(argv, -int(signal.SIGABRT), b"")
            raise RuntimeError("unknown core child operation")

        module.resource = SimpleNamespace(
            RLIMIT_CORE=resource.RLIMIT_CORE, setrlimit=set_limit, getrlimit=get_limit
        )
        module.subprocess = SimpleNamespace(
            run=child, PIPE=subprocess.PIPE, DEVNULL=subprocess.DEVNULL
        )
        code = module.run([])
        self.events.append(["retained-core-suite", entry["id"], code])
        return code

    def _probe_container_operation(self, argv, **kwargs):
        target = argv[-1]
        matches = [
            (name, item) for name, item in self.containers.items() if target in {name, item["id"]}
        ]
        if len(matches) != 1:
            raise RuntimeError("probe operation lacks exact owned identity")
        name, entry = matches[0]
        process = self.condition_processes.get(entry["id"])
        if process is not None and process.poll() is not None:
            entry.update(status="exited", exit_code=process.returncode)
        if argv == ["docker", "kill", entry["id"]] and entry["role"] == "condition":
            if process is None:
                raise RuntimeError("condition kill has no recorded local producer")
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
            entry.update(status="exited", exit_code=process.returncode)
            return self._result(argv, kwargs)
        if argv == ["docker", "rm", "--force", entry["id"]] and process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            self.condition_processes.pop(entry["id"])
        if argv[1:3] == ["inspect", "--format"] and len(argv) == 5:
            observations = {
                "{{.Id}}": entry["id"],
                "{{.Name}}": "/" + name,
                "{{json .Config.Labels}}": json.dumps(entry["labels"]),
                "{{json .State}}": json.dumps(
                    {
                        "Status": entry["status"],
                        "Running": entry["status"] == "running",
                        "Paused": False,
                        "Restarting": False,
                        "OOMKilled": False,
                        "Dead": False,
                        "ExitCode": entry.get("exit_code", 0),
                    }
                ),
            }
            if argv[3] not in observations:
                raise RuntimeError("unbound probe inspection field")
            return self._result(argv, kwargs, stdout=(observations[argv[3]] + "\n").encode())
        if argv == ["docker", "rm", "--force", entry["id"]]:
            del self.containers[name]
            return self._result(argv, kwargs)
        expected_start = (
            ["docker", "start", "--attach", entry["id"]]
            if entry["role"] == "core-suppression-preflight"
            else ["docker", "start", entry["id"]]
        )
        if argv == expected_start and entry["status"] == "created":
            entry["status"] = "running"
            try:
                code = (
                    self._execute_core_probe(entry)
                    if entry["role"] == "core-suppression-preflight"
                    else self._execute_browser_probe(entry)
                )
            except Exception:
                entry.update(status="exited", exit_code=1)
                raise
            entry.update(status="exited", exit_code=code)
            return self._result(argv, kwargs, code)
        if (
            argv
            in (["docker", "wait", entry["id"]], ["docker", "stop", "--time", "10", entry["id"]])
            and entry["status"] == "exited"
        ):
            return self._result(argv, kwargs, stdout=b"0\n")
        raise RuntimeError("unbound probe operation or invalid lifecycle order")

    def _execute_browser_probe(self, entry):
        """Retained browser algorithm, with a stateful private Playwright leaf."""
        import contextlib
        import resource
        from types import ModuleType

        attempt = Path(entry["attempt"])
        image_root = self.binding.root / "image-files"
        static = image_root / "opt/giclab/fixtures/static.html"
        executable = image_root / "opt/ms-playwright/chromium-1084/chrome-linux/chrome"
        observations = self.binding.document()["process_observations"]
        proc = attempt / "offline-proc"
        proc.mkdir(mode=0o700)
        state = {"stage": "new"}

        def transition(before, after):
            if state["stage"] != before:
                raise RuntimeError("browser model lifecycle order drifted")
            state["stage"] = after
            self.events.append(["simulated-browser", before, after])

        class Page:
            def goto(inner, uri):
                if uri != static.resolve(strict=True).as_uri():
                    raise RuntimeError("browser model denied nonfixture navigation")
                transition("page", "navigated")

            def screenshot(inner, *, path):
                if Path(path) != attempt / "browser-preflight.png":
                    raise RuntimeError("browser screenshot output escaped exact target")
                transition("navigated", "captured")
                # Deterministic environmental output; never called a real render.
                with Path(path).open("xb") as stream:
                    stream.write(
                        bytes.fromhex(
                            "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
                            "0000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082"
                        )
                    )

            def title(inner):
                if state["stage"] != "captured":
                    raise RuntimeError("browser title observed out of order")
                return observations["browser_title"]

            def close(inner):
                transition("captured", "page-closed")

        class Context:
            def new_page(inner):
                transition("context", "page")
                return Page()

            def close(inner):
                transition("page-closed", "context-closed")

        class Browser:
            version = observations["browser_version"]

            def new_context(inner, *, viewport):
                if viewport != {"width": 1280, "height": 720}:
                    raise RuntimeError("browser viewport differs from contract")
                transition("launched", "context")
                return Context()

            def close(inner):
                transition("context-closed", "closed")
                if self.fault != "browser-residue":
                    (proc / "100/comm").unlink()
                    (proc / "100").rmdir()

        def launch(*, headless):
            if headless is not True:
                raise RuntimeError("browser model requires headless mode")
            transition("entered", "launched")
            (proc / "100").mkdir(mode=0o700)
            (proc / "100/comm").write_text("chromium\n")
            return Browser()

        @contextlib.contextmanager
        def playwright():
            transition("new", "entered")
            yield SimpleNamespace(
                chromium=SimpleNamespace(executable_path=str(executable), launch=launch)
            )
            transition("closed", "driver-closed")

        source = self.package / entry["source"]
        self.source_inputs.source_sha256(self.package, entry["source"])
        # Importing this explicit leaf never imports/starts an installed driver.
        fake = ModuleType("playwright.sync_api")
        fake.sync_playwright = playwright
        previous = sys.modules.get("playwright.sync_api")
        sys.modules["playwright.sync_api"] = fake
        try:
            spec = importlib.util.spec_from_file_location("offline_retained_browser_probe", source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            if previous is None:
                sys.modules.pop("playwright.sync_api")
            else:
                sys.modules["playwright.sync_api"] = previous
        module.ATTEMPT_ROOT = attempt
        roots = (attempt, attempt / "offline-tmp", attempt / "offline-shm")
        for root in roots[1:]:
            root.mkdir(mode=0o700)
        module.WRITABLE_CORE_SCAN_ROOTS = roots
        module.STATIC_PAGE, module.PACKAGE_MANIFEST = (
            static,
            image_root / "opt/giclab/installed-packages.txt",
        )
        module.Path = lambda value: proc if value == "/proc" else Path(value)
        module.os = SimpleNamespace(**{key: getattr(os, key) for key in dir(os)})
        module.os.environ = {}
        module.os.getuid = module.os.getgid = lambda: 1000
        limits = None

        def set_limit(kind, value):
            nonlocal limits
            if kind != resource.RLIMIT_CORE or value != (0, 0) or limits is not None:
                raise RuntimeError("browser core resource operation differs")
            limits = tuple(observations["core_limits"])

        def get_limit(kind):
            if kind != resource.RLIMIT_CORE or limits is None:
                raise RuntimeError("browser core resource observation precedes limit")
            return limits

        def version(name):
            if name != "playwright":
                raise RuntimeError("browser dependency observation is not bound")
            return "0.0" if self.fault == "browser-version" else observations["playwright_version"]

        module.resource = SimpleNamespace(
            RLIMIT_CORE=resource.RLIMIT_CORE, setrlimit=set_limit, getrlimit=get_limit
        )
        module.importlib = SimpleNamespace(metadata=SimpleNamespace(version=version))
        module.main()
        if state["stage"] != "driver-closed":
            raise RuntimeError("browser driver lifecycle incomplete")
        self.events.append(["retained-browser-probe", entry["id"], 0])
        return 0

    def run(self, argv, **kwargs):
        if not isinstance(argv, list) or argv[:1] != ["docker"]:
            raise RuntimeError("image model command prefix is not allowlisted")
        timeout = kwargs.get("timeout")
        if not isinstance(timeout, (float, int)) or not 0 < timeout <= 300:
            raise RuntimeError("image model command lacks finite timeout")
        image_id = self.binding.image_id
        if argv == ["docker", "info"]:
            self.events.append(list(argv))
            return self._result(argv, kwargs)
        references = {image_id, self.tag}
        self.events.append(list(argv))
        if argv[1:2] == ["create"]:
            if "giclab.t09.role=condition" in argv:
                return self._create_condition(argv, **kwargs)
            return self._create_probe(argv, **kwargs)
        if argv[1:2] in (["inspect"], ["start"], ["wait"], ["stop"], ["kill"], ["rm"]):
            return self._probe_container_operation(argv, **kwargs)
        if self.contract is not None and argv == [
            "docker",
            "ps",
            "--all",
            "--filter",
            f"label=giclab.t09.plan={self.contract.plan_id}",
            "--filter",
            f"label=giclab.t09.host_run={self.contract.host_run_id}",
            "--format",
            "{{.Names}}",
        ]:
            return self._result(
                argv,
                kwargs,
                stdout="".join(name + "\n" for name in sorted(self.containers)).encode(),
            )
        if (
            len(argv) == 7
            and argv[1:4] == ["ps", "--all", "--filter"]
            and argv[5:] == ["--format", "{{.ID}}"]
        ):
            selector = argv[4]
            if self.contract is None:
                raise RuntimeError("container inventory lacks transaction contract")
            if selector.startswith("name=^/") and selector.endswith("$"):
                name = selector[7:-1]
                if not name.startswith(self.contract.container_prefix):
                    raise RuntimeError("container inventory requested an unrelated name")
                entry = self.containers.get(name)
            elif selector.startswith("id=") and len(selector) == 67:
                entry = next(
                    (item for item in self.containers.values() if item["id"] == selector[3:]), None
                )
            else:
                raise RuntimeError("container inventory selector is not allowlisted")
            return self._result(
                argv, kwargs, stdout=(entry["id"] + "\n").encode() if entry else b""
            )
        if len(argv) == 6 and argv[1:5] == ["image", "inspect", "--format", "{{.Id}}"]:
            reference = argv[5]
            if reference not in references:
                raise RuntimeError("image inspection requested an unbound identity")
            if not self.load_count:
                self.before_load.add(reference)
            visible = self.loaded and (reference == image_id or self.tagged)
            observed = "sha256:" + "e" * 64 if self.fault == "wrong-image" else image_id
            return self._result(
                argv, kwargs, 0 if visible else 1, (observed + "\n").encode() if visible else b""
            )
        if len(argv) == 4 and argv[1:3] == ["load", "--input"]:
            if self.before_load != references or self.load_count or self.loaded:
                raise RuntimeError("image load violates inspect/once ordering")
            descriptors = kwargs.get("pass_fds", ())
            if len(descriptors) != 1 or argv[3] != f"/proc/self/fd/{descriptors[0]}":
                raise RuntimeError("image load lacks exact retained held descriptor")
            fd = descriptors[0]
            metadata = os.fstat(fd)
            expected = self.binding.document()["archive"]
            data = os.pread(fd, 1_048_577, 0)
            if metadata.st_size != expected["bytes"] or sha(data) != expected["sha256"]:
                raise RuntimeError("image load descriptor input drifted")
            self.load_count += 1
            self.loaded = self.fault != "missing"
            if self.fault == "timeout":
                raise subprocess.TimeoutExpired(argv, timeout, output=b"partial fixture load\n")
            if self.fault in {"load-error", "partial"}:
                return self._result(
                    argv, kwargs, 1, b"partial fixture load\n", b"fixture failure\n"
                )
            return self._result(argv, kwargs, stdout=b"simulated image load\n")
        if argv == ["docker", "tag", image_id, self.tag] and self.loaded and not self.tagged:
            self.tagged = True
            return self._result(argv, kwargs)
        if argv == ["docker", "image", "inspect", image_id] and self.loaded and self.tagged:
            import tarfile

            with tarfile.open(self.binding.archive_path, "r:") as archive:
                manifest = json.load(archive.extractfile("manifest.json"))
                config = json.load(archive.extractfile(manifest[0]["Config"]))
            return self._result(
                argv,
                kwargs,
                stdout=canonical(
                    [
                        {
                            "Id": image_id,
                            "Architecture": config["architecture"],
                            "Os": config["os"],
                            "Config": config["config"],
                            "RootFS": {"Type": "layers", "Layers": []},
                        }
                    ]
                ),
            )
        if argv == ["docker", "image", "rm", "--force", image_id] and self.loaded:
            self.loaded = self.tagged = False
            self.removal_count += 1
            return self._result(argv, kwargs)
        raise RuntimeError("image model denied unknown command or lifecycle transition")


def write(path, document):
    encoded = canonical(document)
    allowance = admit_campaign_write(path, len(encoded), CampaignWriterRole.PHASE_CONTROL)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(encoded):
            count = os.write(fd, memoryview(encoded)[offset : offset + 65536])
            if count <= 0:
                raise OSError("phase control write made no progress")
            observe_campaign_write(allowance, count)
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)
    verify_campaign_write(allowance, path)
    return path


def bound(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": sha(data)}


def instrument_bound_io(read_fd, write_fd, *, inject_continuations):
    """Test-only OS leaf faults on two held descriptors; all transport code is real."""
    original_read, original_write = os.read, os.write
    identities = {fd: (os.fstat(fd).st_dev, os.fstat(fd).st_ino) for fd in (read_fd, write_fd)}
    counts = {
        name: {"calls": 0, "eintr": 0, "eagain": 0, "bytes": 0, "short": 0}
        for name in ("read", "write")
    }

    def selected(fd, expected):
        if fd != expected:
            return False
        metadata = os.fstat(fd)
        return (metadata.st_dev, metadata.st_ino) == identities[fd]

    def step(name):
        counter = counts[name]
        counter["calls"] += 1
        if inject_continuations and counter["calls"] == 1:
            counter["eintr"] += 1
            raise InterruptedError("bound synthetic EINTR")
        if inject_continuations and counter["calls"] == 2:
            counter["eagain"] += 1
            raise BlockingIOError("bound synthetic EAGAIN")
        return counter

    def read(fd, count):
        if not selected(fd, read_fd):
            return original_read(fd, count)
        counter = step("read")
        limit = min(count, 3) if inject_continuations and counter["calls"] == 3 else count
        value = original_read(fd, limit)
        counter["bytes"] += len(value)
        counter["short"] += int(0 < len(value) < count)
        return value

    def write(fd, data):
        if not selected(fd, write_fd):
            return original_write(fd, data)
        counter = step("write")
        part = data[:3] if inject_continuations and counter["calls"] == 3 else data
        count = original_write(fd, part)
        counter["bytes"] += count
        counter["short"] += int(0 < count < len(data))
        return count

    os.read, os.write = read, write

    def restore():
        os.read, os.write = original_read, original_write

    return counts, restore


class RetainedCandidateEffects(DeterministicLowLevelEffects):
    def __init__(
        self, *, source_inputs, qualification_source_root=None, environment_binding=None, **kwargs
    ):
        super().__init__(source_inputs=source_inputs, **kwargs)
        self.source_inputs = source_inputs
        self.phase_receipts = {}
        self.transfer_request = None
        self.unstarted_transfer_request = None
        self.phase_events = []
        self.retained_closeouts = {}
        self.condition_invocations = {}
        self.condition_ownership = {}
        self.condition_io = {}
        self.wire_faults = []
        self.retained_exports = {}
        self.retained_export_attempts = set()
        self.qualification_source_root = qualification_source_root
        self.environment_binding = environment_binding
        self.remote_environment = None

    @contextlib.contextmanager
    def retained_observation_scope(self):
        """Bind the host validator's availability query to the same fake daemon.

        Only the environmental subprocess leaf is replaced on the retained host
        module. The evidence readers, start-intent validator and shared consumer
        still execute; all other dispatch continues through the process guard.
        """
        from giclab.control.production import _host_module

        if self.environment_binding is None:
            raise RuntimeError("retained observation lacks explicit environment binding")
        self.environment_binding.validate(self.source_inputs, self.repository)
        host = _host_module(self.repository)
        native = host.subprocess
        channel = ImageCommandChannel(
            self.environment_binding,
            tag=self.contract.replacement_image_tag,
            transaction_root=self._root,
            package=self.repository,
            source_inputs=self.source_inputs,
            contract=self.contract,
        )

        def run(argv, **kwargs):
            if argv == ["docker", "info"]:
                result = channel.run(argv, **kwargs)
                if len(channel.events) > 256:
                    raise RuntimeError("retained observation count exceeded bound")
                self.phase_events.append(
                    {
                        "phase": "retained-evidence-environment-observation",
                        "environment_sha256": self.environment_binding.digest,
                        "command": argv,
                        "returncode": result.returncode,
                    }
                )
                return result
            return native.run(argv, **kwargs)

        host.subprocess = SimpleNamespace(**{**vars(native), "run": run})
        try:
            yield
        finally:
            host.subprocess = native

    def implementation_identity(self):
        return repository_effect_identity(
            self.repository / RELATIVE,
            repository=self.repository,
            factory="RetainedCandidateEffects",
        )

    def _credential_target(self, provider_entry):
        journal = EarlyCleanupJournal(provider_entry.parent.parent / "preflight-cleanup-state")
        targets = [t for t in journal.load().targets if t.target_id == "temporary-remote-secret"]
        if len(targets) != 1:
            raise RuntimeError("candidate transfer lacks exact credential ownership")
        target = targets[0]
        path = Path(target.locator)
        if (
            target.kind is not CleanupTargetKind.TEMPORARY_REMOTE_CREDENTIAL
            or target.ownership_sha256 != cleanup_locator_identity(target.kind, target.locator)
            or not path.is_absolute()
            or not path.is_relative_to(self._root)
            or ".." in path.parts
            or any(p.is_symlink() for p in (path, *path.parents))
        ):
            raise RuntimeError("candidate credential target is outside its ownership binding")
        return path

    def _invoke(
        self,
        phase,
        *,
        binding,
        inputs,
        outputs,
        previous=None,
        expected_projection=None,
        execution=None,
        observer=None,
        cleanup_request=None,
    ):
        if (phase == "host-cleanup") != (cleanup_request is not None):
            raise RuntimeError("retained cleanup requires its explicit output authority")
        if cleanup_request is not None:
            authority = cleanup_request.output_authority
            if (
                authority is None
                or authority.binding.transaction_root != str(self._root)
                or authority.binding.candidate_sha256 != self.source_inputs.digest
                or authority.binding.handoff_sha256 != cleanup_request.immutable_handoff_sha256
                or authority.deadline != cleanup_request.cleanup_deadline_monotonic
            ):
                raise RuntimeError("retained cleanup output capability identity drift")
            authority.remaining()
        root = Path(binding["remote_root"])
        root.mkdir(mode=0o700, exist_ok=True)
        phase_root = root / "phases"
        phase_root.mkdir(mode=0o700, exist_ok=True)
        previous_path = self.phase_receipts.get(previous)
        instance = phase if execution is None else phase + "-" + execution.run_id
        provider_entry = (
            inputs["provider_entry_receipt"]
            if execution is None
            else self.transfer_request.provider_entry_receipt_path
        )
        if self.remote_environment is not None:
            binding = {**binding, "offline_environment_sha256": self.environment_binding.digest}
        request = {
            "schema_version": "1.0.0",
            "phase": phase,
            "execution_mode": "external-offline-candidate",
            "binding": binding,
            "previous_phase_receipt_path": str(previous_path) if previous_path else None,
            "previous_phase_receipt_sha256": sha(previous_path.read_bytes())
            if previous_path
            else None,
            "requested_wall_time": self._clock.wall_time(),
            "requested_monotonic": self._clock.monotonic(),
            "deadline_monotonic": (
                cleanup_request.cleanup_deadline_monotonic
                if cleanup_request is not None
                else self._clock.monotonic() + 60
            ),
            "inputs": {name: bound(path) for name, path in inputs.items()},
            "output_paths": {name: str(path) for name, path in outputs.items()},
            "expected_projection": expected_projection or {},
            "deterministic_fixture": False,
        }
        request_path = write(phase_root / f"{instance}-request.json", request)
        receipt_path = phase_root / f"{instance}-receipt.json"
        journal = provider_entry.parent.parent / "preflight-cleanup-state"
        package = self.repository
        argv = [
            "--provider-contract",
            self.contract.version,
            "--repository",
            str(package),
            "--artifact-root",
            str(root),
            "--package-commit",
            binding["source_commit"],
            phase,
            "--phase-request",
            str(request_path),
            "--phase-receipt",
            str(receipt_path),
        ]
        if execution is not None:
            argv = argv[:-2]
            boundary = argv.index(phase)
            argv[boundary:boundary] = [
                "--early-cleanup-journal",
                str(journal),
                "--secret-file",
                str(self._credential_target(provider_entry)),
                "--evaluator-overlay",
                str(root / "qualification-inputs/evaluator-overlay"),
            ]
            argv += ["--run-id", execution.run_id]
        if phase in {
            "host-transfer-verify",
            "host-preflight",
            "host-qualify",
            "host-freeze",
            "host-cleanup",
        }:
            argv += [
                "--dynamic-receipt",
                str(inputs["provider_entry_receipt"]),
                "--dynamic-source-root",
                str(inputs["provider_entry_receipt"].parent),
                "--early-cleanup-journal",
                str(journal),
                "--secret-file",
                str(self._credential_target(inputs["provider_entry_receipt"])),
            ]
        if phase == "host-qualify":
            # These are distinct retained input roles. Missing qualification or
            # image input is never replaced by an archive/source fixture receipt.
            argv += [
                "--local-finalizer-qualification",
                str(root / "qualification-inputs/local-finalizer-qualification.json"),
                "--replacement-image-archive",
                str(self.remote_environment / "offline-image.tar"),
                "--evaluator-overlay",
                str(root / "qualification-inputs/evaluator-overlay"),
            ]
        if phase == "host-freeze":
            argv += ["--model-metadata-receipt", str(inputs["model_metadata_receipt"])]
        document = self.source_inputs.document()
        invocation = {
            "snapshot": str(self.source_inputs.root.parent),
            "package": str(package),
            "parent_repository": str(self.source_inputs.parent_repository),
            "binding_sha256": self.source_inputs.digest,
            "parent_head": document["parent_head"],
            "parent_tree": document["parent_tree"],
            "transaction_root": str(self._root),
            "argv": argv,
            "wall": self._clock.wall_time(),
            "monotonic": self._clock.monotonic(),
            "fault_operation": self.fault_plan.fail_operation,
            "phase": phase,
            "instance": instance,
            "environment_root": str(self.remote_environment) if self.remote_environment else None,
            "environment_sha256": self.environment_binding.digest
            if self.environment_binding
            else None,
        }
        phase_started = time.monotonic()
        if cleanup_request is not None:
            result = self._cleanup_channel(invocation, phase_root, cleanup_request)
        elif execution is None:
            result = subprocess.run(
                [sys.executable, "-B", str(self.source_inputs.root / RELATIVE)],
                input=json.dumps(invocation),
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
                cwd=self.source_inputs.root,
                env={
                    "PATH": os.defpath,
                    "PYTHONPATH": str(self.source_inputs.root / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                },
            )
        else:
            assert observer is not None
            invocation_path = write(phase_root / f"{instance}-invocation.json", invocation)
            self.condition_invocations[execution.run_id] = invocation_path
            result = self._condition_channel(invocation_path, execution, observer)
        trace_path = self._root / "retained-phase-traces" / f"{instance}.json"
        trace = json.loads(trace_path.read_bytes()) if trace_path.exists() else None
        if trace is not None and (
            trace["candidate_binding_sha256"] != self.source_inputs.digest
            or trace["environment_sha256"] != invocation["environment_sha256"]
        ):
            raise RuntimeError("retained phase trace switched candidate/environment")
        clock_events = trace.get("clock_events", []) if trace else []
        if clock_events and (
            phase != "host-freeze"
            or len(clock_events) != 1
            or clock_events[0].get("operation") != "sleep"
            or not isinstance(clock_events[0].get("seconds"), (int, float))
            or not 0 <= clock_events[0]["seconds"] <= 120
        ):
            raise RuntimeError("retained phase returned an unbound environmental wait")
        # A real condition measures elapsed time in both processes. Carry that
        # interval into the campaign clock before cleanup or the next phase;
        # never infer chronology by editing a produced lifecycle receipt.
        elapsed = (
            time.monotonic() - phase_started
            if execution is not None or cleanup_request is not None
            else 0.0
        )
        self._clock.advance(0.5 + elapsed + sum(event["seconds"] for event in clock_events))
        self.phase_events.append(
            {
                "phase": phase,
                "returncode": result.returncode,
                "trace_sha256": sha(trace_path.read_bytes()) if trace is not None else None,
                "retained_calls": [entry["function"] for entry in trace["calls"]] if trace else [],
            }
        )
        if result.returncode:
            raise RuntimeError(f"retained candidate {phase} failed: {result.stderr[-8192:]}")
        if execution is not None:
            return None
        receipt = json.loads(receipt_path.read_bytes())
        self.phase_receipts[phase] = receipt_path
        return receipt

    def transfer_package_to_host(self, request):
        if self.fault_plan.fail_operation == "host.before-transfer":
            self.unstarted_transfer_request = request
            raise RuntimeError("injected carrier refusal before any transfer effect")
        self.transfer_request = request
        root = Path(request.binding.remote_root)
        root.mkdir(mode=0o700)
        if self.environment_binding is not None:
            from giclab.harness.t09_candidate_inputs import read_member
            from giclab.harness.t09_environment_fixture import load_environment_fixture

            remote = root / "environment-inputs"
            remote.mkdir(mode=0o700)
            self.environment_binding.validate(self.source_inputs, self.repository)
            names = [
                "environment.json",
                "offline-image.tar",
                self.environment_binding.document()["command_probe_input"]["path"],
                *(
                    item["path"]
                    for item in self.environment_binding.document()["overlay_input_members"]
                ),
                *(
                    item["path"]
                    for item in self.environment_binding.document()["image_file_members"]
                ),
            ]
            for name in names:
                data = read_member(self.environment_binding.root, name)
                (remote / name).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with (remote / name).open("xb") as stream:
                    stream.write(data)
                (remote / name).chmod(0o400)
                if name == self.environment_binding.document()["command_probe_input"]["path"]:
                    (remote / name).chmod(0o500)
            load_environment_fixture(
                remote,
                expected_sha256=self.environment_binding.digest,
                source=self.source_inputs,
                package=self.repository,
            )
            self.remote_environment = remote
        secret = self._credential_target(request.provider_entry_receipt_path)
        secret.parent.mkdir(mode=0o700, exist_ok=True)
        with secret.open("xb") as stream:
            stream.write(self.read_model_secret())
        secret.chmod(0o600)
        archive = root / "source-package.tar"
        if self.fault_plan.fail_operation == "matrix-transfer-partial":
            with (
                request.local_assembly.archive_path.open("rb") as source,
                archive.open("xb") as target,
            ):
                target.write(source.read(1024))
            raise RuntimeError("matrix partial SSH archive transfer")
        shutil.copyfile(request.local_assembly.archive_path, archive)
        archive.chmod(0o600)
        members = [m.to_document() for m in request.local_assembly.members]
        manifest = write(root / "source-members.json", {"members": members})
        assembly_document = asdict(request.local_assembly)
        assembly_document.pop("archive_path")
        assembly_document.pop("verification_archive_path")
        assembly = write(root / "local-assembly.json", assembly_document)
        binding = request.binding.to_document()
        binding["host_transfer_receipt_sha256"] = None
        acknowledgement = write(
            root / "transfer-ack.json",
            {
                "schema_version": "1.0.0",
                **{
                    k: v
                    for k, v in request.binding.to_document().items()
                    if k != "candidate_source_binding_sha256"
                },
                "remote_archive_bytes": archive.stat().st_size,
                "remote_archive_sha256": sha(archive.read_bytes()),
                "remote_member_manifest_sha256": sha(canonical(members)),
                "transfer_complete": True,
            },
        )
        journal = EarlyCleanupJournal(
            request.provider_entry_receipt_path.parent.parent / "preflight-cleanup-state"
        )
        cleanup = write(root / "entry-cleanup-state.json", journal.load().to_document())
        receipt = self._invoke(
            "host-transfer-verify",
            binding=binding,
            inputs={
                "local_assembly_receipt": assembly,
                "provider_entry_receipt": request.provider_entry_receipt_path,
                "remote_archive": archive,
                "remote_member_manifest": manifest,
                "host_acknowledgement": acknowledgement,
                "cleanup_state": cleanup,
            },
            outputs={},
        )
        value = HostPackageTransferReceipt(
            binding=request.binding,
            remote_package_path=str(archive),
            remote_manifest_path=str(manifest),
            remote_archive_bytes=archive.stat().st_size,
            remote_archive_sha256=sha(archive.read_bytes()),
            remote_members=request.local_assembly.members,
            remote_member_manifest_sha256=receipt["phase_outputs"]["remote_member_manifest_sha256"],
            host_acknowledgement_sha256=receipt["phase_outputs"]["host_acknowledgement_sha256"],
            started_wall_time=request.requested_wall_time,
            completed_wall_time=self._clock.wall_time(),
            started_monotonic=request.requested_monotonic,
            completed_monotonic=self._clock.monotonic(),
            cleanup_state_sha256=receipt["cleanup_state_sha256"],
            phase_output_sha256s=tuple(receipt["phase_output_sha256s"]),
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._transfer_receipt_identity(value)
        )

    def preflight_host(self, request):
        binding = request.binding.transfer.to_document()
        previous = json.loads(self.phase_receipts["host-transfer-verify"].read_bytes())
        binding["host_transfer_receipt_sha256"] = previous["receipt_sha256"]
        root = Path(binding["remote_root"])
        receipt = self._invoke(
            "host-preflight",
            binding=binding,
            inputs={
                "provider_entry_receipt": request.provider_entry_receipt_path,
            },
            outputs={
                "remote_path_qualification": root / "phases/path-qualification.json",
                "cleanup_state": root / "phases/preflight-cleanup.json",
            },
            previous="host-transfer-verify",
        )
        value = HostPreflightReceipt(
            binding=request.binding,
            previous_phase_receipt_sha256=request.binding.host_transfer_receipt_sha256,
            metadata_receipt_sha256=request.metadata_receipt_sha256,
            remote_path_qualification_sha256=receipt["phase_outputs"][
                "remote_path_qualification_sha256"
            ],
            started_wall_time=request.requested_wall_time,
            completed_wall_time=self._clock.wall_time(),
            started_monotonic=request.requested_monotonic,
            completed_monotonic=self._clock.monotonic(),
            cleanup_state_sha256=receipt["cleanup_state_sha256"],
            phase_output_sha256s=(
                *receipt["phase_output_sha256s"],
                receipt["cleanup_state_sha256"],
            ),
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._preflight_receipt_identity(value)
        )

    def qualify_host(self, request):
        if self.fault_plan.fail_operation == "host.qualify":
            raise RuntimeError("injected qualification-start failure")
        transfer = self.transfer_request
        assert transfer is not None
        binding = request.binding.transfer.to_document()
        previous = json.loads(self.phase_receipts["host-transfer-verify"].read_bytes())
        binding["host_transfer_receipt_sha256"] = previous["receipt_sha256"]
        root = Path(binding["remote_root"])
        qualification = root / "qualification-inputs"
        qualification.mkdir(mode=0o700)
        if self.qualification_source_root is None:
            raise RuntimeError("offline qualification lacks retained local producer inputs")
        for name in ("local-finalizer-qualification.json", "regression.json"):
            source = self.qualification_source_root / name
            data = source.read_bytes()
            target = qualification / name
            with target.open("xb") as output:
                output.write(data)
            target.chmod(0o600)
            if target.read_bytes() != data or source.read_bytes() != data:
                raise RuntimeError("offline qualification transfer changed derived input bytes")
        receipt = self._invoke(
            "host-qualify",
            binding=binding,
            inputs={
                "provider_entry_receipt": transfer.provider_entry_receipt_path,
                "local_finalizer_qualification": qualification
                / "local-finalizer-qualification.json",
                "offline_regression": qualification / "regression.json",
            },
            outputs={
                "qualification": root / "phases/qualification.json",
                "qualification_context": root / "phases/qualification-context.json",
                "cleanup_state": root / "phases/qualification-cleanup.json",
            },
            previous="host-preflight",
        )
        from giclab.control.production import _host_module

        host = _host_module(self.repository)
        commit = self.source_inputs.document()["parent_head"]
        sources = host.validate_finalizer_source(
            repository=self.repository,
            package_commit=commit,
            finalizer_commit=commit,
            source=self.repository / host.FINALIZER_RELATIVE_PATH,
            projection_source=self.repository / host.FINALIZER_PROJECTION_RELATIVE_PATH,
            source_inputs=self.source_inputs,
        )
        context = json.loads((root / "phases/qualification-context.json").read_bytes())
        observed = json.loads((root / "phases/qualification.json").read_bytes())
        local = context["local_finalizer_qualification"]
        if (
            sha((root / "phases/qualification-context.json").read_bytes())
            != receipt["phase_outputs"]["qualification_context_sha256"]
            or context["image_materialization"]["offline_environment_sha256"]
            != self.environment_binding.digest
        ):
            raise RuntimeError("retained qualification projection switched bound evidence")
        value = HostQualificationReceipt(
            binding=request.binding,
            previous_phase_receipt_sha256=request.preflight_receipt_sha256,
            replacement_image_tag=request.replacement_image_tag,
            image_materialization_policy=request.image_materialization_policy,
            qualification_id=request.active_image_qualification_id,
            local_finalizer_qualification_id=request.local_finalizer_qualification_id,
            image_materialization_receipt_sha256=observed["image_materialization_receipt_sha256"],
            image_digest=observed["image_digest"],
            python_interpreter="/opt/sira/.venv/bin/python",
            python_interpreter_sha256=observed["python_interpreter_sha256"],
            dependency_manifest_sha256=observed["dependency_manifest_sha256"],
            dependency_tree_sha256=observed["dependency_tree_sha256"],
            browser_qualification_sha256=observed["browser_qualification_sha256"],
            downstream_source_roles_sha256=sha(canonical(sources[5])),
            finalizer_source_sha256=sources[0],
            finalizer_projection_source_sha256=sources[1],
            finalizer_selector_sha256=sources[2],
            finalizer_schema_sha256=sources[3],
            local_finalizer_qualification_sha256=sha(
                (qualification / "local-finalizer-qualification.json").read_bytes()
            ),
            local_finalizer_interpreter=local["interpreter"],
            local_finalizer_interpreter_sha256=local["interpreter_sha256"],
            local_finalizer_dependency_manifest_sha256=local[
                "interpreter_dependency_manifest_sha256"
            ],
            local_finalizer_dependency_tree_sha256=local["interpreter_dependency_tree_sha256"],
            local_evaluator_dependency_tree_sha256=local["dependency_tree_sha256"],
            cleanup_readiness_sha256=observed["cleanup_readiness_sha256"],
            started_wall_time=request.requested_wall_time,
            completed_wall_time=self._clock.wall_time(),
            started_monotonic=request.requested_monotonic,
            completed_monotonic=self._clock.monotonic(),
            phase_output_sha256s=(
                *receipt["phase_output_sha256s"],
                receipt["cleanup_state_sha256"],
                sha(canonical(sources[5])),
            ),
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._qualification_receipt_identity(value)
        )

    def freeze_science(self, request):
        from giclab.control.remote_bridge import validate_full_dynamic_frozen_manifest
        from giclab.harness.t09_model_metadata_receipt import MODEL_METADATA_RECEIPT_FILENAME

        transfer = self.transfer_request
        if transfer is None or "host-qualify" not in self.phase_receipts:
            raise RuntimeError("offline freeze lacks retained qualification")
        binding = request.binding.transfer.to_document()
        binding["host_transfer_receipt_sha256"] = json.loads(
            self.phase_receipts["host-transfer-verify"].read_bytes()
        )["receipt_sha256"]
        root = Path(binding["remote_root"])
        control = root / self.contract.control_root_name
        receipt = self._invoke(
            "host-freeze",
            binding=binding,
            inputs={
                "provider_entry_receipt": transfer.provider_entry_receipt_path,
                "qualification_context": root / "phases/qualification-context.json",
                "model_metadata_receipt": transfer.provider_entry_receipt_path.parent
                / MODEL_METADATA_RECEIPT_FILENAME,
            },
            outputs={
                "full_frozen_manifest": control / "frozen-run-manifest.json",
                "postfreeze_validation": control / "postfreeze-validation.json",
                "compatibility_preflight_receipt": control / "preflight.json",
                "cleanup_state": root / "phases/freeze-cleanup.json",
            },
            previous="host-qualify",
            expected_projection=dict(request.expected_manifest_projection),
        )
        validated = validate_full_dynamic_frozen_manifest(
            self.repository,
            control / "frozen-run-manifest.json",
            contract=self.contract,
            expected_projection=request.expected_manifest_projection,
        )
        value = ScientificFreezeReceipt(
            binding=request.binding,
            previous_phase_receipt_sha256=request.qualification_receipt_sha256,
            manifest_path=control / "frozen-run-manifest.json",
            manifest_sha256=validated.file_sha256,
            manifest_schema_version=validated.schema_version,
            manifest_projection_sha256=validated.projection_sha256,
            postfreeze_validation_path=control / "postfreeze-validation.json",
            postfreeze_validation_sha256=receipt["phase_outputs"]["postfreeze_validation_sha256"],
            started_wall_time=request.started_wall_time,
            completed_wall_time=self._clock.wall_time(),
            started_monotonic=request.started_monotonic,
            completed_monotonic=self._clock.monotonic(),
            cleanup_state_sha256=receipt["cleanup_state_sha256"],
            phase_output_sha256s=(
                *receipt["phase_output_sha256s"],
                receipt["cleanup_state_sha256"],
            ),
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._freeze_receipt_identity(value)
        )

    def _condition_channel(self, invocation_path, request, observer):
        """Local SSH carrier: real retained host duplex, with the campaign observer."""
        from giclab.control.remote_bridge import (
            ConditionSessionBinding,
            ConditionSessionSupervisor,
            FramedDuplexEndpoint,
            SharedCarrierOutput,
            condition_session_id,
        )

        binding = ConditionSessionBinding(
            session_id=condition_session_id(request.run_id),
            provider_contract_version=self.contract.version,
            plan_id=self.contract.plan_id,
            host_run_id=self.contract.host_run_id,
            condition_run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            frozen_manifest_sha256=request.frozen_manifest_sha256,
        )
        shared_root = (
            request.transaction_root / "control-private/condition-bridges" / request.run_id
        )
        fault = self.fault_plan.fail_operation
        backpressure = fault in {"matrix-ipc-neverread", "matrix-ipc-midframe"}
        deadline = time.monotonic() + (15 if backpressure else 60)
        stderr_path = invocation_path.with_suffix(".stderr")
        carrier_output = SharedCarrierOutput(
            observer,
            transcript_path=shared_root / "shared-authoritative-transcript.json",
            terminal_path=shared_root / "shared-terminal-receipt.json",
            diagnostic_path=stderr_path,
        )
        terminal = None
        error = None
        from giclab.control.production import _host_module

        host = _host_module(self.repository)
        remote_root = Path(self.transfer_request.binding.remote_root)
        control_roots = (
            remote_root / self.contract.control_root_name,
            self.transfer_request.provider_entry_receipt_path.parent.parent
            / "preflight-cleanup-state",
        )
        control_before = sum(host.full_attempt_tree_usage(p).bytes for p in control_roots)
        owner = RetainedProcessOwner(deadline)
        process = None
        endpoint = None
        restore_io = None
        try:
            stderr_fd = owner.own_descriptor(
                os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            )
            process = owner.start(
                [
                    sys.executable,
                    "-B",
                    str(self.source_inputs.root / RELATIVE),
                    "--invocation",
                    str(invocation_path),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.source_inputs.root,
                env={
                    "PATH": os.defpath,
                    "PYTHONPATH": str(self.source_inputs.root / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                },
            )
            assert process.stdin is not None and process.stdout is not None
            assert process.stderr is not None
            owner.start_capture(
                process.stderr,
                lambda chunk: carrier_output.write_diagnostic(stderr_path, stderr_fd, chunk),
                lambda: os.fsync(stderr_fd),
            )
            endpoint = FramedDuplexEndpoint(
                reader=process.stdout,
                writer=process.stdin,
                binding=binding,
                deadline_monotonic=owner.work_deadline,
                cancelled=owner.cancelled,
            )
            if fault == "matrix-terminal-ack":
                original_event = endpoint.write_event

                def refused_ack(**kwargs):
                    if kwargs["event_type"] == "condition-session-terminal-ack":
                        self.wire_faults.append("terminal-ack-rejected")
                        kwargs["payload"] = {**kwargs["payload"], "accepted": False}
                    return original_event(**kwargs)

                endpoint.write_event = refused_ack
            if fault == "transaction-io-continuation" or backpressure:
                counts, restore_io = instrument_bound_io(
                    process.stdout.fileno(),
                    process.stdin.fileno(),
                    inject_continuations=not backpressure,
                )
                self.condition_io[request.run_id] = counts
            if backpressure:
                # The bound carrier peer consumes zero bytes or one 4096-byte
                # prefix. The real pipe must fill, then stop on the owner's
                # original deadline. These are fault bytes, not a phase receipt.
                from giclab.control.remote_bridge import _write_deadline

                _write_deadline(process.stdin.fileno(), b"x" * 524288, endpoint._remaining)
                raise AssertionError("backpressured peer unexpectedly accepted the whole probe")
            terminal = ConditionSessionSupervisor(
                endpoint,
                observer,
                accounting_document=observer.terminal_accounting_document,
            ).serve()
            process.stdin.close()
            owner.wait_for_completion()
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        finally:
            if restore_io is not None:
                restore_io()
            ownership = owner.close()
            self.condition_ownership[request.run_id] = ownership
            if ownership["errors"]:
                error = error or "retained condition ownership failed: " + "; ".join(
                    ownership["errors"]
                )
            if endpoint is not None:
                carrier_output.publish(
                    shared_root / "shared-authoritative-transcript.json",
                    endpoint.transcript_document(side="shared-authoritative"),
                )
            if terminal is not None:
                carrier_output.publish(
                    shared_root / "shared-terminal-receipt.json", terminal.to_document()
                )
        from giclab.control.production import _host_module

        # The retained process group and owned capture/descriptor lifetimes close above.
        # Count the complete remote attempt (including host suffixes and failure
        # copies) against its pre-existing grant. The runtime event remains raw.
        remote_attempt = (
            Path(self.transfer_request.binding.remote_root) / Path(request.raw_output_root).parent
        )
        if remote_attempt.exists():
            control_after = sum(host.full_attempt_tree_usage(p).bytes for p in control_roots)
            if control_after < control_before:
                raise RuntimeError("retained condition removed control occupancy")
            total = (
                host.full_attempt_tree_usage(remote_attempt).bytes + control_after - control_before
            )
            observer.retain_closed_remote_output(total_bytes=total)

        # Preserve the bounded carrier diagnostic separately from sealed raw.
        diagnostic = ""
        if stderr_path.exists():
            if stderr_path.stat().st_size > 65536:
                raise RuntimeError("retained condition diagnostic exceeded its finite cap")
            diagnostic = stderr_path.read_text(errors="replace")
        elif error is None:
            raise RuntimeError("retained condition diagnostic unexpectedly unavailable")
        if error:
            diagnostic += "\nshared carrier: " + error
        return subprocess.CompletedProcess(
            [],
            (process.returncode if process is not None else 1)
            if not error
            else ((process.returncode if process is not None else None) or 1),
            stdout="",
            stderr=diagnostic,
        )

    def _export_retained_attempt(self, request, observer):
        """Run retained stream/verify/restore/ack consumers over the local carrier."""
        from giclab.control.production import _host_module
        from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

        if observer is None:
            raise RuntimeError("retained export lacks its shared accountant")
        host = _host_module(self.repository)
        parent_allowance = _AdmittedPublicationAllowance(_EXPORT_CARRIER_RECORD_BYTES)
        remote = Path(self.transfer_request.binding.remote_root)
        local_attempt = (self._root / request.raw_output_root).parent
        local_control = self._root / self.contract.control_root_name
        roots = (remote, local_attempt, local_control)
        before = sum(host.full_attempt_tree_usage(p).bytes for p in roots if p.exists())
        if request.run_id in self.retained_export_attempts:
            raise RuntimeError(
                "retained export requires its recorded completion or explicit resume"
            )
        self.retained_export_attempts.add(request.run_id)
        invocation = json.loads(self.condition_invocations[request.run_id].read_bytes())
        inbound = self._root / "retained-exports" / request.run_id
        inbound.mkdir(mode=0o700, parents=True, exist_ok=False)
        instance = invocation["instance"] + "-export"
        invocation.update(
            instance=instance,
            export_output_grant={
                "scope": "retained-condition-export-only",
                "candidate_binding_sha256": self.source_inputs.digest,
                "environment_binding_sha256": self.environment_binding.digest,
                "run_id": request.run_id,
                "bytes": _EXPORT_OUTPUT_ALLOCATION_BYTES,
            },
            wall=self._clock.wall_time(),
            monotonic=self._clock.monotonic(),
            postcondition_export={
                "inbound": str(inbound),
                "restoration_root": str(self._root),
                "provider_entry": str(self.transfer_request.provider_entry_receipt_path),
                "run_id": request.run_id,
            },
        )
        invocation["export_output_grant_sha256"] = sha(canonical(invocation["export_output_grant"]))

        def publish_carrier(path, value):
            encoded = canonical(value)

            def admit(candidate, count):
                if candidate != path or not path.is_relative_to(inbound):
                    raise RuntimeError("export carrier changed its owned record role")
                parent_allowance(count)

            token = host._HOST_OUTPUT_ADMISSION.set(admit)
            try:
                host.write_bytes_exclusive(path, encoded)
            finally:
                host._HOST_OUTPUT_ADMISSION.reset(token)
            return path

        try:
            path = publish_carrier(inbound / (instance + "-invocation.json"), invocation)
            started = time.monotonic()
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(self.source_inputs.root / RELATIVE),
                    "--invocation",
                    str(path),
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.source_inputs.root,
                env={
                    "PATH": os.defpath,
                    "PYTHONPATH": str(self.source_inputs.root / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                },
            )
            self._clock.advance(time.monotonic() - started + 0.5)
            trace_path = self._root / "retained-phase-traces" / (instance + ".json")
            trace = json.loads(trace_path.read_bytes()) if trace_path.exists() else None
            if trace is not None and trace["candidate_binding_sha256"] != self.source_inputs.digest:
                raise RuntimeError("retained export switched candidate identity")
            self.phase_events.append(
                {
                    "phase": "retained-attempt-export",
                    "returncode": result.returncode,
                    "trace_sha256": sha(trace_path.read_bytes()) if trace else None,
                    "retained_calls": [entry["function"] for entry in trace["calls"]]
                    if trace
                    else [],
                }
            )
            if len(result.stderr.encode()) > 65536:
                raise RuntimeError("retained export diagnostic exceeded bound")
            publish_carrier(
                inbound / "carrier-result.json",
                {
                    "returncode": result.returncode,
                    "stderr": result.stderr,
                    "classification": "offline-carrier-result-not-export-acknowledgement",
                },
            )
            if result.returncode:
                raise RuntimeError("retained attempt export failed: " + result.stderr[-8192:])
            self.retained_exports[request.run_id] = inbound
        finally:
            after = sum(host.full_attempt_tree_usage(p).bytes for p in roots if p.exists())
            observed = after - before + host.full_attempt_tree_usage(inbound).bytes
            if observed < 0:
                raise RuntimeError("retained export removed previously counted evidence")
            observer.observe_controller_output_bytes(count=observed)

    def execute_condition(self, request, *, observer):
        from giclab.control.production import _host_module, retained_process_expectations
        from giclab.control.remote_bridge import (
            condition_session_id,
            expected_condition_bridge_evidence,
        )

        if self.transfer_request is None or "host-freeze" not in self.phase_receipts:
            raise RuntimeError("offline condition lacks actual retained freeze")
        observer.allocate_controller_output_bytes(
            count=_EXPORT_OUTPUT_ALLOCATION_BYTES + _EXPORT_CARRIER_RECORD_BYTES
        )
        binding = self.transfer_request.binding.to_document()
        binding["host_transfer_receipt_sha256"] = json.loads(
            self.phase_receipts["host-transfer-verify"].read_bytes()
        )["receipt_sha256"]
        root = Path(binding["remote_root"])
        paths = {"commands": self.repository / self.contract.command_manifest_path}
        frozen = root / self.contract.control_root_name / "frozen-run-manifest.json"
        condition_inputs = {
            "full_frozen_manifest": frozen,
            "command_manifest": paths["commands"],
            "condition_plan": self.repository / request.condition_plan_path,
        }
        checkpoint_projection = {}
        if request.first_pair_checkpoint is not None:
            checkpoint = self._root / "runtime-inputs" / (request.run_id + "-checkpoint.json")
            with checkpoint.open("xb") as stream:
                stream.write(request.first_pair_checkpoint)
            checkpoint.chmod(0o600)
            condition_inputs["shared_first_pair_checkpoint"] = checkpoint
            checkpoint_projection["shared_first_pair_checkpoint_sha256"] = sha(
                request.first_pair_checkpoint
            )
        try:
            self._invoke(
                "condition-session",
                binding=binding,
                inputs=condition_inputs,
                outputs={},
                previous="host-freeze",
                execution=request,
                observer=observer,
                expected_projection={
                    **checkpoint_projection,
                    "condition_run_id": request.run_id,
                    "evaluator_run_id": request.evaluator_run_id,
                    "frozen_manifest_sha256": request.frozen_manifest_sha256,
                    "command_package_sha256": sha(paths["commands"].read_bytes()),
                    "command_argv_sha256": request.command_sha256,
                    "condition_plan_sha256": request.condition_plan_sha256,
                    "zero_retry": True,
                    "shared_accounting_owner": "ConditionEventObserver",
                    "remote_authoritative_boundary": False,
                    "shared_process_expectations": retained_process_expectations(request),
                    "session_id": condition_session_id(request.run_id),
                    "transaction_root_identity": sha(
                        canonical(
                            {
                                "candidate": self.source_inputs.digest,
                                "transfer": binding,
                            }
                        )
                    ),
                },
            )
        except RuntimeError:
            # Recovery remains a failed condition. The real essential verifier,
            # export/restore/ack consumers, and shared held-prefix validator must
            # all succeed before any preservation claim is accepted.
            return self._interrupted_condition_outcome(request, observer, root)
        self._export_retained_attempt(request, observer)
        raw = request.transaction_root / request.raw_output_root
        completion = json.loads((raw.parent / "condition-session-completion.json").read_bytes())
        receipt = json.loads((raw.parent / "raw-attempt-complete.json").read_bytes())
        projection = raw.parent / "shared-control-projection"
        evidence_root = projection if completion["process_exit_code"] == 0 else raw
        return ConditionProcessOutcome(
            run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            exit_code=completion["process_exit_code"],
            completed=completion["completed"],
            answer=completion["answer"],
            error=completion["error"],
            raw_root=raw,
            raw_manifest_path=raw.parent / "raw-attempt-manifest.json",
            raw_receipt_path=raw.parent / "raw-attempt-complete.json",
            raw_file_count=receipt["raw_file_count"],
            raw_total_bytes=receipt["raw_total_bytes"],
            output_bytes=observer.output_total_bytes,
            call_ledger_path=evidence_root / "call-ledger.json",
            browser_ledger_path=evidence_root / "browser-ledger.json",
            completion_path=evidence_root / "completion.json",
            process_outcome_path=evidence_root / "process-outcome.json",
            control_projection_path=(
                projection / "manifest.json" if completion["process_exit_code"] == 0 else None
            ),
            retry_count=0,
            retained_source=RetainedConditionSource(
                authority="immutable-raw-attempt",
                manifest_path=raw.parent / "raw-attempt-manifest.json",
                receipt_path=raw.parent / "raw-attempt-complete.json",
                completion_path=raw.parent / "condition-session-completion.json",
                export_acknowledgement_path=(
                    _host_module(self.repository)._received_export_ack_path(
                        self._root, request.run_id
                    )
                ),
            ),
            bridge_evidence=expected_condition_bridge_evidence(
                transaction_root=request.transaction_root, raw_root=raw, run_id=request.run_id
            ),
        )

    def _interrupted_condition_outcome(self, request, observer, remote_root):
        from giclab.control.production import _host_module
        from giclab.control.remote_bridge import retained_failure_bridge_evidence

        host = _host_module(self.repository)
        commands = host.load_object(
            self.repository / self.contract.command_manifest_path,
            label="interrupted condition commands",
        )
        manifest = host._manifest_for_contract(commands, request.run_id, self.contract)
        remote_attempt = remote_root / host.manifest_output_root(manifest)
        completion = host.read_retained_essential_condition_completion(
            attempt_root=remote_attempt,
            run_id=request.run_id,
            package_commit=request.package_commit,
            condition_manifest=manifest,
        )
        if (
            completion["infrastructure_invalid"] is not True
            or completion["evaluator_eligible"] is not False
            or completion["evidence_authority"] != "essential-infrastructure-failure"
        ):
            raise RuntimeError("interrupted carrier lacks validated essential authority")
        self._export_retained_attempt(request, observer)
        attempt = (self._root / request.raw_output_root).parent
        retained = attempt / "essential-failure"
        local = host.read_retained_essential_condition_completion(
            attempt_root=attempt,
            run_id=request.run_id,
            package_commit=request.package_commit,
            condition_manifest=manifest,
        )
        if (
            local != completion
            or json.loads((attempt / "condition-session-completion.json").read_bytes()) != local
        ):
            raise RuntimeError("interrupted source changed during retained export")
        seal = json.loads((attempt / "essential-failure-manifest.json").read_bytes())
        bridge, prefix = retained_failure_bridge_evidence(
            transaction_root=self._root, essential_root=retained, run_id=request.run_id
        )
        return ConditionProcessOutcome(
            run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            exit_code=local["process_exit_code"],
            completed=local["completed"],
            answer=local["answer"],
            error=local["error"],
            raw_root=retained,
            raw_manifest_path=attempt / "essential-failure-manifest.json",
            raw_receipt_path=attempt / "essential-failure-complete.json",
            raw_file_count=len(seal["files"]),
            raw_total_bytes=seal["total_bytes"],
            output_bytes=observer.output_total_bytes,
            call_ledger_path=retained / "provider-call-lifecycle.json",
            browser_ledger_path=retained / "normalized-events.jsonl",
            completion_path=attempt / "condition-session-completion.json",
            process_outcome_path=retained / "failure-summary.json",
            retry_count=0,
            retained_source=RetainedConditionSource(
                authority="essential-infrastructure-failure",
                manifest_path=attempt / "essential-failure-manifest.json",
                receipt_path=attempt / "essential-failure-complete.json",
                completion_path=attempt / "condition-session-completion.json",
                export_acknowledgement_path=host._received_export_ack_path(
                    self._root, request.run_id
                ),
            ),
            bridge_evidence=bridge,
            partial_bridge_evidence=prefix,
        )

    def _cleanup_channel(self, invocation, phase_root, request):
        assert request.output_authority is not None
        deadline = time.monotonic() + request.output_authority.remaining()
        owner = RetainedProcessOwner(deadline)
        try:
            return self._cleanup_channel_owned(invocation, phase_root, request, owner)
        finally:
            owner.close()

    def _cleanup_channel_owned(self, invocation, phase_root, request, owner):
        """One owner carries the retained child, every pipe and console to teardown."""
        authority = request.output_authority
        assert authority is not None
        process = None
        streams = []
        error = None
        inventory_before = None
        inventory_result = None
        inventory_error = None
        transcript_path = phase_root / "host-cleanup-output-admission.json"
        # No resource allocation precedes this reserved failure-envelope capacity.
        transcript_grant = admit_campaign_write(
            transcript_path, 2 * 1024 * 1024, CampaignWriterRole.PHASE_CONTROL
        )
        assert transcript_grant is not None
        try:
            parent_read, child_write = owner.pipe()
            child_read, parent_write = owner.pipe()
            invocation = {
                **invocation,
                "cleanup_output": {
                    "binding": authority.binding.document(),
                    "read_descriptor": child_read,
                    "write_descriptor": child_write,
                    "deadline": owner.work_deadline,
                },
            }
            invocation_path = write(phase_root / "host-cleanup-invocation.json", invocation)
            channel = CleanupOutputChannel(
                parent_read, authority.binding, owner.work_deadline, write_fd=parent_write
            )
            channel.cancelled = owner.cancelled
            env = {
                "PATH": os.defpath,
                "PYTHONPATH": str(self.source_inputs.root / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
            }
            for suffix in ("stdout", "stderr"):
                path = phase_root / ("host-cleanup-" + suffix + ".log")
                lease = admit_campaign_write(path, 65536, CampaignWriterRole.PHASE_CONTROL)
                assert lease is not None
                fd = owner.own_descriptor(
                    os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                )
                streams.append((path, lease, fd))
            inventory_before = cleanup_output_inventory(self._root)
            process = owner.start(
                [
                    sys.executable,
                    "-B",
                    str(self.source_inputs.root / RELATIVE),
                    "--invocation",
                    str(invocation_path),
                ],
                cwd=self.source_inputs.root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(child_read, child_write),
            )
            owner.close_descriptor(child_read)
            owner.close_descriptor(child_write)

            def capture(item, chunk):
                _path, lease, fd = item
                if lease.observed + len(chunk) > lease.granted:
                    raise RuntimeError("cleanup child console grant exhausted")
                offset = 0
                while offset < len(chunk):
                    written = os.write(fd, chunk[offset:])
                    if written <= 0:
                        raise OSError("cleanup capture short write")
                    lease.observe(written)
                    offset += written

            def finalize(item):
                path, lease, fd = item
                os.fsync(fd)
                verify_campaign_write(lease, path)

            for stream, item in zip((process.stdout, process.stderr), streams, strict=True):
                owner.start_capture(
                    stream,
                    lambda chunk, item=item: capture(item, chunk),
                    lambda item=item: finalize(item),
                )
            if self.fault_plan.fail_operation == "cleanup.admission-disconnect":
                owner.close_descriptor(parent_write)
                raise RuntimeError("injected cleanup admission carrier disconnect")
            channel.serve(authority)
            owner.wait_for_completion()
        except BaseException as exc:
            error = type(exc).__name__ + ": " + str(exc)
        finally:
            ownership = owner.close()
            if ownership["errors"]:
                error = error or "retained process ownership failed: " + "; ".join(
                    ownership["errors"]
                )
            if process is not None and process.returncode:
                error = error or "retained cleanup child returned nonzero"
            if inventory_before is not None:
                try:
                    inventory_after = cleanup_output_inventory(self._root)
                    inventory_result = reconcile_cleanup_output(
                        inventory_before,
                        inventory_after,
                        authority,
                        parent_leases=tuple(item[1] for item in streams),
                    )
                except BaseException as exc:
                    inventory_error = type(exc).__name__ + ": " + str(exc)
                    error = error or inventory_error
            record = {
                "inventory": inventory_result,
                "inventory_error": inventory_error,
                "binding": authority.binding.document(),
                "deadline": owner.deadline,
                "events": authority.events,
                "error": error,
                "capture_errors": ownership["errors"],
                "ownership": ownership,
                "child_exit": process.returncode if process is not None else None,
                "reaped": ownership["reaped"],
                "capture_threads_stopped": ownership["capture_workers"] == 0,
                "grant_releases": 0,
                "counting_scope": (
                    "cumulative-actual-write-bytes; full-temporary-grants; "
                    "independent-publication-occupancy"
                ),
                "leases": [
                    {
                        "path": str(x.path),
                        "role": x.role.value,
                        "granted": x.granted,
                        "observed": x.observed,
                        "retired_bytes": x.retired_bytes,
                        "temporary_path": str(x.temporary_path) if x.temporary_path else None,
                    }
                    for x in authority.leases
                ],
            }
            encoded = canonical(record)
            if len(encoded) > transcript_grant.granted:
                raise RuntimeError("cleanup admission transcript exceeded prefunded bound")
            fd = os.open(
                transcript_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            try:
                offset = 0
                while offset < len(encoded):
                    count = os.write(fd, memoryview(encoded)[offset : offset + 65536])
                    if count <= 0:
                        raise OSError("cleanup transcript write made no progress")
                    transcript_grant.observe(count)
                    offset += count
                os.fsync(fd)
            finally:
                os.close(fd)
            verify_campaign_write(transcript_grant, transcript_path)
        if error:
            diagnostic = streams[1][0].read_text()[-8192:] if len(streams) == 2 else ""
            raise RuntimeError("cleanup admission child failed: " + error + " " + diagnostic)
        return subprocess.CompletedProcess([], process.returncode, "", "")

    def cleanup_transaction(self, request):
        transfer = self.transfer_request
        if transfer is None:
            return self._cleanup_before_transfer(request)
        binding = transfer.binding.to_document()
        predecessor = next(
            (
                name
                for name in (
                    "host-freeze",
                    "host-qualify",
                    "host-preflight",
                    "host-transfer-verify",
                )
                if name in self.phase_receipts
            ),
            None,
        )
        phase_transfer = self.phase_receipts.get("host-transfer-verify")
        binding["host_transfer_receipt_sha256"] = (
            None
            if phase_transfer is None
            else json.loads(phase_transfer.read_bytes())["receipt_sha256"]
        )
        root = Path(binding["remote_root"])
        self._invoke(
            "host-cleanup",
            binding=binding,
            inputs={
                "provider_entry_receipt": transfer.provider_entry_receipt_path,
            },
            outputs={
                "cleanup_terminal": root / "phases/cleanup-terminal.json",
                "cleanup_state": root / "phases/cleanup-state.json",
            },
            previous=predecessor,
            cleanup_request=request,
        )
        terminal = json.loads((root / "phases/cleanup-terminal.json").read_bytes())
        retained_path = Path(terminal["retained_cleanup_source"]["path"])
        assert sha(retained_path.read_bytes()) == terminal["retained_cleanup_sha256"]
        retained = terminal["remote_cleanup_observation"]
        handle = request.provider_handle
        assert handle is not None
        campaign_root = transfer.provider_entry_receipt_path.parent.parent
        transport = self.campaign_closeout_transport(
            contract=self.contract,
            launch_ordinal=handle.launch_ordinal,
            handle=handle,
            clock=self._clock,
        )
        with self.campaign_scope():
            closeout_path = provider.closeout_campaign(
                contract=self.contract,
                repository=self.repository,
                package_commit=binding["source_commit"],
                authorization_ledger=self._root / "control-private/authorization-overlay.json",
                dotenv=self._root / "control-private/mixed.env",
                private_root=campaign_root,
                transport=transport,
                remote_cleanup_journal=campaign_root / "preflight-cleanup-state",
                clock=self._clock.wall_time,
                sleeper=self._clock.sleep,
            )
        closeout = json.loads(closeout_path.read_bytes())
        assert closeout["terminal_or_absent"] is True
        assert closeout["zero_t09_instances"] is True
        self.retained_closeouts[handle.launch_ordinal] = closeout_path
        value = CleanupExecutionReceipt(
            immutable_handoff_sha256=request.immutable_handoff_sha256,
            owned_containers_absent=retained["owned_container_residue"] == [],
            exact_secret_matches=len(retained["global_secret_matching_paths"]),
            structural_privacy_findings=tuple(retained["structural_privacy_violations"]),
            remote_secret_removed=retained["remote_secret_removed"],
            firewall_restored=closeout["security_restored"],
            rulesets_restored=closeout["security_restored"],
            started_wall_time=request.started_wall_time,
            completed_wall_time=self._clock.wall_time(),
            started_monotonic=request.started_monotonic,
            completed_monotonic=self._clock.monotonic(),
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._cleanup_receipt_identity(value)
        )

    def _cleanup_before_transfer(self, request):
        """Use durable provider ownership before any retained host phase exists."""
        handle = request.provider_handle
        if (
            handle is None
            or self.unstarted_transfer_request is None
            or self.phase_receipts
            or self.remote_environment is not None
            or request.empirical_prefix
            or request.raw_prefix
        ):
            raise RuntimeError("pre-transfer cleanup does not match a zero-transfer prefix")
        planned = self.unstarted_transfer_request
        remote_root = Path(planned.binding.remote_root)
        if (
            planned.binding.provider_handle_identity != handle.opaque_identity
            or remote_root != self._root / f"offline-remote-{handle.launch_ordinal}"
            or os.path.lexists(remote_root)
        ):
            raise RuntimeError("planned pre-transfer root is not exactly absent")
        campaign_root = (
            self._root / "control-private" / f"campaign-slot-{handle.launch_ordinal:02d}"
        )
        entry = campaign_root / "entry-source/entry-receipt.json"
        controls = self.campaign_low_level_controls()
        journal = provider._cleanup_journal_for_closeout(
            contract=self.contract,
            private_root=campaign_root,
            package_commit=controls.expected_package_commit,
            plan_sha256=provider.file_sha256(self.repository / self.contract.provider_profile_path),
            remote_cleanup_journal=None,
        )
        state = journal.load()
        if state.provider_instance_identity_sha256 != handle.opaque_identity:
            raise RuntimeError("pre-transfer cleanup owner differs from provider handle")
        remote = self._credential_target(entry)
        if os.path.lexists(remote):
            raise RuntimeError("pre-transfer credential absence is contradicted")
        if any(t.kind is CleanupTargetKind.OWNED_CONTAINER for t in state.targets):
            raise RuntimeError("pre-transfer journal unexpectedly owns a container")
        # This is an actual exact-path observation under the bound environmental
        # double. Record it through the retained journal, with no host receipt or
        # synthetic freeze and no interpretation of an absent transfer as cleanup.
        journal.record_result(
            target_id="temporary-remote-secret",
            result=CleanupTargetState.ABSENT,
            detail_code="exact-pre-transfer-credential-path-absent",
            clock=self._clock.wall_time,
        )
        transport = self.campaign_closeout_transport(
            contract=self.contract,
            launch_ordinal=handle.launch_ordinal,
            handle=handle,
            clock=self._clock,
        )
        with self.campaign_scope():
            path = provider.closeout_campaign(
                contract=self.contract,
                repository=self.repository,
                package_commit=controls.expected_package_commit,
                authorization_ledger=self._root / "control-private/authorization-overlay.json",
                dotenv=self._root / "control-private/mixed.env",
                private_root=campaign_root,
                transport=transport,
                clock=self._clock.wall_time,
                sleeper=self._clock.sleep,
            )
        closed = json.loads(path.read_bytes())
        final = journal.load()
        if final.terminal_cleanup_disposition is not TerminalCleanupDisposition.COMPLETE:
            raise RuntimeError("retained pre-transfer cleanup journal is unresolved")
        self.retained_closeouts[handle.launch_ordinal] = path
        from giclab.control.production import _host_module

        # Execute the retained scanner on the exact planned, observed-absent
        # remote artifact root. Public and held local evidence is additionally
        # scanned by ProductionCategory3World.scan_privacy after this receipt.
        privacy = _host_module(self.repository).privacy_violations(remote_root)
        value = CleanupExecutionReceipt(
            immutable_handoff_sha256=request.immutable_handoff_sha256,
            owned_containers_absent=not any(
                t.kind is CleanupTargetKind.OWNED_CONTAINER for t in final.targets
            ),
            exact_secret_matches=int(os.path.lexists(remote)),
            structural_privacy_findings=tuple(privacy),
            remote_secret_removed=not os.path.lexists(remote),
            firewall_restored=closed["security_restored"],
            rulesets_restored=closed["security_restored"],
            started_wall_time=request.started_wall_time,
            completed_wall_time=self._clock.wall_time(),
            started_monotonic=request.started_monotonic,
            completed_monotonic=self._clock.monotonic(),
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._cleanup_receipt_identity(value)
        )

    def provider_terminate(self, handle):
        if handle.launch_ordinal in self.retained_closeouts:
            closeout = json.loads(self.retained_closeouts[handle.launch_ordinal].read_bytes())
            assert closeout["zero_t09_instances"] is True
            assert self.provider_inventory() == ()
            return
        return super().provider_terminate(handle)

    def finalize_condition(self, request):
        from giclab.control.production import _host_module
        from giclab.harness.t09_qualification_fixture import DATASET_PATH, EVALUATOR_ROOT

        host = _host_module(self.repository)
        observer = request.output_observer
        if observer is None:
            raise RuntimeError("retained finalizer lacks shared output admission")
        grant = {
            "schema_version": "1.0.0",
            "scope": "condition-finalizer-output-only",
            "run_id": request.run_id,
            "candidate_binding_sha256": self.source_inputs.digest,
            "raw_manifest_sha256": request.raw_manifest_sha256,
            "host_bytes": _FINALIZER_OUTPUT_ALLOCATION_BYTES,
            "derived_bytes": _FINALIZER_OUTPUT_ALLOCATION_BYTES,
        }
        observer.allocate_controller_output_bytes(
            count=grant["host_bytes"] + grant["derived_bytes"]
        )
        for artifact in request.raw_artifacts:
            artifact.revalidate()
        remote = Path(self.transfer_request.binding.remote_root)
        before_remote = host.full_attempt_tree_usage(remote).bytes
        before_local = (
            host.full_attempt_tree_usage(request.finalized_root).bytes
            if request.finalized_root.exists()
            else 0
        )
        invocation = json.loads(self.condition_invocations[request.run_id].read_bytes())
        original = invocation["instance"]
        invocation.update(
            instance=original + "-finalizer",
            wall=self._clock.wall_time(),
            monotonic=self._clock.monotonic(),
            finalizer_output_grant=grant,
            finalizer_output_grant_sha256=sha(canonical(grant)),
            postcondition_finalizer={
                "run_id": request.run_id,
                "evaluator_root": str(self.repository / EVALUATOR_ROOT),
                "dataset": str(self.repository / DATASET_PATH),
            },
        )
        path = write(
            self._root / "runtime-inputs" / (original + "-finalizer-invocation.json"), invocation
        )
        started = time.monotonic()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(self.source_inputs.root / RELATIVE),
                    "--invocation",
                    str(path),
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=90,
                cwd=self.source_inputs.root,
                env={
                    "PATH": os.defpath,
                    "PYTHONPATH": str(self.source_inputs.root / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                },
            )
            self._clock.advance(time.monotonic() - started + 0.5)
            trace_path = self._root / "retained-phase-traces" / (invocation["instance"] + ".json")
            trace = json.loads(trace_path.read_bytes()) if trace_path.exists() else None
            self.phase_events.append(
                {
                    "phase": "retained-finalization",
                    "returncode": result.returncode,
                    "trace_sha256": sha(trace_path.read_bytes()) if trace else None,
                    "retained_calls": [entry["function"] for entry in trace["calls"]]
                    if trace
                    else [],
                }
            )
            write(
                self._root / "runtime-inputs" / (original + "-finalizer-result.json"),
                {
                    "returncode": result.returncode,
                    "stderr": result.stderr[-65536:],
                    "classification": "actual-finalizer-subprocess-result",
                },
            )
            if result.returncode:
                raise RuntimeError("retained finalizer failed: " + result.stderr[-8192:])
            # The retained result is validated before adapting the shared output role.
            return self._retained_finalizer_outcome(request, invocation)

        finally:
            after_remote = host.full_attempt_tree_usage(remote).bytes
            after_local = (
                host.full_attempt_tree_usage(request.finalized_root).bytes
                if request.finalized_root.exists()
                else 0
            )
            observed = after_remote - before_remote + after_local - before_local
            if observed < 0:
                raise RuntimeError("finalizer removed retained output occupancy")
            observer.observe_controller_output_bytes(count=observed)

    def _retained_finalizer_outcome(self, request, invocation):
        from giclab.control.production import _host_module

        host = _host_module(self.repository)
        from giclab.harness.t09_qualification_fixture import (
            load_deterministic_qualification_archive,
        )

        fixture = load_deterministic_qualification_archive(
            self.repository,
            self._root / "qualification-archive/offline-qualification-fixture.tar.gz",
        )
        result = json.loads(
            (
                self._root / "runtime-inputs" / (invocation["instance"] + "-receipt.json")
            ).read_bytes()
        )
        remote = Path(self.transfer_request.binding.remote_root)
        retained = remote / result["finalized_output_root"]
        if not retained.resolve(strict=True).is_relative_to(remote):
            raise RuntimeError("retained finalization escaped its bound host")
        outcome, _evidence, semantic, files = host.validate_finalized_attempt(
            repository=self.repository,
            finalized_root=retained,
            run_id=request.run_id,
            contract=self.contract,
            source_inputs=self.source_inputs,
            environment_binding=self.environment_binding,
            fixture_binding=fixture,
        )
        complete = json.loads((retained / "finalization-complete.json").read_bytes())
        if (
            sha((retained / "finalization-complete.json").read_bytes())
            != result["finalization_complete_sha256"]
            or complete["raw_manifest_sha256_before"] != request.raw_manifest_sha256
            or complete["raw_manifest_sha256_after"] != request.raw_manifest_sha256
            or complete["raw_receipt_sha256"] != request.raw_receipt_sha256
            or complete["output_files"] != files
            or complete["semantic_projection_sha256"] != host.canonical_sha256(semantic)
        ):
            raise RuntimeError("retained finalizer source/output binding differs")
        source_sessions = sorted((request.raw_root / "sira-output").glob("*.json"))
        if len(source_sessions) != 1:
            raise RuntimeError("retained finalization requires one actual session")
        rows = [
            (
                retained / f["path"],
                request.finalized_root / "retained" / f["path"],
                f["bytes"],
                f["sha256"],
            )
            for f in files
        ]
        rows.append(
            (
                retained / "finalization-complete.json",
                request.finalized_root / "retained/finalization-complete.json",
                (retained / "finalization-complete.json").stat().st_size,
                result["finalization_complete_sha256"],
            )
        )
        session_paths = []
        for source in source_sessions:
            held = next(a for a in request.raw_artifacts if a.path == source)
            held.revalidate()
            destination = request.finalized_root / "source-sessions" / source.name
            rows.append((source, destination, held.bytes, held.sha256))
            session_paths.append(destination)
        for source, destination, count, digest in rows:
            if source.is_symlink() or count > host.MAX_FINALIZED_DERIVED_BYTES:
                raise RuntimeError("retained finalizer export member is unsafe")
            with source.open("rb") as stream:
                host._write_stream_exclusive_or_compare(
                    stream=stream,
                    destination=destination,
                    expected_bytes=count,
                    expected_sha256=digest,
                    before_output_growth=lambda _path, count: (
                        request.output_observer.allocate_controller_output_bytes(count=count)
                    ),
                )
        for artifact in request.raw_artifacts:
            artifact.revalidate()
        valid = (
            outcome["invalid_infrastructure_attempt"] is False
            and outcome["missing_evidence"] is False
            and outcome["process_exit"]["code"] == 0
        )
        completion = {
            name: getattr(request, name)
            for name in (
                "run_id",
                "evaluator_run_id",
                "execution_mode",
                "runtime_qualification_id",
                "runtime_qualification_sha256",
                "raw_output_root",
                "finalized_output_root",
                "finalizer_source_sha256",
                "finalizer_projection_source_sha256",
                "finalizer_selector_sha256",
                "finalizer_schema_sha256",
                "interpreter",
                "interpreter_sha256",
                "dependency_manifest_sha256",
                "dependency_tree_sha256",
                "evaluator_dependency_tree_sha256",
                "evaluator_contract_sha256",
            )
        }
        completion.update(
            {
                "schema_version": "1.0.0",
                "consumed_raw_manifest_sha256": request.raw_manifest_sha256,
                "consumed_raw_receipt_sha256": request.raw_receipt_sha256,
                "consumed_raw_completion_sha256": request.raw_completion_sha256,
                "consumed_process_outcome_sha256": request.process_outcome_sha256,
                "consumed_raw_artifact_binding_sha256": request.raw_artifact_binding_sha256,
                "semantic_projection_sha256": host.canonical_sha256(semantic),
                "session_sha256s": [sha(p.read_bytes()) for p in session_paths],
                "infrastructure_valid": valid,
            }
        )
        path = request.finalized_root / "shared-finalization-complete.json"
        encoded = canonical(completion)
        request.output_observer.allocate_controller_output_bytes(count=len(encoded))
        host.write_bytes_exclusive(path, encoded)
        return FinalizerExecutionOutcome(
            run_id=request.run_id,
            finalized_root=request.finalized_root,
            completion_receipt_path=path,
            completion_receipt_sha256=sha(path.read_bytes()),
            semantic_projection_sha256=host.canonical_sha256(semantic),
            session_paths=tuple(session_paths),
            consumed_raw_manifest_sha256=request.raw_manifest_sha256,
            consumed_raw_receipt_sha256=request.raw_receipt_sha256,
            consumed_raw_artifact_binding_sha256=request.raw_artifact_binding_sha256,
            infrastructure_valid=valid,
        )

    def evaluate_condition(self, request):
        from giclab.harness import t09_sira_pilot as pilot
        from giclab.harness.t09_qualification_fixture import DATASET_PATH, EVALUATOR_ROOT

        self.source_inputs.package_identity(self.repository)
        for artifact in request.finalized_artifacts:
            artifact.revalidate()
        result = pilot.evaluate_retained_session(
            pilot.EvaluatorIdentity(
                root=self.repository / EVALUATOR_ROOT,
                dataset_path=self.repository / DATASET_PATH,
                task_index=request.task_index,
                fixture_subset=True,
            ),
            list(request.session_paths),
        )
        retained = json.loads(
            (request.finalized_root / "retained/evaluator/output.json").read_bytes()
        )
        if result != retained:
            raise RuntimeError("shared evaluator differs from retained finalizer evaluation")
        source_outcome = json.loads(
            (request.finalized_root / "retained/attempt-outcome.json").read_bytes()
        )
        for artifact in request.finalized_artifacts:
            artifact.revalidate()
        value = EvaluatorExecutionOutcome(
            run_id=request.run_id,
            evaluator_run_id=request.evaluator_run_id,
            consumed_finalized_root=request.finalized_root,
            consumed_session_sha256s=tuple(sha(p.read_bytes()) for p in request.session_paths),
            consumed_finalized_artifact_binding_sha256=request.finalized_artifact_binding_sha256,
            evaluator_contract_sha256=request.evaluator_contract_sha256,
            evaluator_valid=result["evaluator_valid"],
            task_completed=result["task_completed"],
            answer_produced=result["answer_produced"],
            score=result["score"],
            infrastructure_failure=source_outcome["invalid_infrastructure_attempt"],
            missing_required_evidence=source_outcome["missing_evidence"],
            receipt_sha256="",
        )
        return replace(
            value, receipt_sha256=ProductionCategory3World._evaluator_outcome_identity(value)
        )

    def preserve_condition_failure(self, request):
        if request.execution.run_id not in self.retained_exports:
            self._export_retained_attempt(request.execution, request.output_observer)
        from giclab.control.production import _host_module

        return _host_module(self.repository).preserve_retained_condition_failure(
            request, clock=self._clock.wall_time
        )

    def export_condition_failure(self, request):
        from giclab.control.production import _host_module

        return _host_module(self.repository).export_retained_condition_failure_projection(
            request,
            transaction_root=self._root,
        )


def _export_condition_evidence(invocation, host, snapshot, fixture, environment_binding):
    """Bind only inputs/carrier paths; the retained consumers produce all receipts."""
    selected = invocation["postcondition_export"]
    if set(selected) != {"inbound", "restoration_root", "provider_entry", "run_id"}:
        raise RuntimeError("offline export input roles are ambiguous")
    transaction = Path(invocation["transaction_root"])
    inbound = Path(selected["inbound"])
    if (
        not inbound.is_relative_to(transaction / "retained-exports")
        or Path(selected["restoration_root"]) != transaction
        or not Path(selected["provider_entry"]).resolve().is_relative_to(transaction)
    ):
        raise RuntimeError("offline export carrier escaped its transaction")
    args = host.parser().parse_args(invocation["argv"])
    args._candidate_source_inputs = snapshot
    args._environment_binding = environment_binding
    args._qualification_fixture = fixture
    host._load_bridge_phase(args, "condition-session")
    if args.run_id != selected["run_id"]:
        raise RuntimeError("offline export switched condition identity")
    archive = inbound / (args.run_id + ".tar.gz")
    with archive.open("xb") as destination:
        result = host.export_attempt(
            args, host._BoundedArchiveWriter(destination, output_path=archive)
        )
        destination.flush()
        os.fsync(destination.fileno())
    if archive.stat().st_size != result["bytes"] or sha(archive.read_bytes()) != result["sha256"]:
        raise RuntimeError("local export carrier changed actual streamed bytes")

    def copy_bound(source, destination):
        metadata = source.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RuntimeError("offline carrier source is not one regular member")
        if metadata.st_size > host.MAX_ATTEMPT_EXPORT_BYTES:
            raise RuntimeError("offline carrier source exceeds retained cap")
        digest = sha(source.read_bytes())
        with source.open("rb") as stream:
            host._write_stream_exclusive_or_compare(
                stream=stream,
                destination=destination,
                expected_bytes=metadata.st_size,
                expected_sha256=digest,
            )

    completion = inbound / (args.run_id + "-export-completion.json")
    copy_bound(host._attempt_export_completion_path(args.artifact_root, args.run_id), completion)
    args.inbound_root = inbound
    args.attempt_export = archive
    args.attempt_export_completion = completion
    args.provider_entry_receipt = Path(selected["provider_entry"])
    args.restore_artifact_root = transaction
    args.restoration_commit = snapshot.document()["parent_head"]
    historical = SimpleNamespace(**vars(args))
    historical._candidate_source_inputs = None
    try:
        host.verify_attempt_export(historical)
    except host.T09HostError as exc:
        if str(exc) != "attempt export switched historical/candidate input selection":
            raise
    else:
        raise RuntimeError("historical export verifier accepted candidate evidence")
    host.verify_attempt_export(args)
    verification = inbound / (args.run_id + "-export-verification.json")
    delivery = inbound / "acknowledgement-delivery.json"
    copy_bound(verification, delivery)
    args.acknowledgement_file = delivery
    host.acknowledge_attempt_export(args)
    command = host.load_object(
        host._contract_paths_for(args.repository, host._argument_provider_contract(args))[
            "commands"
        ],
        label="export command manifest",
    )
    manifest = host._manifest_for_contract(
        command, args.run_id, host._argument_provider_contract(args)
    )
    attempt_relative = host.manifest_output_root(manifest)
    for name in (
        "condition-session-completion.json",
        "duplex-transcript-manifest.json",
        "condition-session-terminal-receipt.json",
    ):
        source = args.artifact_root / attempt_relative / name
        if source.exists():
            copy_bound(source, transaction / attempt_relative / name)
    host.write_exclusive(
        inbound / "offline-export-binding.json",
        {
            "classification": "offline-candidate-carrier-binding-not-live-qualification",
            "candidate_binding_sha256": snapshot.digest,
            "environment_binding_sha256": environment_binding.digest,
            "qualification_fixture": fixture.document(),
            "archive_sha256": result["sha256"],
            "completion_sha256": sha(completion.read_bytes()),
            "verification_sha256": sha(verification.read_bytes()),
            "historical_replay": "not-run",
            "scientific_result": False,
        },
    )


def _run_condition_runtime(invocation, snapshot, package, environment_root):
    """Execute the retained runtime in a fresh process over explicit fake leaves."""
    from types import ModuleType

    from giclab.harness import sira_gate_a_runtime as runtime
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT as contract

    entry = invocation["runtime_command"]
    if entry["run_id"] not in contract.run_ids or entry["role"] != "condition":
        raise RuntimeError("runtime leaf input changed condition identity")
    fixture_relative = "tests/fixtures/t09/offline-condition-runner.py"
    fixture = package / fixture_relative
    snapshot.source_sha256(package, fixture_relative)
    snapshot.source_sha256(snapshot.root, "src/giclab/harness/sira_gate_a_runtime.py")
    mounts = {key: Path(value["source"]) for key, value in entry["mounts"].items()}
    attempt = mounts["/giclab/attempt"]
    upstream = entry["command"][5:]
    if upstream[:6] != [
        "/usr/bin/timeout",
        "--signal=TERM",
        "--kill-after=30s",
        "3600s",
        "/opt/sira/.venv/bin/python",
        "/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py",
    ]:
        raise RuntimeError("runtime leaf changed retained instrumentation entrypoint")
    runtime_argv = upstream[6:]
    runner_index = runtime_argv.index("--gate-upstream-runner") + 1
    mounts[runtime_argv[runner_index]] = fixture
    for logical, name in (("/tmp", "tmp"), ("/dev/shm", "shm")):
        target = environment_root / name
        target.mkdir(mode=0o700, exist_ok=True)
        mounts[logical] = target

    class MountedPath(type(Path())):
        def __new__(cls, *parts):
            value = Path(*parts)
            for logical in sorted(mounts, key=len, reverse=True):
                base = Path(logical)
                if value == base or value.is_relative_to(base):
                    value = mounts[logical] / value.relative_to(base)
                    break
            return super().__new__(cls, value)

    # This is the explicitly simulated container mount lookup, not a verifier
    # replacement. Logical argv/hashes remain unchanged for the real checks.
    runtime.Path = MountedPath
    # The retained timing validator captures its environmental clock when the
    # module imports. Both processes use the same bound wall/monotonic origin;
    # its future-origin rejection and timing arithmetic remain unchanged.
    origins = runtime.pilot_state_time_origins
    origins.__kwdefaults__ = {
        **origins.__kwdefaults__,
        "wall_time": time.time,
        "monotonic": time.monotonic,
    }
    runtime_io = None
    restore_runtime_io = None
    original_port_builder = runtime.build_private_socket_supervisor_port

    def instrument_port(**kwargs):
        nonlocal runtime_io, restore_runtime_io
        port = original_port_builder(**kwargs)
        if invocation["fault_operation"] == "transaction-io-continuation":
            runtime_io, restore_runtime_io = instrument_bound_io(
                port.endpoint.reader.fileno(),
                port.endpoint.writer.fileno(),
                inject_continuations=True,
            )
        if invocation["fault_operation"] == "matrix-runtime-halfclose":
            original_event = port._write_event

            def halfclose_after_send_start(**kwargs):
                value = original_event(**kwargs)
                if kwargs["event_type"] == "model-send-start":
                    channels = [
                        item for item in port._closeables if isinstance(item, socket.socket)
                    ]
                    assert len(channels) == 1
                    channels[0].shutdown(socket.SHUT_WR)
                    raise ConnectionError("bound runtime half-close after possible send")
                return value

            port._write_event = halfclose_after_send_start
        return port

    runtime.build_private_socket_supervisor_port = instrument_port
    condition_mode = runtime_argv[runtime_argv.index("--gate-mode") + 1]
    upstream_boundary = runtime_argv.index("--")
    task_argv = runtime_argv[upstream_boundary + 1 :]
    output = MountedPath(task_argv[task_argv.index("--output_dir") + 1])
    tasks = json.loads((package / "tests/fixtures/t09/fanout-two-task-fixture.json").read_bytes())
    ordinal = contract.run_ids.index(entry["run_id"])
    fault = invocation["fault_operation"]
    if fault not in (
        None,
        "condition.no-answer",
        "condition.partial-failure",
        "cleanup.admission-disconnect",
        "cleanup.descendant-interruption",
        "condition.attach-output-denial",
        "export.output-denial",
        "matrix-raw-export-hook",
        "matrix-finalizer-hook",
        "matrix-evaluator-hook",
        "matrix-checkpoint-hook",
        "matrix-terminal-answer",
        "matrix-terminal-status",
        "matrix-raw-reference",
        "matrix-cross-session-journal",
        "matrix-finalizer-reference",
        "matrix-evaluator-mutation",
        "matrix-selected-reference",
        "transaction-io-continuation",
        "matrix-model-send-loss",
        "matrix-runtime-halfclose",
        "matrix-terminal-ack",
    ):
        raise RuntimeError("unbound runtime fixture scenario")
    selected = ModuleType("giclab_offline_condition_inputs")
    selected.inputs = SimpleNamespace(
        mode=condition_mode,
        output=output,
        goal=tasks[0 if ordinal < 2 else 1]["question"],
        process_failure=fault
        in {
            "condition.partial-failure",
            "cleanup.admission-disconnect",
            "cleanup.descendant-interruption",
        },
        attach_output_blocks=65 if fault == "condition.attach-output-denial" else 0,
    )
    sys.modules[selected.__name__] = selected
    answer = "No relevant answer." if ordinal % 2 == 0 else "Unrelated fixture answer."
    action = "noop()" if fault == "condition.no-answer" else f"send_msg_to_user('{answer}')"
    response_count = 0

    class UpstreamLLM:
        def __init__(self, **kwargs):
            if (
                kwargs["model"] != "gpt-4o-2024-11-20"
                or kwargs["num_retries"] != 0
                or kwargs["custom_llm_provider"] != "openai"
            ):
                raise RuntimeError("fixture model request violated locked routing")
            self.model_name = kwargs["model"]
            self.max_output_tokens = 64
            self._completion = self.complete

        def get_token_count(self, messages):
            if messages != [{"role": "user", "content": "offline fixture observation"}]:
                raise RuntimeError("unbound fixture model input")
            return 9

        def complete(self, **kwargs):
            nonlocal response_count
            if kwargs.get("service_tier") != "default" or kwargs.get("max_completion_tokens") != 64:
                raise RuntimeError("fixture request policy drifted")
            response_count += 1
            if fault == "matrix-model-send-loss":
                raise ConnectionError("bound response lost after one actual fixture send")
            return {
                "id": f"offline-response-{response_count}",
                "service_tier": "default",
                "choices": [{"message": {"content": action}}],
                "usage": {
                    "prompt_tokens": 9,
                    "completion_tokens": 9,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }

    llm = ModuleType("sira.web.utils.llm")
    llm.LLM = UpstreamLLM
    sys.modules[llm.__name__] = llm
    logger = ModuleType("sira.web.utils.logger")
    logger.get_agent_logger = lambda **kwargs: SimpleNamespace(info=lambda *args: None)
    sys.modules[logger.__name__] = logger
    source = package / "containers/sira-smoke/container_entrypoint.py"
    spec = importlib.util.spec_from_file_location("offline_condition_entrypoint", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ATTEMPT_ROOT = attempt
    module.READY_PATH = attempt / ".giclab-entrypoint-ready"
    module.RELEASE_PATH = attempt / ".giclab-release"
    module.read_secret_file.__defaults__ = (mounts["/run/secrets/sira_api_key"],)

    def exec_runtime(executable, argv, environment):
        if executable != upstream[0] or list(argv) != upstream:
            raise RuntimeError("entrypoint attempted an unbound process replacement")
        if "OPENAI_API_KEY" in environment or not environment.get("SIRA_API_KEY"):
            raise RuntimeError("entrypoint failed its retained credential mapping")
        os.environ["SIRA_API_KEY"] = environment["SIRA_API_KEY"]
        result = runtime.run(runtime_argv)
        expected_responses = (
            1
            if fault == "matrix-model-send-loss"
            else 0
            if fault == "matrix-runtime-halfclose"
            else 2
        )
        if response_count != expected_responses:
            raise RuntimeError("retained runtime fixture effect count differs")
        raise SystemExit(result)

    module.os = SimpleNamespace(
        **{name: getattr(os, name) for name in dir(os) if name != "execvpe"}, execvpe=exec_runtime
    )
    # Observe the real census without replacing its result. The second bounded
    # read is labelled stable only if its member sum equals the actual consumer;
    # it is diagnostic evidence, never an output-admission oracle.
    census_records = []
    retained_tree_bytes = runtime.ResourceGuard._tree_bytes

    def observe_tree_bytes(root):
        total = retained_tree_bytes(root)
        if root == attempt:
            members = []
            for directory, _, names in os.walk(root):
                for name in sorted(names):
                    path = Path(directory) / name
                    metadata = path.lstat()
                    if stat.S_ISREG(metadata.st_mode):
                        members.append(
                            {"path": str(path.relative_to(root)), "bytes": metadata.st_size}
                        )
                    if len(members) > 4096:
                        raise RuntimeError("output census diagnostic exceeded its member cap")
            census_records.append(
                {
                    "consumer_bytes": total,
                    "observed_member_bytes": sum(item["bytes"] for item in members),
                    "stable_sum": total == sum(item["bytes"] for item in members),
                    "members": members,
                }
            )
            if len(census_records) > 32:
                raise RuntimeError("output census diagnostic exceeded its observation cap")
        return total

    runtime.ResourceGuard._tree_bytes = staticmethod(observe_tree_bytes)
    # Only exec replacement is modeled. Entry/release/credential parsing, actual
    # runtime.run, its LLM factory, admission, writers and teardown all execute.
    try:
        module.run(entry["command"][1:])
    finally:
        if restore_runtime_io is not None:
            restore_runtime_io()
        runtime.ResourceGuard._tree_bytes = staticmethod(retained_tree_bytes)
        diagnostic = {
            "schema_version": "1.0.0",
            "classification": "offline-read-only-census-diagnostic",
            "candidate_binding_sha256": snapshot.digest,
            "run_id": entry["run_id"],
            "runtime_io": runtime_io,
            "actual_model_response_count": response_count,
            "runtime_process_id": os.getpid(),  # Private diagnostic; publish only distinct count.
            "executed_runtime_source_sha256": sha(Path(runtime.__file__).read_bytes()),
            "observations": census_records,
            "consumer_result_modified": False,
            "admission_proof": False,
        }
        if len(canonical(diagnostic)) > 131072:
            raise RuntimeError("output census diagnostic exceeded its byte cap")
        write(environment_root / f"output-census-{entry['run_id']}.json", diagnostic)


def _duplicate_tracked_descriptor(fd, *, native_dup, native_close, directories):
    """Carry an existing held-directory identity across the actual dup primitive."""
    metadata = os.fstat(fd)
    retained = directories.get(fd)
    directory = stat.S_ISDIR(metadata.st_mode)
    identity = (metadata.st_dev, metadata.st_ino)
    if directory and (retained is None or retained[1] != identity):
        raise RuntimeError("offline dup used an unbound directory descriptor")
    duplicate = native_dup(fd)
    current = os.fstat(duplicate)
    if (current.st_dev, current.st_ino) != identity:
        native_close(duplicate)
        raise RuntimeError("offline dup descriptor identity changed")
    if directory:
        directories[duplicate] = retained
    return duplicate


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--invocation":
        path = Path(sys.argv[2])
        if path.is_symlink() or not path.is_absolute() or path.stat().st_size > 32768:
            raise RuntimeError("offline invocation input is unsafe")
        invocation = json.loads(path.read_bytes())
    else:
        invocation = json.loads(sys.stdin.buffer.read(32768))
    cleanup = invocation.get("cleanup_output")
    if invocation["phase"] == "host-cleanup":
        if not isinstance(cleanup, dict) or set(cleanup) != {
            "binding",
            "read_descriptor",
            "write_descriptor",
            "deadline",
        }:
            raise RuntimeError("cleanup child requires explicit campaign output authority")
        binding = CleanupOutputBinding.from_document(cleanup["binding"])
        if (
            binding.candidate_sha256 != invocation["binding_sha256"]
            or binding.transaction_root != invocation["transaction_root"]
        ):
            raise RuntimeError("cleanup child source/root capability mismatch")
        channel = CleanupOutputChannel(
            cleanup["read_descriptor"],
            binding,
            cleanup["deadline"],
            write_fd=cleanup["write_descriptor"],
        )
        try:
            channel.connect()
            with campaign_output_scope(channel.admit):
                _main(invocation)
            channel.finish()
        finally:
            os.close(cleanup["read_descriptor"])
            os.close(cleanup["write_descriptor"])
        return
    if cleanup is not None:
        raise RuntimeError("cleanup capability supplied to another phase")
    _main(invocation)


def _main(invocation):
    phase_wall = float(invocation["wall"]) + 0.125
    condition_clock = None
    if invocation["phase"] == "condition-session":
        condition_clock = invocation.get("condition_clock") or {
            "wall": phase_wall,
            "monotonic": time.monotonic(),
        }
        if set(condition_clock) != {"wall", "monotonic"}:
            raise RuntimeError("condition clock binding is ambiguous")
        time.time = lambda: (
            condition_clock["wall"] + time.monotonic() - condition_clock["monotonic"]
        )
    else:
        time.time = lambda: phase_wall
    # These retained entry points expose the environmental clock as a
    # keyword dependency. Replace only that default in this private worker.
    # All journal validation, transitions, publication and fsync still execute.
    for name in (
        "initialize",
        "advance_lifecycle",
        "advance_lifecycle_at_least",
        "register_target",
        "record_result",
        "begin_freeze_publication",
        "abort_unpublished_freeze",
        "cleanup",
    ):
        method = getattr(EarlyCleanupJournal, name)
        function = getattr(method, "__func__", method)
        defaults = function.__kwdefaults__
        assert defaults is not None and "clock" in defaults
        function.__kwdefaults__ = {**defaults, "clock": time.time}
    parent = Path(invocation["parent_repository"])
    source_root = Path(invocation["snapshot"]) / "source"
    package = Path(invocation["package"])
    transaction = Path(invocation["transaction_root"])
    environment_root = (
        transaction
        / "fixture-process-environment"
        / invocation.get("instance", invocation["phase"])
    )
    environment_root.mkdir(mode=0o700, parents=True)
    for name, variable in (("home", "HOME"), ("nltk-data", "NLTK_DATA"), ("tmp", "TMPDIR")):
        directory = environment_root / name
        directory.mkdir(mode=0o700)
        os.environ[variable] = str(directory)
    tempfile.tempdir = os.environ["TMPDIR"]
    native_run = subprocess.run
    admitted_archive_command = None
    admitted_probe_command = None
    native_open, native_close, native_dup = os.open, os.close, os.dup
    directory_handles = {}
    open_context = threading.local()

    def descriptor_open(path, flags, mode=0o777, *, dir_fd=None):
        """Resolve retained no-follow openat calls through their held directory.

        CPython's open audit event omits dir_fd. The wrapper supplies only the
        path corresponding to a directory descriptor opened in this worker,
        after verifying that descriptor still has the exact recorded inode.
        """
        value = Path(os.fsdecode(path))
        if dir_fd is not None and not value.is_absolute():
            retained = directory_handles.get(dir_fd)
            if retained is None:
                raise RuntimeError("offline openat used an unbound directory descriptor")
            base, identity = retained
            metadata = os.fstat(dir_fd)
            if (metadata.st_dev, metadata.st_ino) != identity or value.name != str(value):
                raise RuntimeError("offline openat descriptor/path identity drifted")
            resolved = base / value
        else:
            resolved = value.resolve(strict=False)
        previous = getattr(open_context, "path", None)
        open_context.path = resolved
        try:
            fd = native_open(path, flags, mode, dir_fd=dir_fd)
        finally:
            open_context.path = previous
        metadata = os.fstat(fd)
        if stat.S_ISDIR(metadata.st_mode):
            directory_handles[fd] = (resolved, (metadata.st_dev, metadata.st_ino))
        return fd

    def descriptor_close(fd):
        directory_handles.pop(fd, None)
        return native_close(fd)

    def guard(event, args):
        if (
            event in {"socket.connect", "socket.bind"}
            and invocation["phase"] == "condition-session"
        ):
            channel, address = args
            if channel.family == socket.AF_UNIX and Path(
                os.fsdecode(address)
            ).resolve().is_relative_to(transaction):
                return
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "os.system"}:
            raise RuntimeError("retained offline phase denied network/system effect")
        if event == "subprocess.Popen":
            argv = args[1]
            if admitted_archive_command is not None and argv == admitted_archive_command:
                return
            if admitted_probe_command is not None and argv == admitted_probe_command:
                return
            if (
                invocation["phase"] == "condition-session"
                and "runtime_command" not in invocation
                and isinstance(argv, list)
                and len(argv) == 5
                and argv[:4] == [sys.executable, "-B", str(source_root / RELATIVE), "--invocation"]
                and Path(argv[4]).parent == transaction / "runtime-inputs"
                and not Path(argv[4]).is_symlink()
            ):
                return
            if (
                not isinstance(argv, list)
                or argv[:3] != ["git", "-C", str(parent)]
                or argv[3] not in {"show", "rev-parse", "merge-base"}
            ):
                raise RuntimeError("retained offline phase denied external process")
        if event == "open" and isinstance(args[0], (str, bytes)):
            if args[2] & os.O_DIRECTORY:
                return
            path = getattr(open_context, "path", None)
            if path is None:
                path = Path(os.fsdecode(args[0])).resolve()
            guard_entry = Path(os.environ["GICLAB_CI_GUARD_JOURNAL"]) / f"{os.getpid()}.jsonl"
            if path == guard_entry:
                # The precollection guard must retain a denial even when this
                # narrower phase guard rejects the initiating operation.
                return
            roots = (
                source_root,
                package,
                transaction,
                Path(invocation["snapshot"]),
                Path(sys.prefix),
                Path(sys.base_prefix),
            )
            if path != Path("/dev/null") and not any(path.is_relative_to(p) for p in roots):
                raise RuntimeError("retained offline phase denied unbound file")
            if (
                args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
                and path != Path("/dev/null")
                and not path.is_relative_to(transaction)
            ):
                raise RuntimeError("retained offline phase denied nontransaction write")

    def descriptor_dup(fd):
        return _duplicate_tracked_descriptor(
            fd, native_dup=native_dup, native_close=native_close, directories=directory_handles
        )

    os.open, os.close, os.dup = descriptor_open, descriptor_close, descriptor_dup
    sys.addaudithook(guard)
    snapshot = load_candidate_source_snapshot(
        Path(invocation["snapshot"]),
        expected_binding_sha256=invocation["binding_sha256"],
        parent_repository=parent,
        expected_parent_head=invocation["parent_head"],
        expected_parent_tree=invocation["parent_tree"],
    )
    validate_candidate_package(snapshot, package)
    for name, module in tuple(sys.modules.items()):
        if name == "giclab" or name.startswith("giclab."):
            path = getattr(module, "__file__", None)
            if path:
                snapshot.source_sha256(source_root, Path(path).relative_to(source_root).as_posix())
    path = package / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    spec = importlib.util.spec_from_file_location("retained_candidate_host", path)
    host = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = host
    spec.loader.exec_module(host)
    observations = []
    original_builtin_open = builtins.open

    def environment_open(file, *args, **kwargs):
        if (
            isinstance(file, (str, Path))
            and str(file) == "/System/Library/CoreServices/SystemVersion.plist"
        ):
            observations.append(["fixture-macos-version"])
            return io.StringIO(
                "<plist><dict><key>ProductUserVisibleVersion</key><string>13.0.0</string></dict></plist>"
            )
        return original_builtin_open(file, *args, **kwargs)

    builtins.open = environment_open
    environment_binding = None
    image_channel = None
    if invocation.get("environment_root") is not None:
        from giclab.harness.t09_environment_fixture import load_environment_fixture

        environment_binding = load_environment_fixture(
            Path(invocation["environment_root"]),
            expected_sha256=invocation["environment_sha256"],
            source=snapshot,
            package=package,
        )
        contract = host._argument_provider_contract(host.parser().parse_args(invocation["argv"]))
        image_channel = ImageCommandChannel(
            environment_binding,
            tag=contract.replacement_image_tag,
            transaction_root=transaction,
            package=package,
            source_inputs=snapshot,
            contract=contract,
        )

    daemon_state = transaction / "retained-phase-traces/offline-environment-state.json"
    if image_channel is not None and "runtime_command" not in invocation:
        image_channel.load_state(daemon_state)

    def environmental_run(argv, **kwargs):
        nonlocal admitted_archive_command, admitted_probe_command
        if "postcondition_finalizer" in invocation:
            phase_args = host.parser().parse_args(invocation["argv"])
            qualification = host.load_object(
                host._pilot_root(phase_args.artifact_root) / "local-finalizer-qualification.json",
                label="bound finalizer local runtime",
            )
            expected_probes = [
                host.local_dependency_probe_argv(Path(qualification["interpreter"]), site)
                for site in (None, Path(qualification["dependency_site_packages"]))
            ]
            if argv in expected_probes:
                if argv[0] != sys.executable:
                    raise RuntimeError("offline finalizer probe changed interpreter")
                # Only these exact read-only metadata scripts may use this leaf
                # channel. -I suppresses the required child guard, so execute
                # the same script/interpreter against the same explicit package
                # tree in a guarded child. No candidate workload or arbitrary
                # command is admitted by this environmental substitution.
                guarded_probe = [argv[0], "-B", *argv[2:]]
                if argv == expected_probes[0]:
                    # Qualification explicitly selected generated dist-info
                    # inputs, not the CI tool environment. Supply that same
                    # sysconfig observation; the unchanged metadata script
                    # enumerates its actual files and the retained validator
                    # still compares the full package and byte inventories.
                    metadata_root = Path(qualification["interpreter_site_packages"])
                    if (
                        metadata_root.is_symlink()
                        or metadata_root
                        != Path(invocation["snapshot"]) / "qualification/fake-base-packages"
                    ):
                        raise RuntimeError("offline metadata probe lost its declared source root")
                    guarded_probe = [
                        argv[0],
                        "-B",
                        "-c",
                        "import sys,sysconfig;"
                        "_paths=sysconfig.get_paths();"
                        "sysconfig.get_paths=lambda:{**_paths,'purelib':sys.argv[1]};" + argv[3],
                        str(metadata_root),
                    ]
                observations.append(
                    {
                        "role": "guarded-dependency-probe",
                        "environment": "explicit-synthetic-installed-metadata",
                        "requested": argv,
                        "executed": guarded_probe,
                    }
                )
                admitted_probe_command = guarded_probe
                try:
                    return native_run(guarded_probe, **kwargs)
                finally:
                    admitted_probe_command = None
        if "postcondition_finalizer" in invocation and argv[:2] == [
            sys.executable,
            str(package / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"),
        ]:
            child = {
                **invocation,
                "instance": invocation["instance"] + "-worker",
                "finalizer_command": argv[2:],
            }
            child.pop("postcondition_finalizer")
            child_path = write(
                transaction / "runtime-inputs" / (child["instance"] + ".json"), child
            )
            child_environment = dict(kwargs["env"])
            original_pythonpath = child_environment["PYTHONPATH"]
            suffix = ":" + str(package / "src")
            if not original_pythonpath.endswith(suffix):
                raise RuntimeError("finalizer source import mapping differs")
            child_environment["PYTHONPATH"] = (
                original_pythonpath[: -len(suffix)] + ":" + str(source_root / "src")
            )
            return native_run(
                [
                    sys.executable,
                    "-B",
                    str(source_root / RELATIVE),
                    "--invocation",
                    str(child_path),
                ],
                **{**kwargs, "env": child_environment},
            )
        if image_channel is not None and (
            argv[:1] == ["docker"]
            and argv[1:2]
            in (
                ["image"],
                ["load"],
                ["tag"],
                ["ps"],
                ["create"],
                ["inspect"],
                ["start"],
                ["wait"],
                ["stop"],
                ["kill"],
                ["rm"],
            )
        ):
            try:
                return image_channel.run(argv, **kwargs)
            finally:
                image_channel.save_state(daemon_state)
        if argv[:5] == ["git", "-C", str(package), "archive", "--format=tar"]:
            inventory_path = "tests/fixtures/t09/offline-candidate-historical-build-inputs.json"
            snapshot.source_sha256(source_root, inventory_path)
            inventory = json.loads((source_root / inventory_path).read_bytes())
            selected = host._argument_provider_contract(
                host.parser().parse_args(invocation["argv"])
            )
            artifact_root = host.parser().parse_args(invocation["argv"]).artifact_root
            target = (
                artifact_root
                / selected.control_root_name
                / "replacement-image-qualification/work/t07-source.tar"
            )
            expected = [
                "git",
                "-C",
                str(package),
                "archive",
                "--format=tar",
                f"--output={target}",
                host.T07_EXECUTION_COMMIT,
                *inventory["archive_paths"],
            ]
            if (
                argv != expected
                or inventory["source_commit"] != host.T07_EXECUTION_COMMIT
                or sha(canonical(inventory["members"])) != inventory["member_manifest_sha256"]
                or target.exists()
                or target.is_symlink()
                or not target.parent.resolve(strict=True).is_relative_to(transaction)
            ):
                raise RuntimeError("historical source archive input/target differs from binding")
            admitted_archive_command = ["git", "-C", str(parent), *argv[3:]]
            try:
                result = native_run(admitted_archive_command, **kwargs)
            finally:
                admitted_archive_command = None
            if (
                result.returncode
                or not 0 < target.stat().st_size <= inventory["archive_byte_limit"]
            ):
                raise RuntimeError("historical source archive generation failed its finite cap")
            observed = []
            with tarfile.open(target, "r:") as archive:
                for member in archive.getmembers():
                    if member.isdir():
                        continue
                    if (
                        not member.isfile()
                        or not 0 < member.size <= inventory["decoded_byte_limit"]
                    ):
                        raise RuntimeError("historical build input archive member is unsafe")
                    stream = archive.extractfile(member)
                    assert stream is not None
                    data = stream.read(member.size + 1)
                    if len(data) != member.size:
                        raise RuntimeError("historical build input archive member size drifted")
                    observed.append({"path": member.name, "bytes": len(data), "sha256": sha(data)})
            expected_members = [
                {k: v for k, v in member.items() if k != "git_blob"}
                for member in inventory["members"]
            ]
            if observed != expected_members:
                raise RuntimeError("historical build source archive differs from exact inventory")
            observations.append(["git-archive-historical-inputs", sha(target.read_bytes())])
            return result
        if (
            invocation["phase"] == "host-preflight"
            and invocation["fault_operation"] == "host.preflight"
            and argv in (["docker", "info"], ["sudo", "-n", "docker", "info"])
        ):
            observations.append(list(argv))
            return subprocess.CompletedProcess(argv, 1, stdout=b"", stderr=b"")
        selected_contract = host._argument_provider_contract(
            host.parser().parse_args(invocation["argv"])
        )
        if argv in (
            ["docker", "image", "inspect", "--format", "{{.Id}}", identity]
            for identity in (selected_contract.replacement_image_tag, host.RETAINED_IMAGE_ID)
        ):
            observations.append(list(argv))
            return subprocess.CompletedProcess(argv, 1, stdout=b"", stderr=b"")
        if argv == [
            "nvidia-smi",
            "--query-gpu=name,driver_version,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]:
            observations.append(list(argv))
            return subprocess.CompletedProcess(argv, 1, stdout=b"", stderr=b"")
        if argv == ["docker", "info"] and image_channel is not None:
            observations.append(list(argv))
            return image_channel.run(argv, **kwargs)
        return native_run(argv, **kwargs)

    native_popen = subprocess.Popen

    def environmental_popen(argv, **kwargs):
        if isinstance(argv, list) and argv[:3] == ["docker", "start", "--attach"]:
            if image_channel is None:
                raise RuntimeError("condition process lacks environment binding")
            return image_channel.start_condition_process(argv, **kwargs)
        if isinstance(argv, list) and argv[:2] == ["docker", "run"]:
            if image_channel is None:
                raise RuntimeError("container command lacks explicit environment binding")
            try:
                return image_channel.popen(argv, **kwargs)
            finally:
                image_channel.save_state(daemon_state)
        return native_popen(argv, **kwargs)

    def launch_condition(entry, **kwargs):
        runtime_invocation = {
            **invocation,
            "instance": invocation["instance"] + "-runtime",
            "runtime_command": entry,
            "condition_clock": condition_clock,
        }
        input_path = write(
            transaction / "runtime-inputs" / (entry["run_id"] + ".json"), runtime_invocation
        )
        return native_popen(
            [sys.executable, "-B", str(source_root / RELATIVE), "--invocation", str(input_path)],
            stdin=subprocess.DEVNULL,
            stdout=kwargs["stdout"],
            stderr=kwargs["stderr"],
            env={
                "PATH": os.defpath,
                "PYTHONPATH": str(source_root / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
            },
        )

    if image_channel is not None:
        image_channel.condition_launch = launch_condition
        if invocation["phase"] == "condition-session":
            image_channel.condition_context = host.parser().parse_args(invocation["argv"])
    subprocess.Popen = environmental_popen
    subprocess.run = environmental_run
    clock_events = []

    def freeze_sleep(seconds):
        nonlocal phase_wall
        if (
            invocation["phase"] != "host-freeze"
            or clock_events
            or not isinstance(seconds, (int, float))
            or not 0 <= seconds <= 120
        ):
            raise RuntimeError("offline phase attempted an undeclared wait")
        clock_events.append({"operation": "sleep", "seconds": seconds})
        phase_wall += seconds

    host.time = SimpleNamespace(
        time=lambda: phase_wall,
        monotonic=lambda: (
            invocation["monotonic"] + 0.125 + sum(event["seconds"] for event in clock_events)
        ),
        sleep=freeze_sleep,
    )
    if invocation["phase"] == "condition-session":
        # Duration measurement/IPC deadlines use the actual local monotonic epoch.
        # Only the simulated campaign wall origin differs from the host clock.
        host.time = SimpleNamespace(
            time=time.time,
            monotonic=time.monotonic,
            sleep=time.sleep,
        )
    sys.argv = [str(path), *invocation["argv"]]
    fixture = None
    if invocation["phase"] in {"host-qualify", "host-freeze", "condition-session"} or (
        invocation["phase"] == "host-cleanup" and (transaction / "qualification-archive").exists()
    ):
        from giclab.harness.t09_qualification_fixture import (
            build_deterministic_qualification_archive,
            load_deterministic_qualification_archive,
        )

        directory = transaction / "qualification-archive"
        if invocation["phase"] == "host-qualify":
            directory.mkdir(mode=0o700)
            fixture = build_deterministic_qualification_archive(package, directory)
        else:
            fixture = load_deterministic_qualification_archive(
                package, directory / "offline-qualification-fixture.tar.gz"
            )
        if fixture.document() != snapshot.document()["qualification_fixture"]:
            raise RuntimeError("retained phase switched its qualification archive binding")
        if image_channel is not None:
            image_channel.qualification_binding = fixture
        if invocation["phase"] == "host-qualify":
            sys.argv += ["--real-evidence-archive", str(fixture.archive_path)]
    watched = {
        "verify_package",
        "stage_verified_archive",
        "host_transfer_verify",
        "host_preflight",
        "_live_host_preflight",
        "host_qualify",
        "_live_host_qualification",
        "materialize_retained_or_build_image",
        "secret_channel_preflight",
        "evaluator_overlay",
        "validate_evaluator_overlay_binding",
        "final_image_file_hashes",
        "final_image_runtime_preflight",
        "provider_accounting_container_preflight",
        "offline_runtime_preflight",
        "qualified_real_evidence_regression",
        "core_suppression_preflight",
        "browser_lifecycle_preflight",
        "sealing_primitives_preflight",
        "publish_sealing_probe_selection",
        "image_equivalence_adjudication",
        "host_freeze",
        "_live_host_freeze",
        "condition_session",
        "execute_condition",
        "retained_condition_completion",
        "finalize_attempt",
        "finalize",
        "validate_finalizer_source",
        "validate_local_finalizer_qualification",
        "local_evaluator_invocation",
        "validate_finalized_attempt",
        "validate_selected_finalization",
        "evaluate_retained_session",
        "export_attempt",
        "verify_attempt_export",
        "restore_verified_attempt_export",
        "acknowledge_attempt_export",
        "require_attempt_export_acknowledgement",
        "host_cleanup",
        "_live_host_cleanup",
        "cleanup",
        "run",
        "validate_host_phase_predecessor",
        "validate_host_qualification_phase",
        "validate_host_cleanup_phase",
    }
    source_hashes = {
        member["path"]: member["sha256"] for member in snapshot.document()["source_members"]
    }
    calls = []
    resource_observations = []

    def profile(frame, event, _arg):
        if (
            event == "return"
            and "runtime_command" in invocation
            and frame.f_code.co_name == "snapshot"
            and frame.f_code.co_filename
            == str(source_root / "src/giclab/harness/t09_sira_pilot.py")
        ):
            guard = frame.f_locals["self"]
            members = []
            for directory, _, names in os.walk(guard.attempt_root):
                for name in names:
                    path = Path(directory) / name
                    metadata = path.lstat()
                    if not path.is_symlink():
                        members.append(
                            {
                                "path": path.relative_to(guard.attempt_root).as_posix(),
                                "bytes": metadata.st_size,
                            }
                        )
                    if len(members) > 4096:
                        raise RuntimeError("runtime census diagnostic exceeded its member cap")
            if len(resource_observations) >= 128:
                raise RuntimeError("runtime census diagnostic exceeded its observation cap")
            resource_observations.append(
                {
                    "attempt_output_bytes": _arg.attempt_output_bytes,
                    "members": sorted(members, key=lambda item: item["path"]),
                    "classification": "test-observation-after-actual-census",
                }
            )
        if event != "call" or frame.f_code.co_name not in watched:
            return
        filename = frame.f_code.co_filename
        relative = None
        for base in (str(package) + "/", str(source_root) + "/"):
            if filename.startswith(base):
                relative = filename[len(base) :]
                break
        if relative not in source_hashes:
            return
        if len(calls) >= 4096:
            raise RuntimeError("retained call trace exceeded its finite cap")
        calls.append(
            {
                "sequence": len(calls) + 1,
                "source": relative,
                "source_sha256": source_hashes[relative],
                "function": frame.f_code.co_name,
            }
        )

    matrix_fault = invocation.get("fault_operation")
    hooks = {
        "matrix-transfer-verify-hook": ("host-transfer-verify", "host_transfer_verify"),
        "matrix-preflight-hook": ("host-preflight", "host_preflight"),
        "matrix-qualification-hook": ("host-qualify", "host_qualify"),
        "matrix-runtime-hook": ("condition-session", "condition_session"),
        "matrix-raw-export-hook": ("retained-attempt-export", "export_attempt"),
        "matrix-finalizer-hook": ("condition-finalizer", "finalize_attempt"),
        "matrix-cleanup-terminal-hook": ("host-cleanup", "_publish_bridge_phase"),
    }
    selected_hook = hooks.get(matrix_fault)
    # Finalizer/export subcommands retain their own invocation phase names.
    active = selected_hook is not None and (
        invocation["phase"] == selected_hook[0]
        or (matrix_fault == "matrix-finalizer-hook" and "postcondition_finalizer" in invocation)
        or (matrix_fault == "matrix-raw-export-hook" and "postcondition_export" in invocation)
    )
    if active:

        def missing_retained_hook(*args, **kwargs):
            raise RuntimeError("matrix required retained hook withheld: " + selected_hook[1])

        setattr(host, selected_hook[1], missing_retained_hook)
    if matrix_fault == "matrix-freeze-unpublished" and invocation["phase"] == "host-freeze":
        original_open = host.os.open

        def fail_frozen_publication(path, flags, *args, **kwargs):
            if (
                Path(path).name == ".frozen-run-manifest.json.giclab-publication.tmp"
                and flags & os.O_CREAT
            ):
                raise OSError("matrix freeze publication withheld after durable begin")
            return original_open(path, flags, *args, **kwargs)

        host.os.open = fail_frozen_publication

    if invocation["phase"] == "condition-session" and matrix_fault in {
        "matrix-ipc-neverread",
        "matrix-ipc-midframe",
    }:
        if matrix_fault == "matrix-ipc-midframe":
            prefix = os.read(0, 4096)
            if len(prefix) != 4096:
                raise RuntimeError("bound carrier prefix was short")
        time.sleep(120)  # Owner terminates/reaps this exact child inside 15 seconds.
        raise RuntimeError("bound carrier stall unexpectedly returned")

    sys.setprofile(profile)
    try:
        if "postcondition_finalizer" in invocation:
            selected = invocation["postcondition_finalizer"]
            args = host.parser().parse_args(invocation["argv"])
            args._candidate_source_inputs = snapshot
            args._environment_binding = environment_binding
            args._qualification_fixture = fixture
            args.finalizer_commit = snapshot.document()["parent_head"]
            args.finalizer_source = package / host.FINALIZER_RELATIVE_PATH
            args.finalizer_projection_source = package / host.FINALIZER_PROJECTION_RELATIVE_PATH
            args.finalizer_execution_mode = "qualified-local"
            args.local_finalizer_qualification = (
                args.artifact_root
                / host._contract_control_root_name(host._argument_provider_contract(args))
                / "local-finalizer-qualification.json"
            )
            args.local_evaluator_root, args.local_dataset = (
                Path(selected["evaluator_root"]),
                Path(selected["dataset"]),
            )
            if args.run_id != selected["run_id"]:
                raise RuntimeError("finalizer changed its condition")
            grant = invocation["finalizer_output_grant"]
            if sha(canonical(grant)) != invocation["finalizer_output_grant_sha256"] or grant != {
                "schema_version": "1.0.0",
                "scope": "condition-finalizer-output-only",
                "run_id": args.run_id,
                "candidate_binding_sha256": snapshot.digest,
                "raw_manifest_sha256": grant["raw_manifest_sha256"],
                "host_bytes": _FINALIZER_OUTPUT_ALLOCATION_BYTES,
                "derived_bytes": _FINALIZER_OUTPUT_ALLOCATION_BYTES,
            }:
                raise RuntimeError("finalizer output grant identity differs")
            contract = host._argument_provider_contract(args)
            paths = host._contract_paths_for(package, contract)
            manifest = host._manifest_for_contract(
                host.load_object(paths["commands"], label="condition manifests"),
                args.run_id,
                contract,
            )
            raw_manifest = (
                args.artifact_root
                / host.manifest_output_root(manifest)
                / "raw-attempt-manifest.json"
            )
            if sha(raw_manifest.read_bytes()) != grant["raw_manifest_sha256"]:
                raise RuntimeError("finalizer host grant selected another raw source")
            from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

            allowance = _AdmittedPublicationAllowance(grant["host_bytes"])

            def admit_host(path, count):
                if not path.is_relative_to(args.artifact_root) or any(
                    p.is_symlink() for p in [path, *path.parents]
                ):
                    raise RuntimeError("finalizer host writer escaped its bound root")
                allowance(count)

            token = host._HOST_OUTPUT_ADMISSION.set(admit_host)
            try:
                result = host.finalize_attempt(args)
                allowance.require_no_denial()
            finally:
                host._HOST_OUTPUT_ADMISSION.reset(token)
            write(
                transaction / "runtime-inputs" / (invocation["instance"] + "-receipt.json"), result
            )
        elif "finalizer_command" in invocation:
            finalizer_path = package / host.FINALIZER_RELATIVE_PATH
            snapshot.source_sha256(package, host.FINALIZER_RELATIVE_PATH)
            spec = importlib.util.spec_from_file_location(
                "retained_candidate_finalizer", finalizer_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            args = module._parser().parse_args(invocation["finalizer_command"])
            module._enforce_zero_core_limit()
            grant = invocation["finalizer_output_grant"]
            if (
                sha(canonical(grant)) != invocation["finalizer_output_grant_sha256"]
                or grant["candidate_binding_sha256"] != snapshot.digest
                or grant["run_id"] != args.run_id
                or grant["raw_manifest_sha256"] != sha(args.raw_attempt_manifest.read_bytes())
                or grant["derived_bytes"] != _FINALIZER_OUTPUT_ALLOCATION_BYTES
            ):
                raise RuntimeError("finalizer child output grant source differs")
            from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

            allowance = _AdmittedPublicationAllowance(grant["derived_bytes"])

            def admit_derived(path, count):
                if not path.is_relative_to(args.finalized_attempt_root) or any(
                    p.is_symlink() for p in [path, *path.parents]
                ):
                    raise RuntimeError("finalizer derived writer escaped its bound root")
                allowance(count)

            module.finalize(
                args,
                source_inputs=snapshot,
                fixture_binding=fixture,
                environment_binding=environment_binding,
                output_admission=admit_derived,
            )
            allowance.require_no_denial()
        elif "postcondition_export" in invocation:
            from giclab.harness.sira_gate_a_runtime import _AdmittedPublicationAllowance

            grant = invocation["export_output_grant"]
            if (
                grant
                != {
                    "scope": "retained-condition-export-only",
                    "candidate_binding_sha256": snapshot.digest,
                    "environment_binding_sha256": environment_binding.digest,
                    "run_id": invocation["postcondition_export"]["run_id"],
                    "bytes": _EXPORT_OUTPUT_ALLOCATION_BYTES,
                }
                or sha(canonical(grant)) != invocation["export_output_grant_sha256"]
            ):
                raise RuntimeError("retained export switched its explicit shared grant")
            allowance = _AdmittedPublicationAllowance(grant["bytes"])
            # A named environmental failure can narrow the archive writer's
            # window to zero. It cannot increase the shared transaction grant.
            archive_allowance = (
                _AdmittedPublicationAllowance(0)
                if invocation.get("fault_operation") == "export.output-denial"
                else None
            )
            transaction = Path(invocation["transaction_root"])

            def admit_export(path, count):
                if not path.is_relative_to(transaction) or any(
                    p.is_symlink() for p in (path, *path.parents)
                ):
                    raise RuntimeError("export writer escaped its bound transaction")
                if invocation.get("fault_operation") == "export.output-denial" and path == Path(
                    invocation["postcondition_export"]["inbound"]
                ) / (grant["run_id"] + ".tar.gz"):
                    # Consume the actual encoded chunk before its first byte.
                    archive_allowance(count)
                allowance(count)

            token = host._HOST_OUTPUT_ADMISSION.set(admit_export)
            try:
                _export_condition_evidence(invocation, host, snapshot, fixture, environment_binding)
                allowance.require_no_denial()
            finally:
                host._HOST_OUTPUT_ADMISSION.reset(token)
        elif "runtime_command" in invocation:
            _run_condition_runtime(invocation, snapshot, package, environment_root)
        else:
            host.main(
                source_inputs=snapshot,
                fixture_binding=fixture,
                environment_binding=environment_binding,
            )
    finally:
        phase_exception = sys.exc_info()[1]
        sys.setprofile(None)
        write(
            transaction
            / "retained-phase-traces"
            / f"{invocation.get('instance', invocation['phase'])}.json",
            {
                "candidate_binding_sha256": snapshot.digest,
                "environment_sha256": environment_binding.digest if environment_binding else None,
                "phase": invocation["phase"],
                "clock_events": clock_events,
                "calls": calls,
                "resource_observations": resource_observations,
                "environment_events": image_channel.events if image_channel else observations,
                "classification": "execution-trace-not-success-receipt",
                "failure": None
                if phase_exception is None
                else {
                    "type": type(phase_exception).__name__,
                    "message": str(phase_exception)[:1024],
                    "frames": [
                        {
                            "file": Path(frame.filename).name,
                            "line": frame.lineno,
                            "function": frame.name,
                        }
                        for frame in __import__("traceback").extract_tb(
                            phase_exception.__traceback__
                        )[-20:]
                    ],
                },
            },
        )
    snapshot.validate()
    print(json.dumps({"candidate": snapshot.digest, "fake_docker_observations": observations}))
    if (
        invocation["phase"] == "host-cleanup"
        and invocation["fault_operation"] == "cleanup.descendant-interruption"
    ):
        # A bound carrier fault AFTER actual retained cleanup/writers. This is a
        # real same-session descendant holding the two capture pipes, not a
        # successful cleanup/export double. Readiness prevents a TERM race.
        ready_read, ready_write = os.pipe()
        probe = None
        try:
            code = (
                "import os,signal,time; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"os.write({ready_write},b'R'); os.close({ready_write}); "
                "os.write(1,b'cleanup descendant stdout\\n'); "
                "os.write(2,b'cleanup descendant stderr\\n'); time.sleep(120)"
            )
            admitted_probe_command = [sys.executable, "-B", "-c", code]
            probe = native_popen(
                admitted_probe_command, stdin=subprocess.DEVNULL, pass_fds=(ready_write,)
            )
            admitted_probe_command = None
            os.close(ready_write)
            ready_write = None
            remaining = invocation["cleanup_output"]["deadline"] - time.monotonic()
            if remaining <= 0 or not select.select([ready_read], [], [], min(1, remaining))[0]:
                raise TimeoutError("cleanup descendant fixture readiness failed")
            if os.read(ready_read, 1) != b"R":
                raise RuntimeError("cleanup descendant fixture readiness malformed")
            phase_request = Path(
                invocation["argv"][invocation["argv"].index("--phase-request") + 1]
            )
            probe_path = phase_request.parent / "host-cleanup-supervision-probe.json"
            write(
                probe_path,
                {
                    "classification": "bound-offline-carrier-fault-not-success-receipt",
                    "candidate_binding_sha256": snapshot.digest,
                    "binding": invocation["cleanup_output"]["binding"],
                    "leader_pid": os.getpid(),
                    "descendant_pid": probe.pid,
                    "ready": True,
                    "fault": "partial-next-frame-after-retained-cleanup",
                },
            )
            # Prefix only: the shared consumer must preserve the prior grants
            # and classify actual EOF as interruption, without inventing an ACK.
            os.write(invocation["cleanup_output"]["write_descriptor"], b"\x00\x00")
            raise RuntimeError("bound cleanup partial-frame descendant interruption")
        finally:
            admitted_probe_command = None
            os.close(ready_read)
            if ready_write is not None:
                os.close(ready_write)
            # The outer owner retains the unreaped session leader and releases
            # this inherited group; this child may not establish another policy.


if __name__ == "__main__":
    main()
