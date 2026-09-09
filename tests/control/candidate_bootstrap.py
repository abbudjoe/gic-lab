"""Private offline test subprocess: no normal retained CLI selects this file."""

from __future__ import annotations

import argparse
import builtins
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


def qualify_local_fixture_inputs(*, snapshot, package, archive, qualification_root):
    """Run the retained producer over bound fixtures and fake installed metadata.

    Only the installed-package environment is substituted: real dist-info records
    are serialized in this test root and inventoried by the retained producer.
    The Python launcher is observed locally; no evaluator/model/browser is run here.
    """
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT as contract

    path = package / "containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py"
    specification = importlib.util.spec_from_file_location("candidate_local_qualifier", path)
    assert specification and specification.loader
    qualifier = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(qualifier)
    execution_path = package / contract.execution_contract_path
    execution = json.loads(execution_path.read_bytes())
    evaluator_path = package / execution["contract_bindings"]["evaluator"]["path"]
    evaluator = json.loads(evaluator_path.read_bytes())

    def installed_metadata(directory, packages):
        directory.mkdir(mode=0o700)
        for entry in packages:
            name, version = entry.split("==")
            distribution = directory / f"{name.replace('-', '_')}-{version}.dist-info"
            distribution.mkdir(mode=0o700)
            (distribution / "METADATA").write_text(
                f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
            )
        return directory

    base = installed_metadata(
        qualification_root / "fake-base-packages",
        execution["runtime"]["local_finalizer_base_packages"],
    )
    dependencies = installed_metadata(
        qualification_root / "fake-evaluator-packages", qualifier._expected_packages(evaluator)
    )
    qualifier.sysconfig = SimpleNamespace(get_paths=lambda: {"purelib": str(base)})
    return qualifier.qualify(
        argparse.Namespace(
            repository=package,
            provider_contract=contract.version,
            plan_id=None,
            package_commit=snapshot.document()["parent_head"],
            interpreter=Path(sys.executable),
            dependency_site_packages=dependencies,
            execution_contract=execution_path,
            evaluator_contract=evaluator_path,
            evaluator_root=package / "tests/fixtures/t09/pinned-evaluator",
            dataset=package / "tests/fixtures/t09/fanout-two-task-fixture.json",
            real_evidence_regression=qualification_root / "regression.json",
            finalizer_source=package / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py",
            finalizer_projection_source=(
                package / "containers/sira-smoke/pragmatic/t09_finalizer_projection.py"
            ),
            output=qualification_root / "local-finalizer-qualification.json",
        ),
        source_inputs=snapshot,
        fixture_binding=archive,
    )


def main() -> None:
    request = json.loads(sys.stdin.buffer.read(16384))
    root = Path(request["snapshot"])
    package = Path(request["package"])
    parent = Path(request["parent_repository"])
    # Third-party imports such as NLTK construct a downloader even when no
    # download is requested. Give this isolated child an explicit writable
    # test-owned home/cache; never inherit a host home or enable acquisition.
    for name, variable in (("fixture-home", "HOME"), ("nltk-data", "NLTK_DATA")):
        directory = root / name
        directory.mkdir(mode=0o700)
        os.environ[variable] = str(directory)
    forbidden = []
    template_metadata = set()
    original_open = builtins.open
    os_observations = []

    def environment_open(file, *args, **kwargs):
        # CPython's _osx_support probes this during evaluator dependency import.
        # Supply only that OS observation; never read the operator's host file.
        if (
            isinstance(file, (str, Path))
            and str(file) == "/System/Library/CoreServices/SystemVersion.plist"
        ):
            os_observations.append("fixture-macos-version")
            return io.StringIO(
                "<plist><dict><key>ProductUserVisibleVersion</key><string>13.0.0</string></dict></plist>"
            )
        return original_open(file, *args, **kwargs)

    builtins.open = environment_open

    def guard(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "os.system"}:
            forbidden.append(event)
            raise RuntimeError("offline candidate bootstrap denied an environmental operation")
        if event == "subprocess.Popen":
            argv = args[1]
            worker = [
                sys.executable,
                "-B",
                str(root / "source/tests/control/retained_candidate_effects.py"),
            ]
            if argv == worker:
                return
            if (
                isinstance(argv, list)
                and argv[:3] == worker
                and len(argv) == 5
                and argv[3] == "--invocation"
            ):
                invocation_path = Path(argv[4])
                if (
                    invocation_path.is_absolute()
                    and not invocation_path.is_symlink()
                    and invocation_path.is_relative_to(transaction_root)
                    and invocation_path.name.endswith("-invocation.json")
                ):
                    return
            if (
                not isinstance(argv, list)
                or len(argv) < 4
                or argv[:3] != ["git", "-C", str(parent)]
                or argv[3] not in {"show", "rev-parse", "merge-base"}
            ):
                forbidden.append(event)
                raise RuntimeError("offline candidate bootstrap denied a process effect")
        if event == "open" and isinstance(args[0], (str, bytes)):
            if isinstance(args[2], int) and args[2] & os.O_DIRECTORY:
                # Retained staging walks exact ancestors with directory fds.
                # This permits traversal, not file-content reads outside inputs.
                return
            path = Path(os.fsdecode(args[0])).resolve()
            guard_entry = Path(os.environ["GICLAB_CI_GUARD_JOURNAL"]) / f"{os.getpid()}.jsonl"
            if path == guard_entry:
                # Preserve the precollection guard's exact per-process denial
                # record even when this narrower input guard also rejects it.
                return
            allowed = [
                root,
                package,
                Path(sys.prefix),
                Path(sys.base_prefix),
                Path(__file__).resolve().parents[2],
            ]
            writable = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            if (
                writable
                and path != Path("/dev/null")
                and not any(path.is_relative_to(base) for base in (root, package))
            ):
                forbidden.append("write-outside-test-roots")
                raise RuntimeError("offline candidate bootstrap denied an external file write")
            if (
                not any(path.is_relative_to(base) for base in allowed)
                and path != Path("/dev/null")
                and path not in template_metadata
            ):
                forbidden.append("open-outside-inputs:" + str(path))
                raise RuntimeError("offline candidate bootstrap denied an unbound file read")

    sys.addaudithook(guard)
    from giclab.harness.t09_candidate_inputs import (
        CandidateInputError,
        load_candidate_source_snapshot,
        project_candidate_package,
    )
    from giclab.harness.t09_provider_contracts import V16_PROVIDER_CONTRACT

    snapshot = load_candidate_source_snapshot(
        root,
        expected_binding_sha256=request["binding_sha256"],
        parent_repository=parent,
        expected_parent_head=request["parent_head"],
        expected_parent_tree=request["parent_tree"],
    )
    marker = project_candidate_package(snapshot, package)
    temporary = root / "temporary"
    temporary.mkdir(mode=0o700)
    os.environ["TMPDIR"] = str(temporary)
    template_metadata.update(
        (parent / member["path"]).resolve()
        for member in snapshot.document()["source_members"]
        if member["role"]
        in {"historical-template", "control-validation-input", "retained-resource"}
    )
    host_path = package / "containers/sira-smoke/pragmatic/t09_remote_runner.py"
    spec = importlib.util.spec_from_file_location("candidate_retained_host", host_path)
    assert spec and spec.loader
    host = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = host
    spec.loader.exec_module(host)
    normal_rejections = []
    try:
        host.verify_package(package, request["parent_head"], contract=V16_PROVIDER_CONTRACT)
    except CandidateInputError:
        normal_rejections.append("verify_package")
    else:
        raise AssertionError("normal verifier accepted candidate inputs")
    sys.argv = [
        str(host_path),
        "--provider-contract",
        V16_PROVIDER_CONTRACT.version,
        "--repository",
        str(package),
        "--artifact-root",
        str(root / "forbidden-live-root"),
        "--package-commit",
        request["parent_head"],
        "cleanup",
    ]
    try:
        host.main()
    except CandidateInputError:
        normal_rejections.append("retained_cli")
    else:
        raise AssertionError("normal retained CLI accepted candidate inputs")
    commands = host.verify_package(
        package,
        request["parent_head"],
        current_commit=request["parent_head"] if request.get("exercise_current_commit") else None,
        contract=V16_PROVIDER_CONTRACT,
        source_inputs=snapshot,
    )
    current_commit_checks = []
    if request.get("exercise_current_commit"):
        current_commit_checks.append("exact-candidate")
        try:
            host.verify_package(
                package,
                request["parent_head"],
                current_commit="0" * 40,
                contract=V16_PROVIDER_CONTRACT,
                source_inputs=snapshot,
            )
        except host.T09HostError as exc:
            if str(exc) != "candidate source parent/template differs":
                raise
            current_commit_checks.append("wrong-current-rejected")
        else:
            raise AssertionError("candidate source accepted the wrong current ancestor")
    downstream = host.validate_finalizer_source(
        repository=package,
        package_commit=request["parent_head"],
        finalizer_commit=request["parent_head"],
        source=package / host.FINALIZER_RELATIVE_PATH,
        projection_source=package / host.FINALIZER_PROJECTION_RELATIVE_PATH,
        source_inputs=snapshot,
    )
    from giclab.harness.t09_qualification_fixture import build_deterministic_qualification_archive

    qualification_root = root / "qualification"
    qualification_root.mkdir(mode=0o700)
    os.environ["TMPDIR"] = str(qualification_root)
    archive = build_deterministic_qualification_archive(snapshot.root, qualification_root)
    if archive.document() != snapshot.document()["qualification_fixture"]:
        raise ValueError("candidate switched qualification fixture")
    staging, staged = host.stage_qualification_archive(
        repository=package,
        source=archive.archive_path,
        fixture_binding=archive,
    )
    regression_path = package / "containers/sira-smoke/pragmatic/t09_real_evidence_regression.py"
    regression_spec = importlib.util.spec_from_file_location(
        "candidate_retained_regression", regression_path
    )
    assert regression_spec and regression_spec.loader
    regression = importlib.util.module_from_spec(regression_spec)
    regression_spec.loader.exec_module(regression)
    finalizer = package / "containers/sira-smoke/pragmatic/t09_evaluate_attempt.py"
    evaluator_failures = []

    def evaluator_trace(frame, event, value):
        # Observe swallowed fixture-evaluator exceptions without changing the
        # retained evaluator's result or its semantic comparison.
        if frame.f_code.co_name == "evaluate_retained_session":
            if event == "exception" and len(evaluator_failures) < 4:
                kind, error, _ = value
                evaluator_failures.append(
                    {"exception_type": kind.__name__, "message": str(error)[:512]}
                )
            return evaluator_trace
        return None

    previous_trace = sys.gettrace()
    sys.settrace(evaluator_trace)
    try:
        fixture_result = regression.run(
            argparse.Namespace(
                archive=staged,
                public_disposition=qualification_root / "not-historical",
                finalizer_source=finalizer,
                finalizer_source_sha256=hashlib.sha256(finalizer.read_bytes()).hexdigest(),
                dataset=package / "tests/fixtures/t09/fanout-two-task-fixture.json",
                evaluator_root=package / "tests/fixtures/t09/pinned-evaluator",
                output=qualification_root / "regression.json",
            ),
            fixture_binding=archive,
            fixture_repository=package,
        )
    except regression.RegressionError as exc:
        trace = exc.__traceback__
        while trace is not None:
            values = trace.tb_frame.f_locals
            if "repeated_projection" in values and "projection" in values:
                print(
                    json.dumps(
                        {
                            "first_fixture_projection": values["projection"],
                            "repeated_fixture_projection": values["repeated_projection"],
                            "denied_environmental_operations": forbidden,
                            "fixture_evaluator_exceptions": evaluator_failures,
                        }
                    ),
                    file=sys.stderr,
                )
            trace = trace.tb_next
        raise
    finally:
        sys.settrace(previous_trace)
    prelaunch_local_qualification = None
    if request.get("exercise_transaction") in {
        "transaction",
        "condition-failure-export",
        "transaction-no-answer",
        "transaction-attach-output-denial",
        "transaction-export-output-denial",
    }:
        prelaunch_local_qualification = qualify_local_fixture_inputs(
            snapshot=snapshot,
            package=package,
            archive=archive,
            qualification_root=qualification_root,
        )
    preparation = None
    if request.get("exercise_preparation") is True:
        from giclab.control.composition import compose_control_plane
        from giclab.control.proofs import validate_shadow_rehearsal
        from giclab.control.registry_validation import validate_registry_completeness
        from giclab.control.state_capsule import generate_state_capsule
        from giclab.control.version_lint import validate_active_version_dispatch

        lint = validate_active_version_dispatch(package, source_inputs=snapshot)
        registry = validate_registry_completeness(package, source_inputs=snapshot)
        if not registry["complete"] or not lint["complete"]:
            raise AssertionError({"registry": registry["errors"], "lint": lint["findings"]})
        composition = compose_control_plane(
            package,
            contract=V16_PROVIDER_CONTRACT,
            registry_receipt=registry,
            version_lint_receipt=lint,
            source_inputs=snapshot,
        )
        capsule = generate_state_capsule(
            package,
            registry_complete=True,
            composition_valid=True,
            version_lint_valid=True,
            shadow_happy_path=False,
            failure_matrix_valid=False,
            source_inputs=snapshot,
        )
        proof = validate_shadow_rehearsal(
            package,
            V16_PROVIDER_CONTRACT,
            registry_receipt=registry,
            version_lint_receipt=lint,
            composition_receipt=composition,
            state_capsule=capsule,
            source_inputs=snapshot,
        )
        from dataclasses import replace

        from giclab.control.category3 import (
            Category3Request,
            execute_category3_transaction,
            prepare_category3,
        )
        from giclab.control.effects import EffectAuthorityKind, EffectExecutionMode
        from giclab.control.shadow_effects import (
            ShadowFaultPlan,
            build_production_shadow_assembly,
        )

        # Allocate through the shared guard's tracked private-IPC primitive so
        # the same concrete ownership root is inherited by retained children.
        transaction_root = Path(tempfile.mkdtemp(prefix="controller-transaction-", dir=temporary))
        effects = None
        mode = request.get("exercise_transaction")
        if mode:
            worker_path = snapshot.root / "tests/control/retained_candidate_effects.py"
            worker_spec = importlib.util.spec_from_file_location(
                "retained_candidate_effects", worker_path
            )
            worker = importlib.util.module_from_spec(worker_spec)
            sys.modules[worker_spec.name] = worker
            worker_spec.loader.exec_module(worker)
            from giclab.harness.t09_environment_fixture import build_environment_fixture

            environment = build_environment_fixture(
                snapshot, package, transaction_root / "environment-inputs"
            )
            effects = worker.RetainedCandidateEffects(
                repository=package,
                contract=V16_PROVIDER_CONTRACT,
                fault_plan=ShadowFaultPlan(
                    "candidate-input-preparation",
                    fail_operation="condition.partial-failure"
                    if mode == "condition-failure-export"
                    else "condition.no-answer"
                    if mode == "transaction-no-answer"
                    else "export.output-denial"
                    if mode == "transaction-export-output-denial"
                    else "condition.attach-output-denial"
                    if mode == "transaction-attach-output-denial"
                    else "host.before-transfer"
                    if mode == "provider-entry-pre-transfer-failure"
                    else "host.qualify"
                    if mode == "qualification-start-failure"
                    else "host.preflight"
                    if mode == "preflight-start-failure"
                    else None,
                ),
                fixed_tick=1000,
                transaction_root=transaction_root,
                source_inputs=snapshot,
                qualification_source_root=qualification_root,
                environment_binding=environment,
            )
        world = build_production_shadow_assembly(
            package,
            V16_PROVIDER_CONTRACT,
            ShadowFaultPlan("candidate-input-preparation"),
            rehearsal=proof,
            transaction_root=transaction_root,
            source_inputs=snapshot,
            low_level_effects=effects,
        )
        try:
            context = world.authorization_context
            assert context.candidate_source_binding_sha256 == snapshot.digest
            try:
                replace(
                    context,
                    authority_kind=EffectAuthorityKind.LIVE_AUTHORIZED,
                    execution_mode=EffectExecutionMode.EXTERNAL_LIVE,
                )
            except ValueError:
                normal_rejections.append("candidate-live-authority-context")
            else:
                raise AssertionError("candidate input minted a live context")
            controller_request = Category3Request(
                repository=package,
                contract=V16_PROVIDER_CONTRACT,
                scenario="candidate-input-preparation",
                expected_repository_commit=request["parent_head"],
                expected_repository_tree=request["parent_tree"],
                control_proof=proof,
                source_inputs=snapshot,
            )
            if effects is not None:
                retained_failures = []
                prior_trace = sys.gettrace()

                def trace_retained_failure(frame, event, arg):
                    shared_run = (
                        frame.f_code.co_name in {"run", "finalize"}
                        and frame.f_code.co_filename.endswith("/control/production.py")
                    ) or (
                        frame.f_code.co_name
                        in {
                            "finalize_condition",
                            "_retained_finalizer_outcome",
                            "execute_condition",
                            "_interrupted_condition_outcome",
                        }
                        and frame.f_code.co_filename.endswith(
                            "/control/retained_candidate_effects.py"
                        )
                    )
                    if not shared_run and frame.f_code.co_name not in {
                        "hold_retained_condition_source",
                        "preserve_retained_condition_failure",
                        "_publish_retained_condition_failure",
                        "_validate_and_seal_condition_failure",
                        "export_retained_condition_failure_projection",
                        "_hold_failure_artifacts",
                    }:
                        return None
                    if (
                        event == "exception"
                        and (
                            shared_run
                            or frame.f_code.co_name
                            in {
                                "hold_retained_condition_source",
                                "preserve_retained_condition_failure",
                                "_publish_retained_condition_failure",
                                "_validate_and_seal_condition_failure",
                                "export_retained_condition_failure_projection",
                                "_hold_failure_artifacts",
                            }
                        )
                        and len(retained_failures) < 24
                    ):
                        kind, error, _ = arg
                        retained_failures.append(
                            {
                                "function": frame.f_code.co_name,
                                "line": frame.f_lineno,
                                "type": kind.__name__,
                                "error": str(error)[:512],
                                "source_trace": [
                                    {
                                        "file": Path(f.f_code.co_filename).name,
                                        "function": f.f_code.co_name,
                                        "line": line,
                                    }
                                    for f, line in list(__import__("traceback").walk_tb(arg[2]))[
                                        :24
                                    ]
                                ],
                            }
                        )
                    return trace_retained_failure

                try:
                    sys.settrace(trace_retained_failure)
                    with effects.retained_observation_scope():
                        transaction = execute_category3_transaction(
                            controller_request, adapters=world.adapters()
                        )
                finally:
                    sys.settrace(prior_trace)
                    snapshot.validate()
                # Preserve the actual controller result before asserting success.
                # A failed positive transaction remains a failed positive test.
                (transaction_root / "joined-controller-result.json").write_text(
                    json.dumps(transaction, sort_keys=True, indent=2) + "\n"
                )
                (transaction_root / "joined-failure-diagnostics.json").write_text(
                    json.dumps(retained_failures, sort_keys=True, indent=2) + "\n"
                )
                snapshot.validate()
                if mode == "provider-entry-pre-transfer-failure":
                    from giclab.harness import t09_pragmatic_provider as provider

                    # Reuse the actual terminal provider source without a second
                    # environmental request. This is an idempotent consumer check
                    # after the controller prefix, not a second campaign.
                    closeout = effects.retained_closeouts[1]
                    campaign_root = closeout.parent.parent
                    controls = effects.campaign_low_level_controls()
                    before_receipt = closeout.read_bytes()
                    before_accounting = world._campaign_accountant().accounting_document()

                    def no_duplicate_request(*args, **kwargs):
                        raise AssertionError(
                            "idempotent closeout dispatched another provider effect"
                        )

                    with world._campaign_writer_scope(cleanup=True), effects.campaign_scope():
                        resumed = provider.closeout_campaign(
                            contract=V16_PROVIDER_CONTRACT,
                            repository=package,
                            package_commit=controls.expected_package_commit,
                            authorization_ledger=transaction_root
                            / "control-private/authorization-overlay.json",
                            dotenv=transaction_root / "control-private/mixed.env",
                            private_root=campaign_root,
                            transport=SimpleNamespace(request=no_duplicate_request),
                            clock=effects._clock.wall_time,
                            sleeper=effects._clock.sleep,
                        )
                    assert resumed == closeout and resumed.read_bytes() == before_receipt
                    assert world._campaign_accountant().accounting_document() == before_accounting
                    (transaction_root / "joined-pre-transfer-idempotence.json").write_text(
                        json.dumps(
                            {
                                "candidate_binding_sha256": snapshot.digest,
                                "receipt_sha256": hashlib.sha256(before_receipt).hexdigest(),
                                "provider_redispatch_allowed": False,
                                "accounting_unchanged": True,
                                "scope": "retained terminal consumer after full-controller prefix",
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                campaign_boundary = world._campaign_accountant()
                campaign_writers = [
                    {
                        "path": str(item.path.relative_to(transaction_root)),
                        "role": item.role.value,
                        "granted_bytes": item.granted,
                        "observed_bytes": item.observed,
                        "cleanup": item.cleanup,
                        "closed": item.closed,
                    }
                    for item in world._campaign_writes
                ]
                campaign_projection = {
                    "candidate_binding_sha256": snapshot.digest,
                    "plan_id": V16_PROVIDER_CONTRACT.plan_id,
                    "host_run_id": V16_PROVIDER_CONTRACT.host_run_id,
                    "accounting": campaign_boundary.accounting_document(),
                    "writers": campaign_writers,
                    "coverage": "provider-parent and parent cleanup writers; not full R6 closure",
                }
                (transaction_root / "joined-campaign-output.json").write_text(
                    json.dumps(campaign_projection, sort_keys=True, indent=2) + "\n"
                )
                assert campaign_boundary.campaign_output_observed == sum(
                    item["observed_bytes"] for item in campaign_writers
                )
                assert all(item["closed"] for item in campaign_writers)
                assert any(
                    item["role"] == "provider-journal"
                    and item["path"].endswith("entry-source/request-journal.jsonl")
                    for item in campaign_writers
                ), "retained provider entry was disconnected from campaign admission"
                assert any(item["role"] == "cleanup-journal" for item in campaign_writers)
                accounting_rows = []
                for run_id, observer in world._condition_observers.items():
                    actual = observer.boundary.accounting_document()
                    remote = observer._closed_remote_output
                    controller = observer._controller_output_observed
                    row = {
                        "run_id": run_id,
                        "runtime_event_output_bytes": observer.output_total_bytes,
                        "closed_remote_attempt_bytes": remote,
                        "controller_observed_bytes": controller,
                        "remote_granted_bytes": observer._remote_output_allowance,
                        "controller_granted_bytes": observer._controller_output_allowance,
                        "closed_remote_reconciled": observer._closed_remote_reconciled,
                        "accounting": actual,
                        "classification": (
                            "observed-counter-reconciliation-not-writer-admission-proof"
                        ),
                    }
                    accounting_rows.append(row)
                    if remote is not None and observer._closed_remote_reconciled:
                        assert actual["observed_lower_bound"]["condition"]["output_bytes"] == (
                            remote + controller
                        )
                        assert actual["reserved_upper_bound"]["condition"]["output_bytes"] == (
                            observer._remote_output_allowance
                            + observer._controller_output_allowance
                        )
                (transaction_root / "joined-output-accounting.json").write_text(
                    json.dumps(accounting_rows, sort_keys=True, indent=2) + "\n"
                )
                expected_terminal = (
                    "category3-shadow-stopped-cleanup-unresolved"
                    if mode == "transaction-export-output-denial"
                    else "category3-shadow-stopped-cleanup-verified"
                    if mode
                    in {
                        "provider-entry-pre-transfer-failure",
                        "qualification-start-failure",
                        "preflight-start-failure",
                        "condition-failure-export",
                        "transaction-no-answer",
                        "transaction-attach-output-denial",
                    }
                    else "category3-shadow-complete-clean"
                )
                assert transaction["terminal_state"] == expected_terminal, {
                    "stop": transaction["earliest_stopping_phase"],
                    "reason": transaction["stop_reason"],
                    "transitions": transaction["ordered_state_transitions"][-5:],
                    "retained_phase_events": effects.phase_events,
                    "retained_failure_exceptions": retained_failures,
                }
                if mode == "condition-failure-export":
                    run_id = V16_PROVIDER_CONTRACT.run_ids[0]
                    assert transaction["condition_identities_consumed"] == [run_id], {
                        "stop": transaction["earliest_stopping_phase"],
                        "reason": transaction["stop_reason"],
                        "retained_phase_events": effects.phase_events,
                    }
                    assert transaction["earliest_stopping_phase"] == "condition-execution"
                    failure = world._condition_failures[run_id]
                    export = world._essential_failure_exports[run_id]
                    assert failure.retained_source is not None
                    assert (
                        failure.answer == "No relevant answer." and failure.process_exit_code != 0
                    )
                    assert world._finalizations == {} and world._evaluations == {}
                    source = json.loads(failure.retained_source.completion_path.read_bytes())
                    accounting = json.loads(failure.call_ledger_path.read_bytes())
                    assert source["answer"] == failure.answer
                    assert source["process_exit_code"] == failure.process_exit_code
                    assert source["completed"] is failure.completed
                    assert (
                        export.export_complete
                        and export.essential_total_bytes == failure.essential_total_bytes
                    )
                    assert len(accounting["call_ids"]) == 2
                    assert accounting["call_ids"] == accounting["logical_call_ids"]
                    retained_failure_projection = {
                        "candidate_binding_sha256": snapshot.digest,
                        "source_authority": failure.retained_source.authority,
                        "answer": failure.answer,
                        "process_exit_code": failure.process_exit_code,
                        "call_ids": accounting["call_ids"],
                        "logical_call_ids": accounting["logical_call_ids"],
                        "unscored": True,
                        "export_complete": export.export_complete,
                        "source_completion_sha256": hashlib.sha256(
                            failure.retained_source.completion_path.read_bytes()
                        ).hexdigest(),
                        "export_receipt_sha256": export.receipt_sha256,
                    }
                elif mode == "transaction-export-output-denial":
                    run_id = V16_PROVIDER_CONTRACT.run_ids[0]
                    assert transaction["condition_identities_consumed"] == [run_id]
                    assert world._evaluations == {} and world._finalizations == {}
                    assert effects.retained_exports == {}
                    inbound = transaction_root / "retained-exports" / run_id
                    archive = inbound / (run_id + ".tar.gz")
                    assert archive.is_file() and archive.stat().st_size == 0
                    assert not (inbound / "acknowledgement-delivery.json").exists()
                    assert not (inbound / "offline-export-binding.json").exists()
                    carrier = json.loads((inbound / "carrier-result.json").read_bytes())
                    assert carrier["returncode"] != 0
                    assert "allowance" in carrier["stderr"]
                    assert not any(
                        r in world._condition_requests for r in V16_PROVIDER_CONTRACT.run_ids[1:]
                    )
                elif mode == "transaction-attach-output-denial":
                    run_id = V16_PROVIDER_CONTRACT.run_ids[0]
                    assert transaction["condition_identities_consumed"] == [run_id]
                    assert not world._evaluations
                    failure = world._condition_failures[run_id]
                    assert failure.retained_source is not None
                    assert failure.retained_source.authority == "essential-infrastructure-failure"
                    source = json.loads(failure.retained_source.completion_path.read_bytes())
                    summary = json.loads(
                        (
                            failure.retained_source.manifest_path.parent
                            / "essential-failure/failure-summary.json"
                        ).read_bytes()
                    )
                    # Attach output denial is infrastructure-invalid even when
                    # the workload has already exited zero. Preserve the actual
                    # status/answer instead of manufacturing a nonzero exit.
                    assert type(failure.process_exit_code) is int
                    assert (
                        failure.process_exit_code
                        == source["process_exit_code"]
                        == summary["process_exit_code"]
                    )
                    assert source["answer"] == failure.answer
                    assert source["completed"] is failure.completed
                    assert source["infrastructure_invalid"] is True
                    assert source["evaluator_eligible"] is False
                    assert summary["attempt_state"] == "consumed-infrastructure-invalid-unscored"
                    assert summary["task_score"] is None
                    assert summary["campaign_continuation_permitted"] is False
                    assert not world._finalizations
                    assert world._essential_failure_exports[run_id].export_complete is True
                    assert (
                        world._essential_failure_exports[run_id].essential_total_bytes
                        == failure.essential_total_bytes
                    )
                    assert failure.unknown_call_ids == ()
                    assert not any(
                        r in world._condition_requests for r in V16_PROVIDER_CONTRACT.run_ids[1:]
                    )
                elif mode == "transaction-no-answer":
                    assert transaction["condition_identities_consumed"] == list(
                        V16_PROVIDER_CONTRACT.run_ids[:2]
                    ), "normal no-answer attempts must reach the actual first-pair policy"
                    assert not world._condition_failures
                    for run_id in V16_PROVIDER_CONTRACT.run_ids[:2]:
                        outcome = world._condition_outcomes[run_id]
                        assert outcome.exit_code == 0 and outcome.completed is False
                        assert outcome.answer is None
                        assert world._finalizations[run_id].infrastructure_valid is True
                        evaluation = world._evaluations[run_id]
                        assert evaluation["evaluator_valid"] is True
                        assert evaluation["answer_produced"] is False
                        assert evaluation["task_completed"] is False and evaluation["score"] == 0.0
                    assert world._checkpoint_document["decision"] != "continue-to-task-b"
                    assert any(
                        e["phase"] == "first-pair-checkpoint"
                        for e in transaction["ordered_state_transitions"]
                    )
                elif mode == "provider-entry-pre-transfer-failure":
                    assert transaction["condition_identities_consumed"] == []
                    assert effects.phase_receipts == {}
                    assert len(effects.retained_closeouts) == 1
                    assert not world._condition_observers
                elif mode in {"qualification-start-failure", "preflight-start-failure"}:
                    assert transaction["earliest_stopping_phase"] == (
                        "host-preflight"
                        if mode == "preflight-start-failure"
                        else "image-finalizer-qualification"
                    )
                    assert transaction["condition_identities_consumed"] == []
                else:
                    assert transaction["condition_identities_consumed"] == list(
                        V16_PROVIDER_CONTRACT.run_ids
                    )
                    prior = set()
                    runtime_processes = set()
                    for ordinal, run_id in enumerate(V16_PROVIDER_CONTRACT.run_ids):
                        observer = world._condition_observers[run_id]
                        assert observer.prior_call_ids == prior
                        assert observer.prior_logical_call_ids == prior
                        assert len(observer.call_ids) == 2
                        assert not prior.intersection(observer.call_ids)
                        assert observer.call_ids == observer.logical_call_ids
                        prior.update(observer.call_ids)
                        outcome = world._condition_outcomes[run_id]
                        answer = (
                            "No relevant answer."
                            if ordinal % 2 == 0
                            else "Unrelated fixture answer."
                        )
                        assert outcome.exit_code == 0 and outcome.completed is True
                        assert outcome.answer == answer
                        assert observer.completion_state == (True, answer, "")
                        assert world._finalizations[run_id].infrastructure_valid is True
                        evaluation = world._evaluations[run_id]
                        assert evaluation["evaluator_valid"] is True
                        assert evaluation["answer_produced"] is True
                        assert evaluation["task_completed"] is True and evaluation["score"] == 0.0
                        invocation = json.loads(effects.condition_invocations[run_id].read_bytes())
                        diagnostic = json.loads(
                            (
                                transaction_root
                                / "fixture-process-environment"
                                / (invocation["instance"] + "-runtime")
                                / ("output-census-" + run_id + ".json")
                            ).read_bytes()
                        )
                        assert diagnostic["candidate_binding_sha256"] == snapshot.digest
                        assert diagnostic[
                            "executed_runtime_source_sha256"
                        ] == snapshot.source_sha256(
                            snapshot.root, "src/giclab/harness/sira_gate_a_runtime.py"
                        )
                        runtime_processes.add(diagnostic["runtime_process_id"])
                    assert len(prior) == 8 and prior == world._seen_call_ids
                    assert len(runtime_processes) == 4
                    assert world._checkpoint_document["decision"] == "continue-to-task-b"
            else:
                prepared = prepare_category3(controller_request, adapters=world.adapters())
                if prepared.prepared is None:
                    raise AssertionError(prepared)
            assembly = world._package_assembly_evidence
            assert assembly is not None
            assert assembly["candidate_source_binding_sha256"] == snapshot.digest
            assert assembly["tracked_only"] is False
            assert assembly["uploaded"] is False
            if effects is None:
                assert world.low_level_effects.metadata_request_count == 0
        finally:
            world.release_resources()
        preparation = {
            "candidate_binding_sha256": snapshot.digest,
            "registry_contract_count": registry["contract_count"],
            "lint_files_scanned": lint["files_scanned"],
            "composition_sha256": composition["semantic_sha256"],
            "staging_sha256": proof.staging.semantic_sha256,
            "command_package_sha256": proof.staging.command_package_sha256,
            "joined_transaction": "not-run" if effects is None else transaction,
            "retained_phase_events": [] if effects is None else effects.phase_events,
            "retained_failure_projection": retained_failure_projection
            if mode == "condition-failure-export"
            else None,
            "retained_provider_closeouts": []
            if effects is None
            else [
                {"launch_ordinal": ordinal, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for ordinal, path in sorted(effects.retained_closeouts.items())
            ],
            "controller_local_assembly": assembly,
        }
    local_qualification = prelaunch_local_qualification
    if request.get("exercise_local_qualification"):
        local_qualification = qualify_local_fixture_inputs(
            snapshot=snapshot,
            package=package,
            archive=archive,
            qualification_root=qualification_root,
        )
        observed = host.validate_local_finalizer_qualification(
            qualification_root / "local-finalizer-qualification.json",
            repository=package,
            package_commit=request["parent_head"],
            require_local_runtime=False,
            contract=V16_PROVIDER_CONTRACT,
            source_inputs=snapshot,
            fixture_binding=archive,
            fixture_regression=qualification_root / "regression.json",
        )
        assert observed == local_qualification
        # The historical validator must reject test provenance before it probes
        # a runtime, even when the caller selects an ordinary historical root.
        try:
            host.validate_local_finalizer_qualification(
                qualification_root / "local-finalizer-qualification.json",
                repository=parent,
                package_commit=request["parent_head"],
                require_local_runtime=True,
                contract=V16_PROVIDER_CONTRACT,
            )
        except host.T09HostError as exc:
            assert "historical/live" in str(exc)
        else:
            raise AssertionError("historical host accepted an offline local qualification")
        for field in (
            "candidate_binding_sha256",
            "fixture_id",
            "dataset_sha256",
            "finalizer",
            "model_requests",
            "command_manifest_sha256",
        ):
            changed = json.loads(json.dumps(local_qualification))
            if field == "candidate_binding_sha256":
                changed["offline_candidate_inputs"][field] = "f" * 64
            elif field == "fixture_id":
                changed["offline_candidate_inputs"]["qualification_fixture"][field] = "wrong"
            elif field == "finalizer":
                changed["source_sha256s"][field] = "f" * 64
            elif field == "model_requests":
                changed[field] = 1
            else:
                changed[field] = "f" * 64
            mutation = qualification_root / f"mutated-local-{field}.json"
            host.write_exclusive(mutation, changed)
            try:
                host.validate_local_finalizer_qualification(
                    mutation,
                    repository=package,
                    package_commit=request["parent_head"],
                    require_local_runtime=False,
                    contract=V16_PROVIDER_CONTRACT,
                    source_inputs=snapshot,
                    fixture_binding=archive,
                    fixture_regression=qualification_root / "regression.json",
                )
            except host.T09HostError:
                pass
            else:
                raise AssertionError(f"local qualifier accepted mutated {field}")
    imports = []
    for name, module in tuple(sys.modules.items()):
        if name == "giclab" or name.startswith("giclab."):
            source = getattr(module, "__file__", None)
            if source is not None:
                relative = Path(source).resolve().relative_to(snapshot.root.resolve()).as_posix()
                snapshot.source_sha256(snapshot.root, relative)
                imports.append(relative)
    snapshot.validate()
    print(
        json.dumps(
            {
                "marker": marker,
                "imported_sources": sorted(set(imports)),
                "conditions": [m["run_id"] for m in commands["manifests"]],
                "forbidden_effects": forbidden,
                "archive_staging": staging,
                "archive_regression": fixture_result,
                "fake_os_observations": os_observations,
                "normal_entry_rejections": normal_rejections,
                "downstream_source_bindings": downstream[5],
                "current_commit_checks": current_commit_checks,
                "preparation": preparation,
                "local_qualification": local_qualification,
            }
        )
    )


if __name__ == "__main__":
    main()
