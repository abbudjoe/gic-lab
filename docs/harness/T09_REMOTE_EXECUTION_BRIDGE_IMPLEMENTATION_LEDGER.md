# T09 remote-execution bridge implementation ledger

Status: **review-repair-blocked; R1–R6 unresolved**

The prior completion statements below are historical worker claims, challenged by
review `5122766860`. They are not current retained-transaction evidence. Historical
Sol/max attestations and dispositions remain unchanged.

Plan role: **Category 1 shared-control repair workstream**

Live authorization: **false**

Scientific interpretation allowed: **false**

## Source contract

This workstream is governed by the operator-supplied `T09 PR 1.3 — Remote
Execution Bridge and Phase-Conformant Live Path` contract. It repairs the generic
shared bridge exposed by the stopped source-first V17 viability audit. It is not a
V17 package task and cannot create `PLAN-EXP0001-PILOT-V17`, `AUTONOMOUS-0010`, a
V17 contract, effect, proof root, authorization overlay, or run root.

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
live_execution_allowed: false
```

The immutable base is commit
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`, tree
`e3cf777632400ec18736a34b6abec53d6d67de55`, with ordered parents
`f1d872d59c4952eb98467c2506850af7772f4454` and
`ff53df189a50bc040affa4b899b1c46f24acaf7e`.

## Workstream map

- G1 replaces ambiguous pre-provider staging with deterministic local assembly and
  an exact post-entry host-transfer receipt.
- G2 exposes retained transfer verification, preflight, qualification, and freeze
  as distinct typed phases while keeping the historical compound wrapper.
- G3 adds a bounded, sequenced, hash-chained duplex condition session whose remote
  client blocks on the shared observer's admission decision.
- G4 removes the second launch method so `launch_campaign()` plus its selected
  campaign transport is the sole launch mutation seam.
- The viability validator and complete local no-network bridge conformance bind the
  repaired methods and phases before any future package successor is permitted.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| RB-01 | Exact base/history verified | Git/GitHub identity, clean checkout, baseline capsule and agent-check | met |
| RB-02 | Complete method-to-primitive map has zero gaps | Schema-valid source map and generated viability receipt | met |
| RB-03 | Local assembly is distinct from host transfer | Typed requests/receipts and ordering regressions | met |
| RB-04 | Host transfer is post-entry and remotely rehashed | Controller/production tests and bridge conformance | met |
| RB-05 | Preflight, qualification, and freeze are phase-specific | Retained runner entrypoints and phase-chain tests | met |
| RB-06 | Full retained dynamic manifest is authoritative | Versioned validator, projection, and mutation regressions | met |
| RB-07 | Historical compound preflight remains compatible | Compatibility-wrapper regression | met |
| RB-08 | Duplex protocol is bounded, sequenced, and hash-chained | Codec/session/property regressions | met |
| RB-09 | Remote sends/actions block on shared admission | Coupling and failure-order tests | met |
| RB-10 | Shared observer is the sole authoritative accountant | Source lint, runtime proof, and accounting equality | met |
| RB-11 | Channel-loss semantics preserve exact unknown states | Before/after-send disconnect regressions | met |
| RB-12 | Transcript is bound into raw/essential evidence | Held transcript manifests and mutation tests | met |
| RB-13 | Provider launch has exactly one mutation seam | Protocol removal, static scan, and transport tests | met |
| RB-14 | Shared transaction order matches live lifecycle | Exact state-transition regression | met |
| RB-15 | Full no-network remote-bridge conformance passes | Local subprocess/private IPC receipt | met |
| RB-16 | Viability receipt reports every live method complete | Generated V16 receipt and schema validation | met |
| RB-17 | Synthetic successor requires no shared edits | Temporary successor conformance and byte-map proof | met |
| RB-18 | Historical V16 proof remains valid | Rebound/current and historical-root validation | met |
| RB-19 | No actual V17 artifact exists | Tracked/worktree boundary scan | met |
| RB-20 | Science and authority remain unchanged/false | Science hash diff, capsule, and receipt assertions | met |
| RB-21 | Full/parity/static/privacy/site gates pass | Required local validation contract | met |
| RB-22 | Draft PR open, exact-head CI green, no merge | GitHub PR/check metadata | met |

No item may be marked `met` without concrete source or regression evidence. The
workstream cannot be reported complete while any row is partial, blocked, or not
started.

## Initial source-grounded diagnosis

- G1: `prepare_category3()` calls `HostRuntime.stage()` before secret access,
  provider launch, provider entry, or a `ProviderHandle`. `PackageStageRequest`
  therefore has no host target, while `PackageStageReceipt` nevertheless carries
  host acknowledgement, rehash, and upload fields.
- G2: the retained `t09_remote_runner.preflight()` validates the host, qualifies the
  image/runtime/browser/finalizer closure, publishes the full frozen manifest, and
  writes post-freeze admission. The shared controller calls those as three distinct
  operations but validates only a small synthetic freeze document.
- G3: `sira_gate_a_runtime` constructs an in-process `ProviderBudgetBoundary`, while
  the shared production wrapper constructs a second authoritative boundary around
  `ConditionEventObserver`. The remote runner has no request/reply admission stream,
  so post-hoc replay cannot provide before-effect admission.
- G4: `ProductionCategory3World.launch()` mutates only through retained
  `launch_campaign()` and `campaign_transport()`. `provider_launch()` is invoked
  only by the deterministic queued transport, creating a second protocol seam that
  a real package would be forced to implement without a live caller.

## Evidence log

- 2026-09-04: verified the exact remote, destination commit/tree/parents, merged PR
  #14 reviewed head, clean original checkout, branch/worktree absence, V3–V16-only
  registry, V16-consumed/V17-not-created goal, false authority/science fields, exact
  cumulative T09 cost, and retained zero-provider evidence without live inspection.
- 2026-09-04: created the fresh task worktree on
  `codex/t09-remote-execution-bridge`; starting tree is
  `e3cf777632400ec18736a34b6abec53d6d67de55`.
- 2026-09-04: exact-base deterministic state capsule and aggregate agent-check pass;
  registry completeness is 14/14 and all 16 production-wrapper shadow scenarios
  pass with zero real effects.
- 2026-09-04: immutable implementation commit
  `fe756d5debd89ae8613ca99b85e6d86df476cd9a`, tree
  `adc3ba68a9125955d36e7a096e902f3df4c29fd5`, added protocol v2 local
  assembly/host transfer, phase-specific retained host entrypoints, the canonical
  duplex supervisor/runtime client, one campaign-transport launch seam, the
  source-grounded 31-method/24-phase viability map, and integrated no-network
  conformance. Descendant commits only tightened regressions and the explicit null
  evidence binding for a failure before bridge construction.
- 2026-09-04: the 318-node focused controller, checkpoint, phase, duplex,
  conformance, viability, coupling, evidence, held-identity, authority, loader, and
  registry matrix passed. The live-shaped conformance used the shared controller
  and production assembly, local subprocess remote-runner entrypoints, a private
  Unix socket relay, runtime admission client, full retained manifest, four ordered
  condition sessions, raw/finalizer/evaluator fixtures, and cleanup with zero real
  external effects.
- 2026-09-04: marked incident
  `INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE` resolved only after the complete
  no-network remote bridge, coupling denial, channel-loss, replay, manifest-mutation,
  evidence-mutation, first-pair stop, and resumable-cleanup regressions passed.
- 2026-09-04: the first sealed-root generation attempts failed closed before
  publication because proof validation and aggregate agent-check did not resolve the
  viability receipt's repository-local method-schema reference. One offline local
  schema registry now serves every shared cross-file schema consumer. It registers
  only unique `$id` aliases, keeps historically reused execution-schema IDs
  unselectable as aliases, and requires exact-file selection for those historical
  schemas. Strict Ruff/mypy and the viability, duplex, host-phase, failure-envelope,
  and repository-validation regressions pass; no partial V16 root was published.
- 2026-09-04: an exact-name disposable generator candidate with executable incident
  repetitions disabled passed all remaining generation, topology, schema, and
  aggregate-binding gates with 29 receipts, then was destroyed. The final tracked
  root still requires the unchanged normal command with all incident regressions.
- 2026-09-04: full incident repetition exposed that an untracked synthetic
  successor's declarative registry entry cannot survive an `exec` into a fresh
  interpreter. Host-phase conformance now runs the tracked remote-runner entry point
  in a bounded forked child. The child inherits the exact already-selected registry,
  while the receipt proves five child processes, the tracked entry point, and the
  absence of any serialized contract override or default/latest selection.
- 2026-09-04: froze shared implementation ancestor
  `0e628694db56a90e1e1f4748c8c338d48baddbb2`, tree
  `d77c83be4d4495df9f1491e4dccdeb955d27a6de`. The unchanged normal generator
  executed all seven incident groups three times through its standalone,
  pre-topology agent-check, and post-topology agent-check paths, then atomically
  published 29 V16 receipts. A default capsule check then rejected that first root's
  explicit-selector target source, correctly preserving exact target equivalence.
  The root remains recoverable in descendant `8c8a2789ed1f5e52e18a358893c2b4819afd1e7d`.
- 2026-09-04: regenerated through the same normal command without a selector so the
  sealed target source is the successor-driven `goal-record`, matching the base
  convention and default consumer. That intermediate receipt control ancestor is
  `63f3306631d909e9bd161d473275c8621b3487d4`, tree
  `1e10b9a085a8121f32cb3d6709987546f0e9c827`; aggregate binding file SHA-256 is
  `77bd98899e51eb88422450c3c9d6c9b3007d6fe9decb75ba5b7f4850f2babd5d`.
  Receipt descendant `f9f8e8d9ee9f338beecb5d07aa61f17c19adf009` has sealed-root Git tree
  `33a051972b2790ff34740e58df7466536b3ac868`. The default deterministic capsule
  selects V16 from the goal and reports anti-shadow valid.
- 2026-09-04: the sealed viability receipt reports protocol `2.0.0`, 31 methods,
  24 ordered phases, zero unresolved methods, one launch mutation seam, synthetic
  successor compatibility, and zero real effects. The sealed remote bridge receipt
  reports five tracked-runner host-phase child processes, four duplex condition
  sessions, the shared controller/production assembly, one authoritative observer,
  complete transcript/evidence bindings, all failure probes passing, zero real
  effects, and USD `0.00` new cost. Both the retained legacy root and rebound V16
  package root validate in the generated topology.
- 2026-09-04: the first repository-wide validation after sealing exposed one
  duplicated schema dispatch: proof validation handled source-binding schemas
  `1.0.0` through `3.0.0`, while top-level repository validation independently
  handled only `1.0.0` and `2.0.0`. The shared exact-version resolver now owns all
  three mappings, both consumers use it, unknown versions fail without a latest
  fallback, and an exact three-generation regression covers the contract.
- 2026-09-05: the unchanged normal generator completed the final goal-selected V16
  rebind against immutable source commit
  `aeff713e46a75d513dd9ccbcb53586e3151fdfd6`, tree
  `a6a650de2c7d2611bb042789e8a359293f5ccd83`. It atomically published 29 receipts;
  aggregate binding file SHA-256 is
  `a5a3eaef846e2086d78b325fd764a74c76e62cd2f4425092c7d74300a68b802c`
  and aggregate binding semantic SHA-256 is
  `f6ce105a60df816a9311656db1d22124096f855334b79baab3fdf209e8af4aea`.
  Receipt descendant `410ada3e687e727410a063c6f1ddd444990122cc`, tree
  `67802e6836dde226807d734696937e1e2be277b3`, passes the default deterministic
  state capsule and full repository validation. The capsule selects V16 from the
  goal, reports bridge and viability conformance valid, keeps V17 not-created, and
  keeps authority and scientific interpretation false.
- 2026-09-05: final local formatting left all 226 files unchanged; Ruff, strict
  mypy across 91 source files, repository validation, aggregate agent-check,
  sequential state-capsule, registry-check, version-lint, all-registered
  composition, all-required shadow, and incident-check pass. Portable Quarto
  `1.9.38` renders all 16 pages and site validation passes. The aggregate agent
  check reports 14/14 registered contracts, 16/16 required shadow scenarios, 31
  live methods with zero gaps, 24 ordered phases, complete remote-bridge
  conformance, and zero real effects.
- 2026-09-05: `make test` completed naturally with 2,354 passed, 23 failed, and 5
  skipped in 3,718.51 seconds. The failures are inherited historical protocol and
  unavailable ignored-private-evidence nodes, not bridge regressions. A temporary
  archive of exact base `f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2` reproduced
  the six public EXP-0001 protocol failures byte-for-byte and was destroyed; the
  repository parity gate remains responsible for the complete two-sided
  classification. No historical science or private evidence was fabricated to make
  the raw full-suite command green.
- 2026-09-05: the first exact-base parity comparison reported zero newly failing
  nodes, zero missing base failures, and zero invalid outcome transitions. It
  nevertheless failed closed because the typed G1/G2 replacement had changed three
  collected parameter IDs. Explicit compatibility IDs now retain those exact base
  nodes while their assertions exercise local assembly, the stronger preflight
  predecessor, and the stronger qualification predecessor. All five current
  host-effect mutation cases pass.
- 2026-09-05: the fresh complete `ci-check` against exact base
  `f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2` passed on head
  `647fc84aa7c0bce418a33fb39ee852b020c452e7`. The base reported 27 failures;
  the head reported the 23 unchanged historical/private-evidence failures and four
  parity-sandbox environment/path nodes newly passing. The comparator reported zero
  newly failing nodes, zero missing base failures, zero missing collected base
  nodes, zero invalid outcome transitions, and five symmetric deselections for the
  unavailable private T09 evidence. Lock consistency, formatting, Ruff, strict
  mypy, aggregate agent-check, repository validation, Quarto `1.9.38` rendering of
  all 16 pages, site validation, and parity all passed.
- 2026-09-05: draft PR #15 is open against
  `phase-1/sira-pilot-autonomous-r2`, remains draft and unmerged, and has no
  auto-merge request. GitHub Actions run `33966412283`, job `101307218125`,
  completed successfully in 3h40m18s against exact implementation-evidence head
  `e6732bdfd0c40f3f249718fc9ec682d6c32cf1d1`. The deterministic agent/control
  gate and exact-base PR parity gate both passed; the non-PR strict-local branch
  was correctly skipped. This ledger closure is an evidence-only descendant and
  must itself receive the same exact-final-head local and hosted gates before
  handoff.
- 2026-09-05: direct Sol/max self-review found no route for host transfer before
  provider entry, no implicit qualification or freeze in preflight, no minimal
  substitute accepted by the full-manifest validator, no remote model or browser
  action without shared admission, no second authoritative remote accountant, no
  secondary provider launch seam, and no missing transcript binding in raw or
  essential-failure evidence. The source-grounded viability receipt confirms a
  package-only successor can map all 31 live methods and 24 shared phases without
  another shared-control edit.

## Decisions and blockers

- The governing request prohibits delegation. Direct Sol/max self-review replaces
  the assembly workflow's usual subagent review; independent exact-head review is a
  later external gate.
- Temporary local subprocesses and private IPC are permitted only in isolated
  network-disabled tests. No real credential, cloud inspection/mutation, SSH,
  Docker, browser, SiRA, evaluator, or scientific condition is permitted.
- No irreducible blocker is currently known.

## Review 5122766860 repair attempt — blocked

The last statement above describes the historical implementation handoff. This
append-only review entry supersedes its readiness claim, without relabelling the
historical Sol/max worker attestations or rewriting any prior evidence.

Worker: **operator-attested GPT 6 Astra / high**. Runtime metadata was not
introspected. No implementation, testing, review, architecture, Git, or scientific
work was delegated. This is Category 1 only, with no merge or execution authority.

Before mutation, read-only checks matched repository `abbudjoe/gic-lab`, PR #15,
branch `codex/t09-remote-execution-bridge`, the designated clean task worktree,
local/tracking/remote/PR head `a98b4b875ab4d101709d62bc7222b5c90681a893`, head
tree `b75ce4579c934440c7679cbf289b3294d01d6caf`, base
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`, and base tree
`e3cf777632400ec18736a34b6abec53d6d67de55`. PR #15 was open, draft, unmerged,
and had no auto-merge request. Run `33977310188`, job `101336174251`, both
reported success for the exact reviewed head. Review `5122766860` was read in
full. No actual successor artifact was found in the task tree. Repository authority
was false; retained resource state was inspected without a live provider query.

The pre-edit `make state-capsule` passed, semantic SHA-256
`25ab78bf1f48354201259e8b264abcc118cdcb3a76699f0eb5ae824b919387b4`.
Its component-derived completeness flags are the historical claims under review,
not evidence that R1–R6 have been repaired. The separately started `make agent-check`
is not reusable as final validation of this work. No final validation cycle, receipt
generation, implementation freeze, Git commit, push, or PR publication is claimed.

### R1–R6 evidence index

Unless qualified below, node references are in `tests/control/test_remote_transaction_review.py`.
The baseline column preserves the reviewed-source observations; repair and node
columns include the explicit-fixture continuation. No finding is closed.

| Finding | Failing-at-reviewed-head evidence | Source repair | Active regression node IDs | Joined coverage | Remaining limitation |
|---|---|---|---|---|---|
| R1 | With accumulated prior IDs, one fresh runtime subprocess succeeds and the second is rejected; observed `CALL-T09-00000001` is reused. Terminal lookup then masks admission failure with `KeyError`. | Candidate: actual factory asks the port for immutable session-derived IDs; both peers check scope/sequence; preserve admission exception. | `test_r1_fresh_runtime_processes_preserve_campaign_call_history`; `tests/control/test_remote_bridge.py::test_remote_call_scope_is_checked_at_each_peer_before_send` | None | Four fresh processes now pass with carried prior IDs, but the shared-controller transaction, complete replay matrix and all failure-envelope ID bindings remain unproven. |
| R2 | Continuation, before terminal source edits: four `condition_session` cases fail at exact answer equality: two digest substitutions, None replaced by digest, partial answer discarded on nonzero exit. | Candidate: `retained_condition_completion` validates the raw seal, derives source completion/answer/error, validates exit evidence and writes a separate bound artifact. | `tests/control/test_remote_terminal_review.py::test_r2_actual_host_terminal_preserves_session_answer`, four parameter cases | None | Terminal unit cases pass. Admission/runtime inputs and the terminal capture are substituted in this characterization. Shared no-answer acceptance, mutation matrix, finalizer/evaluator chain and failure-envelope preservation remain unproven. |
| R3 | Candidate source binding `5f78002153c0c9c1137dbd92430e3027d8552a39f93dd5cc9aee37992ed3d6a6`: shared controller accepts retained transfer/preflight, then an injected qualification-start failure reaches actual external cleanup, which rejects the preflight predecessor instead of cleaning. Both cleanup functions are AST-identical to reviewed head. | Partial: latest predecessor and durable journal validation; exact-owned staging cleanup; explicit fresh sealing-probe evidence root outside mutation-intent discovery. | `tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[qualification-start-failure]`; `tests/control/test_remote_host_phases.py::test_cleanup_predecessor_does_not_require_freeze`; `test_cleanup_cannot_omit_acknowledged_transfer`; `tests/control/test_remote_terminal_review.py::test_retained_source_archive_cleanup_preserves_exact_ownership`; `tests/control/test_candidate_inputs.py::test_retained_sealing_probe_does_not_publish_container_mutation_authority`; `test_sealing_probe_failure_preserves_separate_evidence` | Earlier preflight-start and qualification-start faults; current contained transaction also passes actual post-freeze cleanup and provider closeout after its first shared condition entry fails | Other joined lifecycle cells, root/credential ownership, and the complete resume matrix remain unproven. Component tests reject missing/contradictory publication; earlier partial-publication failures stayed unresolved. Complete lifecycle fault/resume matrix is still missing. |
| R4 | Reviewed source aggregates independent components. New external preflight/qualification component regressions also reject a provider-entry input that actual orchestration requires; both validator functions were AST-identical to reviewed head before repair. Missing historical archive/source bindings were prerequisites, not behavioral proof. | Explicit archive/candidate/environment seams and exact input rechecks; shared freeze now selects the actual runtime-contract hash (the reviewed code selected the provider-profile hash). No integrated conformance success receipt. | Existing archive/candidate boundary nodes; `tests/control/test_remote_host_phases.py::test_external_generated_outputs_retain_required_provider_entry[host-preflight]` and `[host-qualify]`; active candidate `[transaction]` remains failing during wiring. | One contained controller transaction passes retained transfer/preflight/qualification/full freeze and reaches first shared condition entry; retained cleanup/provider closeout pass after the unimplemented runtime operation fails | No four-condition campaign, runtime/finalizer/evaluator/checkpoint chain, or phase mutation matrix. Historical source-pin conflict remains historical-only; candidate input propagation is authorized and in progress. |
| R5 | All 12 endpoint/relay pipe/socket cases block past a 0.10-second deadline; watchdog reaps each child before the behavioral assertion fails. | Candidate: nonblocking partial reads/writes with deadlines, EAGAIN/EINTR handling, cancellable accept/relay worker; bounded subprocess diagnostic read and reaping. | `test_r5_write_deadline_includes_kernel_backpressure`, all parameters below; `test_r5_maximum_frame_survives_partial_io_eintr_eagain_exactly_once[endpoint]` and `[relay]` | None | Primitive backpressure and exact maximum-frame tests pass. Full-controller timeout accounting, terminal acknowledgement interruption, cleanup and worker/fd release are not established. |
| R6 | Actual retained factory/EventWriter wrote 1,210 unadmitted bytes with aggregate output headroom exhausted; intended assertion failed twice on the dirty candidate. Pre-repair EventWriter AST was identical to reviewed head; factory included earlier R1 repair. | Partial: shared accountant output reservation distinct from observation; duplex allocation and retained event writer before-growth admission. | `tests/control/test_remote_transaction_review.py::test_r6_runtime_event_writer_cannot_grow_without_shared_output_headroom`; `tests/control/test_remote_bridge.py::test_output_allowance_is_shared_and_distinct_from_observed_usage`; `tests/control/test_remote_bridge.py::test_actual_event_writer_reconciles_exact_bytes_after_shared_grant` | None | Denied event bytes now prevented and event totals reconcile. Runtime logs, bridge journals, failure evidence, cleanup reserve and complete transaction reconciliation remain incomplete. |

Exact R5 parameter IDs (each appended to the node above):

```text
[never-reads-endpoint-pipe]
[never-reads-endpoint-unix-socket]
[never-reads-relay-to-shared-pipe]
[never-reads-relay-to-shared-unix-socket]
[never-reads-relay-to-remote-pipe]
[never-reads-relay-to-remote-unix-socket]
[stops-mid-frame-endpoint-pipe]
[stops-mid-frame-endpoint-unix-socket]
[stops-mid-frame-relay-to-shared-pipe]
[stops-mid-frame-relay-to-shared-unix-socket]
[stops-mid-frame-relay-to-remote-pipe]
[stops-mid-frame-relay-to-remote-unix-socket]
```

Commands run with working source explicitly selected:

```text
PYTHONPATH=src uv run --no-sync pytest tests/control/test_remote_transaction_review.py -k r1 --tb=short
PYTHONPATH=src uv run --no-sync pytest tests/control/test_remote_transaction_review.py -k r5 --tb=short
PYTHONPATH=src uv run --no-sync pytest tests/control/test_remote_transaction_review.py -k substitute_historical_archive --tb=short
```

Initial results were respectively 1 failed (intended four-condition assertion;
only one succeeded), 12 failed (intended deadline-return assertions), and 1 passed
(the source-bound archive validator correctly rejects substitution). These are not
import, missing-fixture, network-denial, skip, or xfail results. The archive test is
not counted as a red R4 regression or as successful qualification.

### Seam map at the blocked boundary

This is an inventory of executed characterization seams and the unbuilt joined
wiring, not a receipt of integrated execution.

| Required retained implementation | Actual execution here | Environmental substitution | Observable evidence |
|---|---|---|---|
| Shared controller and production assembly | Not joined to retained phases | None added | No integrated campaign identity or receipt exists. |
| Retained host phase external orchestration | Source inspected; not executed end to end | None added | Qualification archive prerequisite identified below. |
| `_install_locked_llm_factory` → `DuplexSupervisorPort` → `_ConditionSessionBridge` → shared `_AccountingObserver` | Existing local subprocess probe, with prior IDs carried between observers | Existing upstream LLM/browser stand-ins and local IPC | First condition terminalizes; second collides. This does not establish shared-controller accounting. |
| `condition_session` terminal derivation and downstream finalizer/evaluator | Not exercised | None added | No real-answer preservation claim. |
| `FramedDuplexEndpoint.write_event` / `CanonicalFrameRelay._write_packet` | Actual primitives in child processes | Pipe/socket peers that never read or stop mid-frame | Parent receives no deadline result within 0.8 seconds and reaps the child. |
| `stage_verified_archive` | Actual retained descriptor-based size/hash checks | Same-size synthetic source bytes only; expected identity is unchanged | Rejects at `archive staging source hash drifted`, before destination creation. |
| Retained checkpoint, cleanup and authority terminalization | Not joined | None added | All corresponding acceptance requirements remain unproven. |

### Material blocker and stopped state

`_live_host_qualification` calls `stage_verified_archive` with retained constants,
then `qualified_real_evidence_regression`, which independently invokes
`validate_private_regression_archive`. The exact archive has 3,439,137 bytes and
SHA-256 `63ed19b35bcb4cb62c3796a80a48004937340eb3826f9657a1006e251772255d`.
The historical public receipt is not the archive. No candidate archive was found
in either inspected repository tree or at the retained canonical location.

The retained staging primitive hashes the actual descriptor bytes. A same-size
fixture fails that invariant before publication. Replacing the expected hash or
returning a successful qualification receipt would cross the task's prohibition
on weakening bindings or substituting successful outputs above the environmental
seam. Existing component tests that patch archive constants do not satisfy this
joined-transaction contract.

The narrow missing capability is access to those exact archive bytes, or an
explicitly approved fixture-binding contract for this prerequisite. This is a
source/fixture feasibility blocker, not a claim that a joined controller run
reached qualification, and not proof that resolving it will satisfy every later
requirement. No future shared repair is declared impossible.

The new open incident is `INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW`; earlier
incidents and sealed roots are untouched. Goal/state projections now identify the
blocker. Schemas admit that new incident and blocked status; no success criterion
or science/budget contract was relaxed. Stored conformance, method-map, viability,
source-binding and aggregate-binding artifacts are unchanged historical evidence;
they have not been rebound or accepted as current repair evidence.

Terminal state: `t09_remote_execution_bridge_review_repair_blocked`.

Final local characterization rerun (same module, no `-k`): **13 failed, 1 passed
in 35.61 seconds**. The R1 failure includes the original shared-observer
`AdapterFailure('condition model-call identity or immutable routing drifted')`
before the remote timeout and masking `KeyError`. The twelve R5 failures remain
at the bounded-return assertion. There are no new skips or xfails.

The overlapping pre-repair `make agent-check` ended with
`TargetSelectionError: selected-runtime target differs from goal/package state`
after the goal was updated during its execution. This is invalidated evidence,
not an inherited exact-head failure or a passed gate. Incident-document validation
and direct blocked-capsule schema validation pass with all supplied completeness
flags false. The schema rejects either viability or remote integration marked true
in this blocked state. Those checks are structural diagnostics, not aggregate gate
evidence. No raw full-suite, parity, site or final gate result is claimed.

Direct operator-attested Astra/high self-review, without independent approval:

1. Fresh runtime processes do **not** yet have noncolliding campaign IDs: the R1
   regression demonstrates rejection in the second process.
2. Actual answer/absence preservation is **not established**: retained
   `condition_session` still substitutes the raw-manifest digest.
3. Pre-freeze cleanup is **not established**: `_live_host_cleanup` and
   `validate_host_cleanup_phase` still require freeze.
4. One controller driving the actual retained transaction is **not established**:
   no joined harness was completed; `run_remote_execution_bridge_conformance`
   remains component composition.
5. Bounded stalled-peer exit is **false on the tested paths**: all R5 primitive
   backpressure cases fail; parent watchdogs reap their children.
6. Before-growth output containment is **not established**: runtime `run` still
   reconciles output after writes.
7. The historical completeness claims are **not supported as current readiness**:
   the open incident and blocked projections supersede them. Existing stored
   method/receipt artifacts remain unchanged and cannot close this review.

No implementation ancestor or receipt/document descendant was committed. The task
worktree intentionally retains uncommitted blocked-handoff changes and red tests.
No PR body/comment was published, no Git push occurred, and no new CI run is claimed.

Final read-only checks reconfirmed unchanged local/remote/PR head and tree, the
exact base, open/draft/unmerged PR state and disabled auto-merge. The only hosted
CI evidence remains the reviewed run/job above. No task test processes remain.
The characterization and bridge temporary directories are gone; one unrelated
conformance directory predating this turn was inspected, contains no successor
artifact, and was left untouched. `git diff --exit-code HEAD -- experiments
manifests src containers` passes: science, costs, historical evidence and production
sources are unchanged. Targeted test formatting/lint and `git diff --check` pass.

Complete local changed-file inventory:

```text
control/goals/EXP-0001.yaml
control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json
docs/PROJECT_STATE.yaml
docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md
schemas/agent-incident.schema.json
schemas/agent-state-capsule.schema.json
tests/control/test_remote_transaction_review.py
```

New incident file SHA-256:
`eb68e92f0cc54a344beab1fc995ad540e3d7bfad257f7983c5f550c15c2b5142`.
Its immutable-facts SHA-256 is
`8e1f4f11d063f342697da5a0ed1e1d91a9b1be4e3b97c03dc0f6cb1a05c07d22`.
No updated conformance, viability, source-binding or aggregate-binding hash exists.

### Explicit offline-fixture continuation (work in progress)

The operator authorized the separate deterministic input lane and preservation of
the seven-file local delta. Worker setting: operator-attested GPT 6 Astra/high;
runtime metadata not introspected; no delegation. The earlier blocked handoff
above is retained as history. The archive limitation no longer blocks independent
repair work; it still prevents historical replay.

Read-only identity checks before edits reconfirmed base
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2` / tree
`e3cf777632400ec18736a34b6abec53d6d67de55`, and local/tracking/remote/PR head
`a98b4b875ab4d101709d62bc7222b5c90681a893` / tree
`b75ce4579c934440c7679cbf289b3294d01d6caf`. PR #15 remained open, draft,
unmerged, with auto-merge disabled. Review 5122766860 was read. CI
33977310188 / job 101336174251 remains evidence for that committed head only.
No actual successor artifact or live authority was found.

The seven paths listed in the preceding inventory exactly matched the reported
characterization and blocked-state delta. The index was empty, and production
and scientific sources were unchanged. Before edits, a task-owned private
`/tmp/t09-pr15-resume-o412q9ld` snapshot preserved those files, the staged and
unstaged diffs, status and byte/SHA inventory. Directory mode 0700, file modes
0600, bounded below 2 MiB, with fsync and byte-for-byte readback verification.
Inventory SHA-256:
`6a3597adedbfec4eb0ba138ccb354077683b0b7177141f4697ea6c9cb038c1c7`.
The starting source under test is the committed head plus this exact delta:

| Path | Bytes | SHA-256 |
|---|---:|---|
| `control/goals/EXP-0001.yaml` | 3136 | `ef4aa4ac6b307a487e5361f9f5e4ae9bf0e3ee2c3a41dfdb3dc14350319d88ed` |
| `control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json` | 3655 | `eb68e92f0cc54a344beab1fc995ad540e3d7bfad257f7983c5f550c15c2b5142` |
| `docs/PROJECT_STATE.yaml` | 24626 | `428945c5a2359a051839c877f4b2be93955e6b03205e13c447b6762b003ec24a` |
| `docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md` | 29434 | `09e3118d39609b7088285159a11d501e1b06e95249907106a6cf9f2970948740` |
| `schemas/agent-incident.schema.json` | 14597 | `f4a458565d6560654300658878e6a2bf09e647322a7ad0ebc56a686a2c024a0f` |
| `schemas/agent-state-capsule.schema.json` | 12050 | `eddc056fe270d5813d6fbcea70d4cf74c44ec15c427584aa7c6c949564f0d473` |
| `tests/control/test_remote_transaction_review.py` | 7776 | `f3ad569b4ba70dd80abb9e85867d64d9e688553f5489cecf7fcfd7dc747cafc2` |

The unchanged characterization rerun produced **13 failed, 1 passed in 35.57s**,
at the same R1 and twelve R5 assertions. After scoped session IDs and nonblocking
partial I/O, the same module produced **14 passed in 3.05s**. Existing bridge and
runtime tests produced **41 passed in 0.95s**. Initial fixture-boundary and expanded
peer-validation tests produced **37 passed in 0.61s**. These are focused component
results, not an integrated transaction or final validation cycle. R1/R5 remain
open pending their complete acceptance evidence; R2–R4/R6 remain unproven.

The historical archive role is the qualification/regression input staged by
`_live_host_qualification` using `stage_verified_archive`, then consumed by
`qualified_real_evidence_regression` and `t09_real_evidence_regression.run`.
It is distinct from the image archive, source-package tar, and source manifest.
The regression consumer requires eleven exact raw member names, one session under
`sira-output/`, and separate `attempt-outcome.json` / `evidence-index.json`
comparison records. Its historical oracle asserts 52 model calls, 13 browser
actions, task completion, answer presence, and valid score 0.0. The unavailable
3,439,137-byte archive and its original SHA remain unchanged requirements for
historical replay. Historical replay: **not run, required archive unavailable**.

The new fixture builder selects six tracked raw-shape fixture files and explicit
test records, with fixed USTAR metadata, sorted members and fixed gzip metadata.
The immutable in-process binding is passed explicitly to retained staging; the
normal CLI has no flag, environment selector, document capability, or fallback
for this dependency. Actual size/hash/copy/publication validation executes. The
fixture does not claim historical replay or live image/runtime qualification.
Qualification consumption and the joined campaign are still being wired; no
success receipt, new implementation ancestor, PR publication or CI result exists.

### Continuation fixture identities (component evidence only)

Fixture ID: `T09-OFFLINE-QUALIFICATION-FIXTURE-1`. Archive: **2034 bytes**, SHA-256
`284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb`. Generator `src/giclab/harness/t09_qualification_fixture.py` SHA-256
`ba4d8e8361cbec8d0e3b8055f8a4f9175ae42fc49cef737be401a560fd6f27dd`. Classification: non-scientific, no-network, non-live.

The archive has no ignored binary dependency. Two fresh builds use the same
fixed serialization; the archive is not padded to the historical size. Source
inputs and decoded member identities are listed below. These identify bytes,
not a successful joined transaction or a historical/runtime-real qualification.

| Source fixture | Bytes | SHA-256 |
|---|---:|---|
| `tests/fixtures/t09/finalizer-raw-shape/host-cleanup-receipt.json` | 400 | `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` |
| `tests/fixtures/t09/finalizer-raw-shape/normalized-events.jsonl` | 855 | `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` |
| `tests/fixtures/t09/finalizer-raw-shape/provider-budget.json` | 435 | `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` |
| `tests/fixtures/t09/finalizer-raw-shape/provider-call-lifecycle.json` | 2453 | `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` |
| `tests/fixtures/t09/finalizer-raw-shape/runtime-environment.json` | 220 | `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` |
| `tests/fixtures/t09/finalizer-raw-shape/sira-output/PRIVACY-SAFE-FINALIZER-FIXTURE.json` | 318 | `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` |
| `tests/fixtures/t09/fanout-two-task-fixture.json` | 4941 | `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9` |
| `tests/fixtures/t09/pinned-evaluator/evaluator.py` | 6776 | `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` |
| `tests/fixtures/t09/pinned-evaluator/run.py` | 1537 | `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` |
| `tests/fixtures/t09/pinned-evaluator/utils/helpers.py` | 1892 | `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` |
| `tests/fixtures/t09/pinned-evaluator/utils/norm.py` | 1897 | `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` |
| `tests/fixtures/t09/pinned-evaluator/utils/models.py` | 1092 | `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` |

| Archive member | Decoded bytes | SHA-256 |
|---|---:|---|
| `attempt-outcome.json` | 114 | `c92fe28b1d0985a2f9ce49b2224bcccd61009ae89eb23316980571a85defcfa7` |
| `attempt-wall.json` | 72 | `7d49e2b38edd510c39f2870eff79b48679d8c1f17a820f7b08f243b9d6993c34` |
| `condition.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `condition.stdout` | 21 | `bb8f1608282d064b6c6daf04b940f9205305eaf6811f128a849849d976445921` |
| `container-command.json` | 75 | `f15be9880d562c063aeff49ed48cd47df4bf79b9de248e1c9e67632055dbba83` |
| `container-state.json` | 43 | `42db5c6e598f27c3c334867d07cd2f4aa58dd3e9bd98643c6d210fdfe7873cc4` |
| `evidence-index.json` | 107 | `2d9d16cb498bf4e01229694a419bbeb808265660feb3818defc2cf9c265e0b69` |
| `gpu-accounting.json` | 26 | `290937ecc562ab95c8ad1c28b39f785feb7f772c87fc9edace5ac4a101333f66` |
| `host-cleanup-receipt.json` | 400 | `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` |
| `normalized-events.jsonl` | 855 | `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` |
| `provider-budget.json` | 435 | `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` |
| `provider-call-lifecycle.json` | 2453 | `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` |
| `runtime-cleanup.json` | 86 | `c673d4cc437f53efee7e44cb473b81d400d772b600cbc5c96ab940f0e0c79818` |
| `runtime-environment.json` | 220 | `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` |
| `sira-output/PRIVACY-SAFE-FINALIZER-FIXTURE.json` | 318 | `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` |

All fixture nodes are in `tests/control/test_qualification_fixture.py`:

- `test_two_fresh_fixture_builds_are_byte_exact`
- `test_retained_staging_copies_exact_bound_fixture`
- `test_fixture_mutation_fails_before_publication` (five parameter cases)
- `test_historical_selector_cannot_fall_back_to_fixture`
- `test_staging_short_circuit_cannot_supply_a_fixture_success`
- `test_fixture_uses_retained_extraction_and_semantic_validation`
- `test_retained_qualification_consumes_real_staging_and_fixture_regression`

The last component substitutes only its container executor (`run_logged`) and
passes the typed binding directly to the real retained regression consumer. It
runs the actual bounded member extractor and retained semantic finalizer on the
tracked evaluator fixtures, with network calls denied. It does not run the full
`_live_host_qualification` orchestration or its subprocess CLI. Its first attempt
failed on absent pilot-state setup; that was a test prerequisite error, not a
behavioral characterization. After using the existing state initializer, it
passes. No fake staging or qualified semantic receipt is supplied.

The complete mandatory fixture-boundary matrix is **not established**: joined
phase-mutation sensitivity, whole-harness forbidden-effect counters and joined
transcript provenance remain absent. No fixture-success receipt is promoted to
conformance. The generated archive and test directories are removed by their
temporary-directory owners; no temporary successor package was created.

### Source-package binding blocker and preserved stop

The retained `verify_package` is called by both `_live_host_preflight` and
`_live_host_qualification`. After the clean package/execution checks it loads the
selected runtime identity's `repository_instrumentation.files` and compares each
expected SHA with the actual source bytes. The explicit archive binding does not
participate in this check. The V16 runtime identity file is
`experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_RUNTIME_IDENTITY_V16.json`,
SHA-256 `ab4c2f8a93d235c0c00fc24b4d6d10657528b1de9bee656ba611e3311f6fd1f2`.
Eight source pins already disagree with the exact reviewed commit, before these
repair edits:

| Instrumentation source | Frozen V16 SHA-256 | Reviewed-head SHA-256 |
|---|---|---|
| `src/giclab/harness/sira_gate_a_runtime.py` | `0f1cd94fe048102704c9a4c461c6a3bf457ca53eb5586291441a675cd6b256a0` | `7ff27906f6d1e8f83f434ad0dbae7800958cb18d5d01f56fa77b7f13b1560df6` |
| `src/giclab/harness/t09_sira_pilot.py` | `6e0574bddbb1585399ed9c19531b9191b571c483621a3585abe3c40d38a6c017` | `7b197e0ed4b0cea214a8a27306616f0827b1e09e04ab003b73c4ee76dc390aa9` |
| `src/giclab/harness/t09_pragmatic_provider.py` | `8ac3b563842ab994e86c96921e46e292195a8e8c9962165cfe22d8b0a5f1294f` | `f406a40a5b800dbe19335d818e9e524f7bf0533c1b421091aaf85f6b144da512` |
| `src/giclab/harness/t09_provider_contracts.py` | `9c3ad548894c3ea52b151524d265cd158a10733d62183bd763aec33d116b615c` | `024dbcfa3c343539fafb474fe48ffcf0fd6b5012746919fd35df4f89fb71210c` |
| `containers/sira-smoke/pragmatic/t09_remote_runner.py` | `ff7bbe48e2f790282a3cb012184653da237801433947391009b4df1f0225269e` | `39a6216acb02ebc86e1e1a07c4db5d4cb2562ba8bcda9acb29787f1941b7d6ef` |
| `src/giclab/harness/t09_model_metadata_receipt.py` | `88e39033963378454cfcb14f0d8d19dda1c72dc779e24696313f008e707363b5` | `6ec6810ce5c0cad1d5a8fe7470c1f70d9d6449f56289f2e7edb8ff9813df404b` |
| `containers/sira-smoke/pragmatic/t09_freeze_commands.py` | `4b593f68a45eccbe8e78df6192508e689448b7d61a41faa622e2ab191e4656ff` | `45460760c3ee12e834c995d62e2b368e3ba8c55947fc75758be4324b096b0795` |
| `src/giclab/harness/t09_cleanup_state.py` | `39a4d698b8184c4d6652294f32e07911b2998b1a6326ad280353ba5f505e387e` | `97163a2508680fbb1a766d23bd542b4feb242cd0037f146ee715b0fc96d7d711` |

This is not local/remote/PR Git identity drift: all still point to the reviewed
head. It is a source-package prerequisite incompatibility inside the retained
verifier. The comparison was made using `git show <reviewed-head>:<path>` and the
unchanged tracked runtime identity, not a missing-archive test or a fabricated
clean-checkout/qualification receipt. No joined behavioral R4 failure is claimed.

`generate_source_binding_receipt` in `src/giclab/control/proofs.py` records
`scope: shared-control-plane-only` and `historical_package_changed: false`.
The normal receipt generator does not rebind the historical runtime identity
consumed by `verify_package`. The selected V16 contract also declares
`package_transition_policy=NONE`. The supported downstream `current_commit`
exception does not select current instrumentation for the runtime factory and is
not used by these phase entrypoints.

Passing the repaired runtime through this verifier needs a separately defined
**test-only source-package binding** for the implementation under test. That is a
different input role from the historical regression archive. The continuation
expressly authorizes the archive binding and keeps historical/frozen inputs and
normal acceptance unchanged; it does not define this source-package rebind.
Changing the V16 runtime/execution contracts, bypassing `verify_package`, or
accepting arbitrary source hashes would cross that boundary. No such change was
made. This is the narrow outstanding decision; it is not a request for live
qualification, new version, or general fixture framework, nor a claim that any
future shared repair is impossible.

The joined harness was not completed. No full-controller pre-freeze cleanup cell,
no-answer/scoring chain, timeout cleanup cell, or actual writer output-denial cell
is established. R3 and R6 remain source observations only. All six findings and
readiness remain unresolved. The source work here is a candidate repair, not an
accepted implementation ancestor.

Focused validation after the final source edits:

- `PYTHONPATH=src uv run --no-sync pytest tests/control/test_remote_transaction_review.py tests/control/test_remote_terminal_review.py tests/control/test_qualification_fixture.py tests/control/test_remote_bridge.py tests/test_sira_gate_a.py --tb=short`: **80 passed in 5.36s**, no skip/xfail.
- Targeted Ruff formatting and lint pass for the eleven edited/new source/test files.
- Targeted strict mypy passes for the five edited/new package modules. An initial
  optional-stderr typing error was fixed by retaining the narrowed stream; it is
  not an inherited failure.
- Open-incident schema, immutable-facts hash and reference validation pass.
- `experiments/` and `manifests/` are byte-identical to HEAD. Historical archive
  pins, frozen model/tier/data/task/order/score/retry/interpretation/cost inputs are
  unchanged. The exact canonical historical archive remains absent.

These were focused diagnostics, not the final required `make` validation cycle.
No final format/lint/typecheck/validate/agent-check/test/site/ci-check result is
claimed. Raw full-suite and parity were not rerun; the earlier historical raw
suite result (23 failures, 5 skips) is not evidence for this delta. There is no new
CI result, conformance receipt, viability receipt, source-binding or aggregate
binding. Their stored historical hashes were not edited.

Direct operator-attested Astra/high review of the stop (no delegation, not
independent approval):

1. Four fresh runtime clients now produce distinct session-derived IDs with prior
   history in the component probe. One shared-controller campaign is unproven.
2. Actual host terminal unit logic now preserves two distinct answers, None and a
   partial answer with nonzero exit. Downstream agreement and no-answer acceptance
   remain unproven; `ProductionCategory3World.run` still rejects exit-zero
   `completed=False`, and the shared observer constrains completed answer/error.
3. Pre-freeze terminal cleanup remains unproven and unrepaired.
4. No single joined retained-path controller transaction is available.
5. Twelve pipe/socket backpressure cases and two maximum-size partial-I/O cases
   pass. Full-controller cancellation/accounting/cleanup remains unproven.
6. Actual before-growth output admission remains unimplemented and unproven.
7. Historical completeness claims remain superseded by the open incident and
   blocked current projections; component passes cannot establish readiness.

No commit, push, PR body/comment publication, merge, ready-state change, branch
creation, worktree creation or auto-merge occurred. No new version, V17 or
AUTONOMOUS-0010 artifact, live authority, provider/model cost or real external
effect was created. The original seven-file snapshot remains preserved. The task
worktree intentionally retains the explained source/test/document delta and an
empty index; it is not clean and is not a successful terminal handoff.

Terminal state: `t09_remote_execution_bridge_review_repair_blocked`.

Complete preserved continuation changed-file list:

```text
containers/sira-smoke/pragmatic/t09_real_evidence_regression.py
containers/sira-smoke/pragmatic/t09_remote_runner.py
control/goals/EXP-0001.yaml
docs/PROJECT_STATE.yaml
docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md
schemas/agent-incident.schema.json
schemas/agent-state-capsule.schema.json
src/giclab/control/remote_bridge.py
src/giclab/control/remote_execution_conformance.py
src/giclab/harness/sira_gate_a_runtime.py
src/giclab/harness/t09_runtime_admission.py
tests/control/test_remote_bridge.py
control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json
src/giclab/harness/t09_qualification_fixture.py
tests/control/test_qualification_fixture.py
tests/control/test_remote_terminal_review.py
tests/control/test_remote_transaction_review.py
```

Initial snapshot inventory hash reverified unchanged. The final WIP inventory is
retained privately beside it as `continuation-inventory.json`; it identifies the
committed head plus the uncommitted source/test/document delta, not a new Git tree.

## Candidate source-package continuation — preservation checkpoint

The operator explicitly authorized the offline candidate source-package binding.
The earlier source-pin decision blocker is superseded by this permission; its
observations above remain historical. Category 1 only; operator-attested GPT 6
Astra/high, runtime metadata not introspected, no delegation.

Local/tracking/remote/PR head remains `a98b4b875ab4d101709d62bc7222b5c90681a893`, tree
`b75ce4579c934440c7679cbf289b3294d01d6caf`. Destination/base remains
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`, base tree
`e3cf777632400ec18736a34b6abec53d6d67de55`. PR #15 remains open, draft,
unmerged, auto-merge null. Review 5122766860 was re-read at its exact head.
The empty index and exactly 17 continuation paths match the prior local inventory
`421e5a17b7b3f440e5d64b4f8fc7184a4ff2a00e34363fc85813e59dedb7f478`.
No experiment/manifest delta or actual successor-version/authority artifact was found.

Before edits, a new private task-owned snapshot was made outside Git using bounded
regular-file/no-follow reads, exclusive copies, before/after descriptor identity
checks and readback hashes. Its inventory SHA-256 is
`40934a7ee935ea0de7b27366e54626b6835d0553b1c44eb9ca317940e0a6864b`;
total source/test/document bytes: 1,631,663. The private locator is retained with
local task evidence. The original seven-file snapshot remains present and was not
modified. Starting identity means this inventory plus committed HEAD, not HEAD alone.

| Starting path | Type/mode | Bytes | SHA-256 |
|---|---|---:|---|
| `containers/sira-smoke/pragmatic/t09_real_evidence_regression.py` | regular / 0o644 | 24533 | `3e2896f88b3cb011b6970e4fc44057d97ca354ea552b5a686ec889d59637ab6c` |
| `containers/sira-smoke/pragmatic/t09_remote_runner.py` | regular / 0o644 | 1169602 | `5b3d72cb196c393a1c26289878d860c68366647496f4a8864deaad877b054023` |
| `control/goals/EXP-0001.yaml` | regular / 0o644 | 3303 | `b34d625389215ae4320f651b7aff3bd4b8e7f8a89472a985527446e7aeb7449d` |
| `control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json` | regular / 0o644 | 4306 | `a25884b25b06b706b43d15570c6b19322ed3a5d60fda713e4fee467e9d9899e4` |
| `docs/PROJECT_STATE.yaml` | regular / 0o644 | 24881 | `ed0544072353b0afb45c6ebbcf71469b9b6d40ce47c0c77155bc1f056c8e5092` |
| `docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md` | regular / 0o644 | 49363 | `f9864768c3da4720a2cf3c9ccd635af06998934a73ed2175119ce00610a99bb8` |
| `schemas/agent-incident.schema.json` | regular / 0o644 | 14597 | `f4a458565d6560654300658878e6a2bf09e647322a7ad0ebc56a686a2c024a0f` |
| `schemas/agent-state-capsule.schema.json` | regular / 0o644 | 12050 | `eddc056fe270d5813d6fbcea70d4cf74c44ec15c427584aa7c6c949564f0d473` |
| `src/giclab/control/remote_bridge.py` | regular / 0o644 | 104098 | `708e24064767cd625deef8d5e9181430b0b85a1feefb9345bc20d277b3ca8381` |
| `src/giclab/control/remote_execution_conformance.py` | regular / 0o644 | 61359 | `265da733dcb6d27c23b9e853de2c905ec33721d28d87e72cc1c3751995aac300` |
| `src/giclab/harness/sira_gate_a_runtime.py` | regular / 0o644 | 56123 | `2ff3e50f4e45cea89cb17749205028afdf4e145534a6bc696662496c32df6b34` |
| `src/giclab/harness/t09_qualification_fixture.py` | regular / 0o644 | 10709 | `ba4d8e8361cbec8d0e3b8055f8a4f9175ae42fc49cef737be401a560fd6f27dd` |
| `src/giclab/harness/t09_runtime_admission.py` | regular / 0o644 | 31587 | `6ef3c8f00904124cddd486de9775df8f6ee43d930708fe026a4e778bb3efb52f` |
| `tests/control/test_qualification_fixture.py` | regular / 0o644 | 9186 | `ba6a5451144ae486cbc661f2d827aa3f6e7cf27bd5a904be756d1c318d87e81d` |
| `tests/control/test_remote_bridge.py` | regular / 0o644 | 39272 | `cae80d354235971d6d249325af32151539adb58e504d31ab9a947c64ecc4db9d` |
| `tests/control/test_remote_terminal_review.py` | regular / 0o644 | 5042 | `6ace5c168377b8129d5975fe056c041ccdd44bb552ffffe49758102fd9adcf3f` |
| `tests/control/test_remote_transaction_review.py` | regular / 0o644 | 11652 | `b050579bf3083a411ad29096ff30d504801be50497ef2a1c3680d717f11aa2ee` |

The unchanged focused R1/R2/R5/archive-fixture/bridge/Gate-A selection was rerun:
**80 passed in 5.79s**, no skips/xfails. This is component evidence for the
starting combined identity, not joined evidence or the final gate cycle.

Current DoD: preservation met; complete candidate input audit/binding/negative
tests in progress; joined controller transaction and R3/R6 not established;
R1/R2/R5 component repairs partial; R4 conformance and readiness blocked.
The required joined seam remains actual production assembly/controller, retained
phase orchestration and verifier, runtime admission/factory, finalizer/evaluator,
checkpoint and cleanup; only input bindings and lowest environmental operations
may be substituted. No new completeness receipt is authorized by component passes.

### Candidate closure audit and first verifier evidence

The explicit input inventory is `tests/fixtures/t09/offline-candidate-closure.json`
(151 members). It inventories the retained runtime entrypoints, recursive local
imports including relative imports, referenced retained scripts/schema resources,
selected V16 execution bindings and condition-plan references, package metadata,
and the existing public fixture inputs. Imported compatibility modules are source
dependencies; their presence is not evidence that their historical workflows ran.
The normal provider registry and historical scientific files are not changed.

New paths in this continuation are `src/giclab/harness/t09_candidate_inputs.py`,
`tests/control/candidate_bootstrap.py`, `tests/control/test_candidate_inputs.py`,
and the explicit closure JSON. The additional tracked source edit is
`t09_freeze_commands.py`, whose renderer accepts the same explicitly selected
source input for command hashes. These changes implement the authorized candidate
input seam, not a new controller or qualification implementation.

Three-way source audit below: byte count / SHA-256. The historical column uses
only actual V16 instrumentation pins and their source reference `a235d1e6d287b5ea9daf5ca3787f9bbca278f3aa`;
absence of a formal historical pin is stated explicitly. The reviewed-head column
uses Git objects at `a98b4b875ab4d101709d62bc7222b5c90681a893`. The resumed
column uses the preserved 17-file snapshot for changed paths and reviewed Git
bytes for unchanged paths. Newly introduced candidate files were absent at resume.
Exactly the eight earlier reported instrumentation mismatches were reproduced.
No historical expected checksum was changed. Runtime import/mount mappings are
recorded separately in each generated candidate member record. The source
snapshot has its own dirty-delta identity; it is not the reviewed Git tree.

| Source member | Role / consumer | Historical V16 bytes / SHA | Reviewed head bytes / SHA | Preserved resume bytes / SHA |
|---|---|---|---|---|
| `containers/sira-smoke/bounded/browser_preflight.py` | retained-entrypoint | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` |
| `containers/sira-smoke/container_entrypoint.py` | retained-entrypoint | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` |
| `containers/sira-smoke/pragmatic/Containerfile.amd64` | historical-template | not a V16 instrumentation pin | 3239 / `7443af988256c6ce64e8f04d4797c7bae3bb3816c3d9f756d65d35ad5da3b4d8` | 3239 / `7443af988256c6ce64e8f04d4797c7bae3bb3816c3d9f756d65d35ad5da3b4d8` |
| `containers/sira-smoke/pragmatic/materialize_openai_secret.py` | retained-entrypoint | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` |
| `containers/sira-smoke/pragmatic/runtime_preflight.py` | retained-resource | not a V16 instrumentation pin | 10711 / `0530b3ad25fac1d3f9372d31da8046bec67b6c74eea3cdd3c8d91353948f1b3d` | 10711 / `0530b3ad25fac1d3f9372d31da8046bec67b6c74eea3cdd3c8d91353948f1b3d` |
| `containers/sira-smoke/pragmatic/t09_core_preflight.py` | retained-resource | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` |
| `containers/sira-smoke/pragmatic/t09_evaluate_attempt.py` | retained-resource | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` |
| `containers/sira-smoke/pragmatic/t09_finalizer_projection.py` | retained-resource | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` |
| `containers/sira-smoke/pragmatic/t09_freeze_commands.py` | retained-resource | 6695 / `4b593f68a45eccbe8e78df6192508e689448b7d61a41faa622e2ab191e4656ff` | 6812 / `45460760c3ee12e834c995d62e2b368e3ba8c55947fc75758be4324b096b0795` | 6812 / `45460760c3ee12e834c995d62e2b368e3ba8c55947fc75758be4324b096b0795` |
| `containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py` | retained-resource | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` |
| `containers/sira-smoke/pragmatic/t09_preflight.py` | retained-resource | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` |
| `containers/sira-smoke/pragmatic/t09_provider_accounting_preflight.py` | retained-resource | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` |
| `containers/sira-smoke/pragmatic/t09_real_evidence_regression.py` | retained-resource | 21892 / `b6a8b571f275894473b81dc547bbacf44db5257cda00d81c22469af2ab31ca50` | 21892 / `b6a8b571f275894473b81dc547bbacf44db5257cda00d81c22469af2ab31ca50` | 24533 / `3e2896f88b3cb011b6970e4fc44057d97ca354ea552b5a686ec889d59637ab6c` |
| `containers/sira-smoke/pragmatic/t09_remote_runner.py` | retained-resource | 1092957 / `ff7bbe48e2f790282a3cb012184653da237801433947391009b4df1f0225269e` | 1163386 / `39a6216acb02ebc86e1e1a07c4db5d4cb2562ba8bcda9acb29787f1941b7d6ef` | 1169602 / `5b3d72cb196c393a1c26289878d860c68366647496f4a8864deaad877b054023` |
| `containers/sira-smoke/pragmatic/t09_secret_preflight.py` | retained-resource | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY4_FINALIZER_REGRESSION.json` | historical-template | not a V16 instrumentation pin | 8105 / `f6b6da5543dc6014c9069997cc2c4e2630640ec3bf3dbfcbe6b94d57d9565b6b` | 8105 / `f6b6da5543dc6014c9069997cc2c4e2630640ec3bf3dbfcbe6b94d57d9565b6b` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_DATASET_CONTRACT.json` | historical-template | not a V16 instrumentation pin | 4413 / `fac0b6174b8697fd9390c7cf1b3badd6e1cbb2307e08d55e7d00f56e932527aa` | 4413 / `fac0b6174b8697fd9390c7cf1b3badd6e1cbb2307e08d55e7d00f56e932527aa` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_EVALUATOR_CONTRACT.json` | historical-template | not a V16 instrumentation pin | 6914 / `c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321` | 6914 / `c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V16.json` | historical-template | not a V16 instrumentation pin | 23521 / `377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b` | 23521 / `377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V16.json` | historical-template | not a V16 instrumentation pin | 31649 / `a2bb10017263b1d3aab09f22a35854d3d78362fec500fbcd49a3d5053336d72e` | 31649 / `a2bb10017263b1d3aab09f22a35854d3d78362fec500fbcd49a3d5053336d72e` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_RUNTIME_IDENTITY_V16.json` | historical-template | not a V16 instrumentation pin | 11150 / `ab4c2f8a93d235c0c00fc24b4d6d10657528b1de9bee656ba611e3311f6fd1f2` | 11150 / `ab4c2f8a93d235c0c00fc24b4d6d10657528b1de9bee656ba611e3311f6fd1f2` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0000-reactive.yaml` | historical-template | not a V16 instrumentation pin | 1526 / `8c0b447b794853e9f69fe9fc665cde632e3c4d0aa9a99a4346d46f345aaf20bf` | 1526 / `8c0b447b794853e9f69fe9fc665cde632e3c4d0aa9a99a4346d46f345aaf20bf` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0000-simulative.yaml` | historical-template | not a V16 instrumentation pin | 1532 / `30515859c919b5dd62a821b57efeb39135760c059ee9a05fbe1c6d54b269ca1c` | 1532 / `30515859c919b5dd62a821b57efeb39135760c059ee9a05fbe1c6d54b269ca1c` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0001-reactive.yaml` | historical-template | not a V16 instrumentation pin | 1526 / `6a3bc1f4775bc27dcb8aaa19770ce43a72e03da0a7466a8eba978121a2d6170d` | 1526 / `6a3bc1f4775bc27dcb8aaa19770ce43a72e03da0a7466a8eba978121a2d6170d` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0001-simulative.yaml` | historical-template | not a V16 instrumentation pin | 1532 / `081af4f0f0477f529b06df136a72042dd792508af33adb3a34bf31d7e3959378` | 1532 / `081af4f0f0477f529b06df136a72042dd792508af33adb3a34bf31d7e3959378` |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V16.yaml` | historical-template | not a V16 instrumentation pin | 15897 / `80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a` | 15897 / `80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a` |
| `pyproject.toml` | historical-template | not a V16 instrumentation pin | 1396 / `1e35d1ee8f3788950676aad1ad8200bfd1b1e01bae6e1032363677a1c0c41570` | 1396 / `1e35d1ee8f3788950676aad1ad8200bfd1b1e01bae6e1032363677a1c0c41570` |
| `schemas/t09-active-version-lint-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 1578 / `cf907af3fe7d904e7665fbf00a587b61d96641071fc3a5f88c4e42a514b6633f` | 1578 / `cf907af3fe7d904e7665fbf00a587b61d96641071fc3a5f88c4e42a514b6633f` |
| `schemas/t09-agent-check-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 5396 / `6a6bd2aba66978ce5a78398d53759c10d685b68c556daf9fa99ddb339ba6b7f7` | 5396 / `6a6bd2aba66978ce5a78398d53759c10d685b68c556daf9fa99ddb339ba6b7f7` |
| `schemas/t09-anti-shadow-lint-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 8591 / `20df97d4fbf9c5443e2cf610012b6edbd3387b55732634a646296f35513f2f39` | 8591 / `20df97d4fbf9c5443e2cf610012b6edbd3387b55732634a646296f35513f2f39` |
| `schemas/t09-category3-shadow-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 9173 / `7a74af233666fde629c52f73950dfcfb76dd7930c1e71cf94eaef6d28b9719c8` | 9173 / `7a74af233666fde629c52f73950dfcfb76dd7930c1e71cf94eaef6d28b9719c8` |
| `schemas/t09-cleanup-export-handoff.schema.json` | retained-resource | not a V16 instrumentation pin | 5738 / `fc5fd18d35239aabf1a02caa10c56ecce2a2ad073a94f0f0b282e77a75f801e9` | 5738 / `fc5fd18d35239aabf1a02caa10c56ecce2a2ad073a94f0f0b282e77a75f801e9` |
| `schemas/t09-condition-duplex-frame.schema.json` | retained-resource | not a V16 instrumentation pin | 2643 / `190757e75e09c50a8a7e82258880b3d2ba28deaf72c0b4f54dad39ae091492af` | 2643 / `190757e75e09c50a8a7e82258880b3d2ba28deaf72c0b4f54dad39ae091492af` |
| `schemas/t09-condition-duplex-transcript.schema.json` | retained-resource | not a V16 instrumentation pin | 2574 / `7f2e5b3d5d6bc955132217948b99654d85c3588c032a57f2e877a60a2753d07c` | 2574 / `7f2e5b3d5d6bc955132217948b99654d85c3588c032a57f2e877a60a2753d07c` |
| `schemas/t09-condition-host-terminal-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 2455 / `8dfc659a94f27c3906606d5e8e463e6a18bbbdeefa10b4d6a7ee8689542760e6` | 2455 / `8dfc659a94f27c3906606d5e8e463e6a18bbbdeefa10b4d6a7ee8689542760e6` |
| `schemas/t09-condition-runtime-detachment.schema.json` | retained-resource | not a V16 instrumentation pin | 1189 / `d65e09cf916b568494da945088ff51440826702fea3036512f818357d7397a7d` | 1189 / `d65e09cf916b568494da945088ff51440826702fea3036512f818357d7397a7d` |
| `schemas/t09-condition-session-terminal-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 2615 / `2804edf3875a257ada60eab5f00ac7fac1e80e9344d54867a7a51539ef181cf7` | 2615 / `2804edf3875a257ada60eab5f00ac7fac1e80e9344d54867a7a51539ef181cf7` |
| `schemas/t09-control-composition-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 3051 / `a394ed475d2c319454821c46a4a75b5b33c6a9bbf1df32b2c14c49cb10bf0012` | 3051 / `a394ed475d2c319454821c46a4a75b5b33c6a9bbf1df32b2c14c49cb10bf0012` |
| `schemas/t09-control-plane-source-binding.schema.json` | retained-resource | not a V16 instrumentation pin | 1609 / `f801d7587d38b7c7a7be94c061d52c6c489a450479ba8ade16dd8f4300fb1fae` | 1609 / `f801d7587d38b7c7a7be94c061d52c6c489a450479ba8ade16dd8f4300fb1fae` |
| `schemas/t09-control-receipt-bindings.schema.json` | retained-resource | not a V16 instrumentation pin | 8485 / `bb69128e15cbdb377c3416f207d904380c1d80bbee53996a46b740fe5180a29d` | 8485 / `bb69128e15cbdb377c3416f207d904380c1d80bbee53996a46b740fe5180a29d` |
| `schemas/t09-control-registry-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 1693 / `09811de1f906f4d7caae38104578750324f7d5a86d96cf6e9569dc7f53487a49` | 1693 / `09811de1f906f4d7caae38104578750324f7d5a86d96cf6e9569dc7f53487a49` |
| `schemas/t09-control-target.schema.json` | retained-resource | not a V16 instrumentation pin | 2100 / `0337c5fdc1d1c87b3700575dd1261fdb91c1d847ccd7f53f69a59e4333eb32b1` | 2100 / `0337c5fdc1d1c87b3700575dd1261fdb91c1d847ccd7f53f69a59e4333eb32b1` |
| `schemas/t09-early-cleanup-state.schema.json` | retained-resource | not a V16 instrumentation pin | 5162 / `1e041fe3197ed7c53f80e782c727f1dfb9e6d27ec9476543466711948b018edf` | 5162 / `1e041fe3197ed7c53f80e782c727f1dfb9e6d27ec9476543466711948b018edf` |
| `schemas/t09-effect-authorization-context.schema.json` | retained-resource | not a V16 instrumentation pin | 2989 / `6e0075353daf77a5a786a5203935f18f579a5850436ec75510df2756c16c1aef` | 2989 / `6e0075353daf77a5a786a5203935f18f579a5850436ec75510df2756c16c1aef` |
| `schemas/t09-essential-failure-complete.schema.json` | retained-resource | not a V16 instrumentation pin | 1651 / `4b85240e1567b569dca70a4f95e70a76510ec89d4919f1d5972de2791feea5be` | 1651 / `4b85240e1567b569dca70a4f95e70a76510ec89d4919f1d5972de2791feea5be` |
| `schemas/t09-essential-failure-export-acknowledgement.schema.json` | retained-resource | not a V16 instrumentation pin | 1614 / `a147416647bc5cb387aa1f4de53301f7e8079930eaf1ff6e44eea7c8db6e417a` | 1614 / `a147416647bc5cb387aa1f4de53301f7e8079930eaf1ff6e44eea7c8db6e417a` |
| `schemas/t09-essential-failure-manifest.schema.json` | retained-resource | not a V16 instrumentation pin | 2676 / `8eb960d4418bf0f42b40ef10c4ca7c1ab4e366c5ff61724eda690972679536b4` | 2676 / `8eb960d4418bf0f42b40ef10c4ca7c1ab4e366c5ff61724eda690972679536b4` |
| `schemas/t09-full-dynamic-frozen-manifest.schema.json` | retained-resource | not a V16 instrumentation pin | 5591 / `ba9b7e39342c493b5a1aeb0a0ea3416f108147cc7a0e566d2bd85fa1c97e3472` | 5591 / `ba9b7e39342c493b5a1aeb0a0ea3416f108147cc7a0e566d2bd85fa1c97e3472` |
| `schemas/t09-host-phase-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 2183 / `0da3cf2ce824e79eede3efcdd46052462c9db8daef7257665091285439b6b7e7` | 2183 / `0da3cf2ce824e79eede3efcdd46052462c9db8daef7257665091285439b6b7e7` |
| `schemas/t09-host-phase-request.schema.json` | retained-resource | not a V16 instrumentation pin | 3525 / `ac9834094c451082f186d2c52d7e0503c75240cde0c823d1312402cd847fb2ce` | 3525 / `ac9834094c451082f186d2c52d7e0503c75240cde0c823d1312402cd847fb2ce` |
| `schemas/t09-incident-completeness-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 1920 / `2258f2467d48f517c76adb4f14be259fc807b5499e4ad88ecfeda9fcdfec9e8e` | 1920 / `2258f2467d48f517c76adb4f14be259fc807b5499e4ad88ecfeda9fcdfec9e8e` |
| `schemas/t09-live-effect-conformance-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 29544 / `1df6ce62a816c08ac54d99493731c41c9ab11013994f8e2fc69c49f17ffc1ab5` | 29544 / `1df6ce62a816c08ac54d99493731c41c9ab11013994f8e2fc69c49f17ffc1ab5` |
| `schemas/t09-live-method-map.schema.json` | retained-resource | not a V16 instrumentation pin | 2588 / `ade03d252e591e1e33bf22cb7c1bf5fbda487ee61d6bf98e4d5e5c6189d46050` | 2588 / `ade03d252e591e1e33bf22cb7c1bf5fbda487ee61d6bf98e4d5e5c6189d46050` |
| `schemas/t09-live-method-viability.schema.json` | retained-resource | not a V16 instrumentation pin | 3514 / `fd0a17d41ea40a81bec1aac8d04022cf68d138b1703913980ded7fd0851c4854` | 3514 / `fd0a17d41ea40a81bec1aac8d04022cf68d138b1703913980ded7fd0851c4854` |
| `schemas/t09-model-metadata-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 2649 / `8b61a8f7e572abfd5ed6347998c2829af0f114c6b7ca457e81e8691c5574a70a` | 2649 / `8b61a8f7e572abfd5ed6347998c2829af0f114c6b7ca457e81e8691c5574a70a` |
| `schemas/t09-offline-refinalization-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 9032 / `4965287881472b0605678223173e15ac870eebe894f95cae2609b390daf801e9` | 9032 / `4965287881472b0605678223173e15ac870eebe894f95cae2609b390daf801e9` |
| `schemas/t09-private-condition-socket-binding.schema.json` | retained-resource | not a V16 instrumentation pin | 1369 / `45bb526628a33c71cd32db3965242de6885550ff0b4e86df51af38e1be9aa85b` | 1369 / `45bb526628a33c71cd32db3965242de6885550ff0b4e86df51af38e1be9aa85b` |
| `schemas/t09-remote-execution-bridge-conformance.schema.json` | retained-resource | not a V16 instrumentation pin | 8742 / `678fcd14160568f77d7e67570aed85ad78d589b0e02d41410f5af681be4db442` | 8742 / `678fcd14160568f77d7e67570aed85ad78d589b0e02d41410f5af681be4db442` |
| `schemas/t09-sira-pilot-evidence.schema.json` | retained-resource | not a V16 instrumentation pin | 8579 / `e0a3d158a9ba27df01f302197511cc29d069e3d94b4d7a974593fe0aefa2b1db` | 8579 / `e0a3d158a9ba27df01f302197511cc29d069e3d94b4d7a974593fe0aefa2b1db` |
| `schemas/t09-sira-pilot-execution.schema.json` | retained-resource | not a V16 instrumentation pin | 9230 / `55d5e4c80546f5af58ab707f847fc156cd9bd3da9ca76e6c7d5c19bcecf0a004` | 9230 / `55d5e4c80546f5af58ab707f847fc156cd9bd3da9ca76e6c7d5c19bcecf0a004` |
| `schemas/t09-sira-pilot-score.schema.json` | retained-resource | not a V16 instrumentation pin | 3779 / `1f2e85eba21b2bce7a56448e44682e6c00155744ab9a2fa3308dffe3442e7746` | 3779 / `1f2e85eba21b2bce7a56448e44682e6c00155744ab9a2fa3308dffe3442e7746` |
| `schemas/t09-sira-pilot-v10-execution.schema.json` | retained-resource | not a V16 instrumentation pin | 9298 / `19aa66563bac64d40233e8b4c70a7b94418d0402a11dff61993c2dd878ec448a` | 9298 / `19aa66563bac64d40233e8b4c70a7b94418d0402a11dff61993c2dd878ec448a` |
| `schemas/t09-sira-pilot-v11-execution.schema.json` | retained-resource | not a V16 instrumentation pin | 9809 / `096e0a589a102b5cbf270eb3f8a14d9b9dd6cf7a48fb9397b1f126b1af8b6525` | 9809 / `096e0a589a102b5cbf270eb3f8a14d9b9dd6cf7a48fb9397b1f126b1af8b6525` |
| `schemas/t09-sira-pilot-v12-execution.schema.json` | retained-resource | not a V16 instrumentation pin | 11169 / `dbfe483f5238fa03b97e4e0f0d4846d4312f58ab46dbbea10017080604c6fbb1` | 11169 / `dbfe483f5238fa03b97e4e0f0d4846d4312f58ab46dbbea10017080604c6fbb1` |
| `schemas/t09-sira-pilot-v13-execution.schema.json` | retained-resource | not a V16 instrumentation pin | 11169 / `65bd4fa0cf2ef72873adca85afa2c0b6c825b4503ea7fed34d713124d81e9db0` | 11169 / `65bd4fa0cf2ef72873adca85afa2c0b6c825b4503ea7fed34d713124d81e9db0` |
| `schemas/t09-sira-pilot-v14-execution.schema.json` | retained-resource | not a V16 instrumentation pin | 11164 / `2a457caf35b81d3158dde5e16b4b3d2a68777e646dd61924bdc6de0aa4b0806b` | 11164 / `2a457caf35b81d3158dde5e16b4b3d2a68777e646dd61924bdc6de0aa4b0806b` |
| `schemas/t09-sira-pilot-v16-execution.schema.json` | historical-template | not a V16 instrumentation pin | 12217 / `22ff91eb1de34edc890c81eeb242b40418acf0671bbfcfab36fefc43df138a3d` | 12217 / `22ff91eb1de34edc890c81eeb242b40418acf0671bbfcfab36fefc43df138a3d` |
| `schemas/t09-v10-plan.schema.json` | retained-resource | not a V16 instrumentation pin | 20979 / `7d0f2a6c9d0b5106f111c799aa29ef55012d12596f4819d27dbc9c57ced5285e` | 20979 / `7d0f2a6c9d0b5106f111c799aa29ef55012d12596f4819d27dbc9c57ced5285e` |
| `schemas/t09-v11-plan.schema.json` | retained-resource | not a V16 instrumentation pin | 23345 / `3291af39c50ce4f186008adc56d79fc1715adc539a1faea92c2fb3bff4988a7f` | 23345 / `3291af39c50ce4f186008adc56d79fc1715adc539a1faea92c2fb3bff4988a7f` |
| `schemas/t09-v12-plan.schema.json` | retained-resource | not a V16 instrumentation pin | 27632 / `bf799255b12def214689f0a0ad7c18f7dda9bd0d19876c6414159c4bb3209908` | 27632 / `bf799255b12def214689f0a0ad7c18f7dda9bd0d19876c6414159c4bb3209908` |
| `schemas/t09-v13-model-metadata-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 2653 / `b30dae9e4d703e12bcbc7757a3afe266af6f911dfb0d6adbb8a7f28986e81cae` | 2653 / `b30dae9e4d703e12bcbc7757a3afe266af6f911dfb0d6adbb8a7f28986e81cae` |
| `schemas/t09-v13-plan.schema.json` | retained-resource | not a V16 instrumentation pin | 29512 / `7435fc2c126dcf1166f46a3b86218800765dcb9c590eb75bc8ad9e460e2073f3` | 29512 / `7435fc2c126dcf1166f46a3b86218800765dcb9c590eb75bc8ad9e460e2073f3` |
| `schemas/t09-v14-model-metadata-receipt.schema.json` | retained-resource | not a V16 instrumentation pin | 2653 / `e01925b516d78774802149ddd887e4371d41eda00524f38d45737d4b256f941a` | 2653 / `e01925b516d78774802149ddd887e4371d41eda00524f38d45737d4b256f941a` |
| `schemas/t09-v14-plan.schema.json` | retained-resource | not a V16 instrumentation pin | 31604 / `6e9715b463a6b82fae1a0f05c1197498d3ff5628a26502d7827d5c63efefca30` | 31604 / `6e9715b463a6b82fae1a0f05c1197498d3ff5628a26502d7827d5c63efefca30` |
| `schemas/t09-v16-model-metadata-receipt.schema.json` | historical-template | not a V16 instrumentation pin | 2653 / `4e135f5059a9d446499cb3972ce474b7f2cc78fb8b91df451bbb045e295c0ea3` | 2653 / `4e135f5059a9d446499cb3972ce474b7f2cc78fb8b91df451bbb045e295c0ea3` |
| `src/giclab/__init__.py` | import-package | not a V16 instrumentation pin | 66 / `1ba2dce15386a0abda4d8c35e38158220523ecdb3523638c9790be13dabeb872` | 66 / `1ba2dce15386a0abda4d8c35e38158220523ecdb3523638c9790be13dabeb872` |
| `src/giclab/control/__init__.py` | import-package | not a V16 instrumentation pin | 192 / `b3250bf7d8c6e894cdb53903359885eeb25dd02e115a9064e614ba23a712f2b7` | 192 / `b3250bf7d8c6e894cdb53903359885eeb25dd02e115a9064e614ba23a712f2b7` |
| `src/giclab/control/adapters.py` | import-dependency | not a V16 instrumentation pin | 8578 / `f6124e51763c2440c312f9b570e40fa4d9ed28292e8a323ee5ea151477093f42` | 8578 / `f6124e51763c2440c312f9b570e40fa4d9ed28292e8a323ee5ea151477093f42` |
| `src/giclab/control/anti_shadow_lint.py` | import-dependency | not a V16 instrumentation pin | 52412 / `d1004584cfae4d1f8685b73c39c9c1dcbe1f296591b8322c61b198c4c4d4fe2d` | 52412 / `d1004584cfae4d1f8685b73c39c9c1dcbe1f296591b8322c61b198c4c4d4fe2d` |
| `src/giclab/control/category3.py` | import-dependency | not a V16 instrumentation pin | 44743 / `965d2f635e1c0dbde6d898d90d25fb8a857385f5d8e66c0bb78ec53510ce14a6` | 44743 / `965d2f635e1c0dbde6d898d90d25fb8a857385f5d8e66c0bb78ec53510ce14a6` |
| `src/giclab/control/composition.py` | import-dependency | not a V16 instrumentation pin | 14162 / `ea2f5ea3bae9a0a0dd241bc8a08255e84775c006f7d1bd3c59c733635726473d` | 14162 / `ea2f5ea3bae9a0a0dd241bc8a08255e84775c006f7d1bd3c59c733635726473d` |
| `src/giclab/control/consumers.py` | import-dependency | not a V16 instrumentation pin | 16974 / `a02492bd29148fd75ae30bc45459718534187efdab9023ed7b45003dc6fbf7e6` | 16974 / `a02492bd29148fd75ae30bc45459718534187efdab9023ed7b45003dc6fbf7e6` |
| `src/giclab/control/contracts.py` | import-dependency | not a V16 instrumentation pin | 2045 / `11091738583b1df60a4949e4aba206861549aed6412a503e0a747c5157fec7bf` | 2045 / `11091738583b1df60a4949e4aba206861549aed6412a503e0a747c5157fec7bf` |
| `src/giclab/control/effects.py` | import-dependency | not a V16 instrumentation pin | 92297 / `1aec331d62cc02e13f9dded6dd87ad7bbeabeae4ba4f95379b81019d48588be7` | 92297 / `1aec331d62cc02e13f9dded6dd87ad7bbeabeae4ba4f95379b81019d48588be7` |
| `src/giclab/control/production.py` | retained-entrypoint | not a V16 instrumentation pin | 280246 / `09347a65ccbc1c3e0794fb8cb1109a03585892e31c09e48aa4418b568fd75e36` | 280246 / `09347a65ccbc1c3e0794fb8cb1109a03585892e31c09e48aa4418b568fd75e36` |
| `src/giclab/control/proofs.py` | import-dependency | not a V16 instrumentation pin | 77725 / `5b1aba3cd3f5eea1c133b4670818edf75b477f7bd0eec52b57d7979429f92004` | 77725 / `5b1aba3cd3f5eea1c133b4670818edf75b477f7bd0eec52b57d7979429f92004` |
| `src/giclab/control/registry_validation.py` | import-dependency | not a V16 instrumentation pin | 17629 / `4a455c4faf78996838e8e5081bb0872e6a10e2a8ad2bff5db0afac72317733a1` | 17629 / `4a455c4faf78996838e8e5081bb0872e6a10e2a8ad2bff5db0afac72317733a1` |
| `src/giclab/control/remote_bridge.py` | import-dependency | not a V16 instrumentation pin | 102837 / `ca48a145927fc158476d76b9bf113c9550e1eba52ee6d56897fd6915bd1a0ee6` | 104098 / `708e24064767cd625deef8d5e9181430b0b85a1feefb9345bc20d277b3ca8381` |
| `src/giclab/control/scenarios.py` | import-dependency | not a V16 instrumentation pin | 729 / `4cf66a4f0ec37bc8405777794af3d5dbbaf5feafbbb661d5d62c4aa5b1298a5c` | 729 / `4cf66a4f0ec37bc8405777794af3d5dbbaf5feafbbb661d5d62c4aa5b1298a5c` |
| `src/giclab/control/target.py` | import-dependency | not a V16 instrumentation pin | 23710 / `e354aa938c3f37ac56c6cd45ca672c497014ac3c09200771c23431b057e70ca7` | 23710 / `e354aa938c3f37ac56c6cd45ca672c497014ac3c09200771c23431b057e70ca7` |
| `src/giclab/control/version_lint.py` | import-dependency | not a V16 instrumentation pin | 13530 / `e148b51125d085e7c2f0f6b558d24b34af07eddfb4f6c866341c2ea54fe37b49` | 13530 / `e148b51125d085e7c2f0f6b558d24b34af07eddfb4f6c866341c2ea54fe37b49` |
| `src/giclab/harness/__init__.py` | import-package | not a V16 instrumentation pin | 3669 / `9cb096df25019fbb4e6c61a55b46cf4bb38ebe6b650248f1f0623347cf568c97` | 3669 / `9cb096df25019fbb4e6c61a55b46cf4bb38ebe6b650248f1f0623347cf568c97` |
| `src/giclab/harness/adapters/__init__.py` | import-package | not a V16 instrumentation pin | 1749 / `f241a205c6c4a616418b5ac6cd8fb25b6c3a135decb0e35dacb9954e540095af` | 1749 / `f241a205c6c4a616418b5ac6cd8fb25b6c3a135decb0e35dacb9954e540095af` |
| `src/giclab/harness/adapters/base.py` | import-dependency | not a V16 instrumentation pin | 2430 / `22e6a4c84b0d8b583bd3055d115a4a2e61a9555e466f076d79a91520aa3b985e` | 2430 / `22e6a4c84b0d8b583bd3055d115a4a2e61a9555e466f076d79a91520aa3b985e` |
| `src/giclab/harness/adapters/sira.py` | import-dependency | not a V16 instrumentation pin | 78882 / `5da13853584caa1f680536f719a873b860031c2648a88f9812d67163ba7be5bc` | 78882 / `5da13853584caa1f680536f719a873b860031c2648a88f9812d67163ba7be5bc` |
| `src/giclab/harness/artifacts.py` | import-dependency | not a V16 instrumentation pin | 20779 / `643f02b893694c947d7cd4c29f374a158caf54b167f3d8d192b36e1a6eae2c3d` | 20779 / `643f02b893694c947d7cd4c29f374a158caf54b167f3d8d192b36e1a6eae2c3d` |
| `src/giclab/harness/budget.py` | import-dependency | not a V16 instrumentation pin | 5400 / `376ad8f491940a0758b49d6bc597e182a69af0459ace9d06c7e652d76ad9bc2a` | 5400 / `376ad8f491940a0758b49d6bc597e182a69af0459ace9d06c7e652d76ad9bc2a` |
| `src/giclab/harness/events.py` | import-dependency | not a V16 instrumentation pin | 12542 / `b6a4c529d9bc3939c552891e75083bd0d7420744b5948a4739165c861992a29d` | 12542 / `b6a4c529d9bc3939c552891e75083bd0d7420744b5948a4739165c861992a29d` |
| `src/giclab/harness/executor.py` | import-dependency | not a V16 instrumentation pin | 70144 / `007c627e42ba53db0009f31ec2594ede8f40bfc690f027109068fd5f37189a70` | 70144 / `007c627e42ba53db0009f31ec2594ede8f40bfc690f027109068fd5f37189a70` |
| `src/giclab/harness/lambda_archive.py` | import-dependency | not a V16 instrumentation pin | 27340 / `2004f5c9b23a41a040baad766516e0f2d62e6edf440a4571b484ee061b2d1c4c` | 27340 / `2004f5c9b23a41a040baad766516e0f2d62e6edf440a4571b484ee061b2d1c4c` |
| `src/giclab/harness/lambda_archive_v3.py` | import-dependency | not a V16 instrumentation pin | 43290 / `29e59e6c9e71c45211322b10c365d6044445658d7e3b317f4d0017b17d6b0f50` | 43290 / `29e59e6c9e71c45211322b10c365d6044445658d7e3b317f4d0017b17d6b0f50` |
| `src/giclab/harness/lambda_campaign_lifecycle.py` | import-dependency | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` |
| `src/giclab/harness/lambda_cloud.py` | import-dependency | not a V16 instrumentation pin | 103598 / `69aa0c54e48f9f49f9dd7d297af12e41468ed6d0c7b9a36e89ba10d3d668c51c` | 103598 / `69aa0c54e48f9f49f9dd7d297af12e41468ed6d0c7b9a36e89ba10d3d668c51c` |
| `src/giclab/harness/lambda_cloud_v3.py` | import-dependency | not a V16 instrumentation pin | 56507 / `4ffb4f649e6fdd3e3e2d058f7b009aa9f64d5c9e4d32874ff0e24754ec3dfae6` | 56507 / `4ffb4f649e6fdd3e3e2d058f7b009aa9f64d5c9e4d32874ff0e24754ec3dfae6` |
| `src/giclab/harness/lambda_firewall_baseline.py` | import-dependency | not a V16 instrumentation pin | 108400 / `fe736fb42136ce56ab1a81dc5a2face6e3c5be8855bba496878fe5ac2bd579e3` | 108400 / `fe736fb42136ce56ab1a81dc5a2face6e3c5be8855bba496878fe5ac2bd579e3` |
| `src/giclab/harness/lambda_inventory_plan_v3.py` | import-dependency | not a V16 instrumentation pin | 37867 / `80c3b39ec904b3a5cfb03118a1173b67b22ce0d7e4fb325fdc4195a308c57d1b` | 37867 / `80c3b39ec904b3a5cfb03118a1173b67b22ce0d7e4fb325fdc4195a308c57d1b` |
| `src/giclab/harness/lambda_l13_security.py` | import-dependency | not a V16 instrumentation pin | 93281 / `1f2736ae223649f86bb18621b008f06bf9fd0d82af6d28ed904f53e8b0111fd0` | 93281 / `1f2736ae223649f86bb18621b008f06bf9fd0d82af6d28ed904f53e8b0111fd0` |
| `src/giclab/harness/lambda_l20_plan.py` | import-dependency | not a V16 instrumentation pin | 128149 / `e4c7ad2aa7c41520a47bd41c3faaaf204fc2e0a5ce6dc1299e688f1f8e98cc7c` | 128149 / `e4c7ad2aa7c41520a47bd41c3faaaf204fc2e0a5ce6dc1299e688f1f8e98cc7c` |
| `src/giclab/harness/lambda_l2m_checkpoints.py` | import-dependency | not a V16 instrumentation pin | 33515 / `3c8ae545c4d39b633bdd9e02ae3d79a704d0eda5f0a70b0378dd3d32e6afe0f0` | 33515 / `3c8ae545c4d39b633bdd9e02ae3d79a704d0eda5f0a70b0378dd3d32e6afe0f0` |
| `src/giclab/harness/lambda_l2m_observer.py` | import-dependency | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` |
| `src/giclab/harness/lambda_request_ledger_v3.py` | import-dependency | not a V16 instrumentation pin | 52146 / `4e3f15c8d1651f18cc64d7c9dd47bc15d655bac5b3a348d74b364c12687dfd4c` | 52146 / `4e3f15c8d1651f18cc64d7c9dd47bc15d655bac5b3a348d74b364c12687dfd4c` |
| `src/giclab/harness/lambda_ssh_key_fingerprint.py` | import-dependency | not a V16 instrumentation pin | 42587 / `89570f118d9bd860b1b251fdaa9b3b28e80e5a4476ccffe6607763643967320a` | 42587 / `89570f118d9bd860b1b251fdaa9b3b28e80e5a4476ccffe6607763643967320a` |
| `src/giclab/harness/models.py` | import-dependency | not a V16 instrumentation pin | 49840 / `79de878cba256283a7bf360c8e1930ed67fdab9145059c509281c9752cadb739` | 49840 / `79de878cba256283a7bf360c8e1930ed67fdab9145059c509281c9752cadb739` |
| `src/giclab/harness/plan.py` | import-dependency | not a V16 instrumentation pin | 12402 / `3ffbfea3ca16aacba6fab2db88e3f103888cb698294e45c94be2698864dd2f13` | 12402 / `3ffbfea3ca16aacba6fab2db88e3f103888cb698294e45c94be2698864dd2f13` |
| `src/giclab/harness/policy.py` | import-dependency | not a V16 instrumentation pin | 50697 / `e6a48e19b169c586123e30243837e2349c5767b57dd852daf953e2bb249cdc1b` | 50697 / `e6a48e19b169c586123e30243837e2349c5767b57dd852daf953e2bb249cdc1b` |
| `src/giclab/harness/regulation.py` | import-dependency | not a V16 instrumentation pin | 17438 / `02418042e29678d05774f123f829daa85e94f09c3f5839acafa558bc921e7001` | 17438 / `02418042e29678d05774f123f829daa85e94f09c3f5839acafa558bc921e7001` |
| `src/giclab/harness/safety.py` | import-dependency | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` |
| `src/giclab/harness/sira_colima.py` | import-dependency | not a V16 instrumentation pin | 46831 / `b5c50dbe04f84de24aa1566603ae09f4c8cf8bf7a3d3398e3412ed7bbaf8c999` | 46831 / `b5c50dbe04f84de24aa1566603ae09f4c8cf8bf7a3d3398e3412ed7bbaf8c999` |
| `src/giclab/harness/sira_gate_a.py` | import-dependency | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` |
| `src/giclab/harness/sira_gate_a_runtime.py` | import-dependency | 51033 / `0f1cd94fe048102704c9a4c461c6a3bf457ca53eb5586291441a675cd6b256a0` | 55760 / `7ff27906f6d1e8f83f434ad0dbae7800958cb18d5d01f56fa77b7f13b1560df6` | 56123 / `2ff3e50f4e45cea89cb17749205028afdf4e145534a6bc696662496c32df6b34` |
| `src/giclab/harness/sira_storage.py` | import-dependency | not a V16 instrumentation pin | 131263 / `0c8b111a657288278b519351d1a0973641c6897245bccc61228d90ddb5294c11` | 131263 / `0c8b111a657288278b519351d1a0973641c6897245bccc61228d90ddb5294c11` |
| `src/giclab/harness/t09_candidate_inputs.py` | candidate-binding-input | not a V16 instrumentation pin | absent | absent |
| `src/giclab/harness/t09_cleanup_state.py` | import-dependency | 55024 / `39a4d698b8184c4d6652294f32e07911b2998b1a6326ad280353ba5f505e387e` | 55515 / `97163a2508680fbb1a766d23bd542b4feb242cd0037f146ee715b0fc96d7d711` | 55515 / `97163a2508680fbb1a766d23bd542b4feb242cd0037f146ee715b0fc96d7d711` |
| `src/giclab/harness/t09_model_metadata_receipt.py` | import-dependency | 43545 / `88e39033963378454cfcb14f0d8d19dda1c72dc779e24696313f008e707363b5` | 43659 / `6ec6810ce5c0cad1d5a8fe7470c1f70d9d6449f56289f2e7edb8ff9813df404b` | 43659 / `6ec6810ce5c0cad1d5a8fe7470c1f70d9d6449f56289f2e7edb8ff9813df404b` |
| `src/giclab/harness/t09_pragmatic_provider.py` | import-dependency | 372381 / `8ac3b563842ab994e86c96921e46e292195a8e8c9962165cfe22d8b0a5f1294f` | 384727 / `f406a40a5b800dbe19335d818e9e524f7bf0533c1b421091aaf85f6b144da512` | 384727 / `f406a40a5b800dbe19335d818e9e524f7bf0533c1b421091aaf85f6b144da512` |
| `src/giclab/harness/t09_provider_contracts.py` | import-dependency | 47052 / `9c3ad548894c3ea52b151524d265cd158a10733d62183bd763aec33d116b615c` | 64903 / `024dbcfa3c343539fafb474fe48ffcf0fd6b5012746919fd35df4f89fb71210c` | 64903 / `024dbcfa3c343539fafb474fe48ffcf0fd6b5012746919fd35df4f89fb71210c` |
| `src/giclab/harness/t09_qualification_fixture.py` | retained-entrypoint | not a V16 instrumentation pin | absent | 10709 / `ba4d8e8361cbec8d0e3b8055f8a4f9175ae42fc49cef737be401a560fd6f27dd` |
| `src/giclab/harness/t09_remote_host_phases.py` | import-dependency | not a V16 instrumentation pin | 43450 / `b0721c5855ccb32d72ffe39afe5a5d72f8faab4a2c76fadbd07b992aa92004bc` | 43450 / `b0721c5855ccb32d72ffe39afe5a5d72f8faab4a2c76fadbd07b992aa92004bc` |
| `src/giclab/harness/t09_runtime_admission.py` | import-dependency | not a V16 instrumentation pin | 31066 / `918a79ce52afce3957763d2b55e9b8ea5c22904bceeed35ae611ab8968f8c3bd` | 31587 / `6ef3c8f00904124cddd486de9775df8f6ee43d930708fe026a4e778bb3efb52f` |
| `src/giclab/harness/t09_sira_pilot.py` | import-dependency | 150090 / `6e0574bddbb1585399ed9c19531b9191b571c483621a3585abe3c40d38a6c017` | 155554 / `7b197e0ed4b0cea214a8a27306616f0827b1e09e04ab003b73c4ee76dc390aa9` | 155554 / `7b197e0ed4b0cea214a8a27306616f0827b1e09e04ab003b73c4ee76dc390aa9` |
| `src/giclab/harness/task_source.py` | import-dependency | not a V16 instrumentation pin | 601 / `fb0631241e134c58914d4c6cf9c8617313dbdb5a3b5472af2333fc674052639b` | 601 / `fb0631241e134c58914d4c6cf9c8617313dbdb5a3b5472af2333fc674052639b` |
| `src/giclab/plans.py` | import-dependency | not a V16 instrumentation pin | 1947 / `f7bcc8054788b64aa79c7d17d379730bf52448a9c0d1f04eb0e8d4faba657400` | 1947 / `f7bcc8054788b64aa79c7d17d379730bf52448a9c0d1f04eb0e8d4faba657400` |
| `src/giclab/registry.py` | import-dependency | not a V16 instrumentation pin | 5801 / `dd97677ffd28dd6e576fcac6507728acd59405236747d5b1beab61aecd731af4` | 5801 / `dd97677ffd28dd6e576fcac6507728acd59405236747d5b1beab61aecd731af4` |
| `src/giclab/sitegen.py` | import-dependency | not a V16 instrumentation pin | 5645 / `90e929340d53fdcdaa2ce113234d0bf6cc2eb28ff43bf6fe7385c180b03f5b97` | 5645 / `90e929340d53fdcdaa2ce113234d0bf6cc2eb28ff43bf6fe7385c180b03f5b97` |
| `src/giclab/validation.py` | import-dependency | not a V16 instrumentation pin | 185729 / `596fd8cd2960604bc925455a0c76dd174230ad673a66d18a03cca87a66a1dad3` | 185729 / `596fd8cd2960604bc925455a0c76dd174230ad673a66d18a03cca87a66a1dad3` |
| `tests/control/candidate_bootstrap.py` | candidate-binding-input | not a V16 instrumentation pin | absent | absent |
| `tests/control/test_candidate_inputs.py` | candidate-binding-input | not a V16 instrumentation pin | absent | absent |
| `tests/fixtures/t09/fanout-two-task-fixture.json` | qualification-fixture-input | not a V16 instrumentation pin | 4941 / `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9` | 4941 / `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9` |
| `tests/fixtures/t09/finalizer-raw-shape/host-cleanup-receipt.json` | qualification-fixture-input | not a V16 instrumentation pin | 400 / `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` | 400 / `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` |
| `tests/fixtures/t09/finalizer-raw-shape/normalized-events.jsonl` | qualification-fixture-input | not a V16 instrumentation pin | 855 / `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` | 855 / `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` |
| `tests/fixtures/t09/finalizer-raw-shape/provider-budget.json` | qualification-fixture-input | not a V16 instrumentation pin | 435 / `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` | 435 / `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` |
| `tests/fixtures/t09/finalizer-raw-shape/provider-call-lifecycle.json` | qualification-fixture-input | not a V16 instrumentation pin | 2453 / `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` | 2453 / `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` |
| `tests/fixtures/t09/finalizer-raw-shape/runtime-environment.json` | qualification-fixture-input | not a V16 instrumentation pin | 220 / `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` | 220 / `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` |
| `tests/fixtures/t09/finalizer-raw-shape/sira-output/PRIVACY-SAFE-FINALIZER-FIXTURE.json` | qualification-fixture-input | not a V16 instrumentation pin | 318 / `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` | 318 / `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` |
| `tests/fixtures/t09/offline-candidate-closure.json` | candidate-binding-input | not a V16 instrumentation pin | absent | absent |
| `tests/fixtures/t09/pinned-evaluator/evaluator.py` | qualification-fixture-input | not a V16 instrumentation pin | 6776 / `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` | 6776 / `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` |
| `tests/fixtures/t09/pinned-evaluator/run.py` | qualification-fixture-input | not a V16 instrumentation pin | 1537 / `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` | 1537 / `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` |
| `tests/fixtures/t09/pinned-evaluator/utils/helpers.py` | qualification-fixture-input | not a V16 instrumentation pin | 1892 / `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` | 1892 / `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` |
| `tests/fixtures/t09/pinned-evaluator/utils/models.py` | qualification-fixture-input | not a V16 instrumentation pin | 1092 / `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` | 1092 / `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` |
| `tests/fixtures/t09/pinned-evaluator/utils/norm.py` | qualification-fixture-input | not a V16 instrumentation pin | 1897 / `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` | 1897 / `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` |
| `uv.lock` | historical-template | not a V16 instrumentation pin | 418224 / `bec09cf0d326c56af9f717782eef9160579e7720dff701083570df9aa712b34b` | 418224 / `bec09cf0d326c56af9f717782eef9160579e7720dff701083570df9aa712b34b` |

Candidate ID: `T09-OFFLINE-CANDIDATE-SOURCE-PACKAGE-1`. Hash order is
source bytes, member inventory/delta, binding payload, then binding digest; no
binding embeds its own digest. Historical template members are checked against
the immutable reviewed reference. The temporary runtime/execution/command
projection changes instrumentation hashes, the runtime reference hash and the
actual retained renderer output. Model/task/data/evaluator/budget/order/retry
policy content remains exact. The original template source ancestor remains a
template reference, while the separate binding names the actual dirty bytes.
Every derived file records both template and actual byte/hash identities.

Initial `tests/control/test_candidate_inputs.py` run: **9 passed in 31.76s**.
It includes a fresh Python subprocess loaded from the sealed source snapshot,
the actual retained command renderer and actual `verify_package`, with imported
source paths verified against the candidate manifest. Its environmental guard
permits only read-only Git identity operations and denies network operations.
This first passing package test is not host qualification, historical replay,
condition execution, joined evidence or readiness. More negative binding and
phase-coupling evidence is required. The archive fixture remains exactly 2,034
bytes / `284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb`.
The historical 3,439,137-byte archive remains unavailable and exact historical
replay remains not-run. No image archive, upstream dataset, model or provider
availability is inferred from this input verification.

Candidate continuation, propagation checkpoint (not closure): the four additional
modified paths `src/giclab/control/registry_validation.py`, `consumers.py`,
`production.py`, and `category3.py` carry the explicit `CandidateSourceSnapshot`
through command resolution, assembly identity, and shadow-only preparation. They
are task-owned changes under the newly authorized dependency propagation seam;
the provider registry and historical expected hashes are not changed. Composition,
retained phase entry, condition, and downstream propagation remain incomplete.
The current delta therefore has 26 paths, including the preserved initial 17.

The expanded candidate boundary selection passed 23 tests. A subsequent combined
run of `tests/control/test_candidate_inputs.py` and the existing
`tests/control/test_production_coupling.py` produced **32 passed, 13 failed in
91.29s**, with no skips/xfails. All candidate tests passed; thirteen existing
coupling tests stopped earlier at image/finalizer qualification. Their expected
later behavioral assertions were not reached, so these are not R1–R6 red
characterizations. The qualification failure is being diagnosed; no parity or
inherited-failure classification is inferred from this run.

The isolated candidate subprocess now executes the actual source/package
verifier, actual archive staging, and actual retained regression consumer on the
same bound source. A denied CPython macOS-version observation initially caused
the two fixture evaluator projections to differ. The bootstrap now substitutes
only that exact OS-version file observation and places temporary files beneath
its private input root. The focused subprocess case then passed (1 passed,
7.76s). These remain component/input results, not a joined controller campaign.

Candidate controller-preparation checkpoint (still no joined campaign):
`tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[preparation]`
passed in 20.27s. The subprocess executes the actual full registry validator,
active-version scan, composition, state capsule validator and deterministic
staging proof, followed by the actual archive consumer. Normal `verify_package`
and the normal retained CLI reject candidate input. The same subprocess also
checks all four downstream source roles with the retained no-follow metadata,
finite size and exact byte comparisons. Candidate role records say `git_blob:
null` and bind the candidate digest; they do not claim dirty bytes are Git blobs.

Additional task-owned propagation paths are `src/giclab/control/composition.py`,
`proofs.py`, `state_capsule.py`, and `version_lint.py`. The source-input parameter
selects exact candidate bytes; ordinary invocation retains its previous expected
identities. Historical target selection remains a template reference. Its
read-only metadata inputs are independently compared to the sealed source
snapshot before the existing target selector reads them; it does not accept the
candidate command package as a historical V16 package.

The preparation closure now has 320 explicitly listed members. The original
151-member inventory covered retained package/source verification but not the
full controller preparation corpus. Added inputs are the complete Python scan
roots and Makefile/CI selection surfaces used by active-version lint, every JSON
schema loaded by `local_schema_registry`, all registered plan/profile/command
and execution documents consumed by registry validation, goal/provenance records,
and the active repair regression sources. Their presence does not authorize
executing older workflows or replaying historical experiments. The candidate-only
member limit is 512, with the existing 16 MiB total and 2,000,000-byte member
limits; retained production caps are unchanged. The builder rejects omitted
active Python/schema inputs instead of silently scanning a reduced tree.

Preparation setup rejections (not behavioral R1–R6 failures) identified a missing
consumer parameter, a bound schema read, the incident's regression source, and
default temporary-directory placement. The final preparation run reaches the
actual validators with those inputs recorded and temporary writes confined to
the private test root. The earlier existing coupling failures were diagnosed as
a local/committed selector byte-size mismatch, not a source-role cap overrun.
No parity classification is assigned before the final exact-base cycle.

Candidate boundary checkpoint: the full candidate file subsequently passed
**31 tests in 148.96s**, without skips/xfails. This run includes independent
derived-policy equality checks after an attacker recomputes the outer artifact
hash, stale final argv rejection, source-directory replacement, and a parent
directory replacement during descriptor-held reading. It predates the following
phase/context propagation edits and is not reused as their validation.

Four additional task-owned propagation paths are
`src/giclab/harness/t09_remote_host_phases.py`,
`schemas/t09-host-phase-request.schema.json`,
`src/giclab/control/effects.py`, and `src/giclab/control/shadow_effects.py`.
The current explained delta therefore contains 34 paths including the initial
17. Host requests carry the exact candidate digest in a distinct external
offline mode, with `deterministic_fixture` false. The normal host CLI cannot
select it; only the test bootstrap's typed Python dependency selects candidate
inputs. Normal documents omit the new optional field, retaining their previous
serialization. The shadow context binds the same digest and rejects a candidate
with live authority. The production preparation and transfer compare that
identity; candidate local assembly explicitly reports `tracked_only: false`
and its test classification instead of labelling dirty input bytes as tracked.

The existing host-phase and host-terminal selection passed **21 tests in 1.74s**
after the host phase input propagation. This is component compatibility evidence,
not an execution of the new candidate phase lane. R3 still requires a freeze
predecessor in both orchestration and output validation. R4 joined execution,
R6 output containment, and the remaining integrated requirements of R1/R2/R5
remain unresolved. No full gates, implementation freeze, receipts, commits,
push or PR publication have occurred.

The controller preparation test now also invokes `prepare_category3` with the
production world and actual deterministic archive assembler. It passed in
27.15s, proving two matching local archive renders before any metadata request;
no forward host phase or condition ran. Candidate source identity is now
propagated to the retained provider's existing shadow control dependency in
`src/giclab/harness/t09_pragmatic_provider.py`. It uses the same candidate package
validator, with no normal historical fallback or provider registry change.

Related R4 producer/validator incompatibility characterized:
`tests/control/test_remote_host_phases.py::test_external_generated_outputs_retain_required_provider_entry[host-preflight]`
and `[host-qualify]` both failed because the output validator rejected the
required retained `provider_entry_receipt` input. AST comparison against
`a98b4b875ab4d101709d62bc7222b5c90681a893` confirmed both validator functions were
unchanged at characterization. The earlier fixture setup rejection at output
root containment was corrected before recording the behavioral failures.
These are explicitly component contract tests using existing phase fixtures,
not retained orchestration or joined campaign proof. The narrow source repair
retains the required input and independently revalidates its hash, host and
provider identity in both output validators. The existing test helper now uses
its private temporary root as its remote-root binding, without writing to any
live path. The additional test path and provider source path are task-owned;
the explained continuation is now 36 paths. R1–R6 closure remains blocked.

Candidate retained prefix checkpoint: the new task-owned test adapter/worker
`tests/control/retained_candidate_effects.py` brings the explained delta to
37 paths, with 322 explicit source-input members. It inherits only the existing
environmental provider fixtures and archive assembler on the executed path;
forward qualification, freeze, condition, finalizer/evaluator and failure-export
methods currently fail explicitly before an unbound operation. They cannot
fall through to canned successful component receipts. The active happy-path
transaction test remains failing and is not a completed R4 characterization.

The R3 qualification-start case now fails at the intended terminal-cleanup
assertion (**1 failed in 50.50s**). Controller phase history records successful
local assembly, fake credential/metadata/provider entry, retained transfer and
retained preflight; a deliberate qualification-start fault follows. Actual
`_live_host_cleanup` then rejects the valid preflight predecessor because it
requires `host-freeze`. No freeze file or receipt is fabricated, no condition
is entered, and cleanup stays unresolved. AST comparison confirms both
`_live_host_cleanup` and `validate_host_cleanup_phase` are unchanged from the
reviewed head at this characterization. Earlier setup failures involving the
test remote-secret locator, clock-domain binding, receipt projection and
candidate metadata source identity are not counted as behavioral red evidence.

This exact dirty candidate and its actual phase/provider/journal evidence were
preserved privately: 352 regular files, 9,426,027 bytes, inventory SHA-256
`c196eb7f63e69663b1264f10649ff4b122ddc69b72e4408608d668e7657c63a3`.
Its binding SHA-256 is
`5f78002153c0c9c1137dbd92430e3027d8552a39f93dd5cc9aee37992ed3d6a6`,
source-member manifest SHA-256
`2151b041af1579195567f7b7c909b3126a8d0c7aae754a2a3be11a87b422ea0f`,
dirty-delta SHA-256
`db220588099ea6c8929a7273c4c7f1bbcf5f1129bf64e84baac361419c8ae467`.
Parent remains reviewed HEAD/tree. Generator SHA-256 is
`ade76e3e203e7b18b6b954d97660eaaad767aa46c50a2acef7ae8cadbbcc3edc`,
closure-input SHA-256
`aa0eb0b6415bd4fffba2a4fb3d9d914d3550743f3b3caa7950c78cdfbdef5956`,
and unchanged scientific/policy projection SHA-256
`7fc2759a4a6df2299afcedd933b9ef6593be58a51501a14643df32901b983eae`.
These identify failure evidence, not an implementation ancestor or success receipt.

Current joined-harness seam map:

| Actual path | Lowest substituted dependency | Observable evidence |
| --- | --- | --- |
| `execute_category3_transaction` / `prepare_category3` / production assembly | Explicit sealed candidate input; existing local tar renderer | Controller transitions and two identical held archives before metadata |
| Retained `launch_campaign`, selected campaign transport and entry validation | Existing deterministic provider response transport, fake runtime-created credential bytes, environmental clock | One launch/entry history and durable provider cleanup journal; zero real provider traffic |
| Retained subprocess `host-transfer-verify` / independent archive member rehash | Local copy as SSH carrier | Returned archive/member/ack identities accepted by the same production world |
| Retained subprocess `host-preflight` / actual package and metadata verifiers / pilot initialization | Docker `info` and exact-owned `ps` observations; journal/host wall clock | Actual preflight receipt and journal versions; production acceptance |
| Retained subprocess `host-cleanup` / `_live_host_cleanup` | No cleanup result substituted | Fails at mandatory freeze predecessor; no success receipt |
| Qualification, freeze, four runtime clients, finalizer/evaluator/checkpoint, output containment | Not yet connected | Unproven; not included in a completeness claim |

The provider's candidate-only test secret locator is mechanically derived from
the held test root and launch ordinal before durable registration. Ordinary
provider selection retains its original locator and clean-source checks. The
metadata receipt verifier now takes the same explicit source binding; it still
executes all receipt/source/identity/chronology checks and constructs no model
transport. No historical pin, scientific file or live acceptance criterion was
replaced. The host-phase component file most recently passed **20 tests in
2.25s**, and focused Ruff plus seven-module mypy passed before the final metadata
propagation. Full gates and publication remain not-run.

R3 development after the preserved red candidate: cleanup predecessor admission
now validates the supplied latest transfer/preflight/qualification/freeze/cleanup
receipt, while an omitted predecessor after acknowledged transfer is rejected.
External cleanup output additionally binds and validates the actual durable
journal version. This is partial implementation, not closure: durable proof of
freeze nonpublication, exact-root replacement cases, interrupted cleanup, and the
full failure matrix remain outstanding. Missing archive parents are now represented
as explicit absence in the existing cleanup intent and checked consistently on
resume; a newly appearing parent/file cannot acquire that absent identity.

The same qualification-start controller case continued to fail in 46.87s at an
unconditional archive-parent stat, then in 47.15s when the no-effect guard stopped
an unbound Docker image observation before execution. After the absence repair
and exact environmental image/GPU observation bindings, it failed in 47.73s at
retained cleanup terminal validation. The actual failure projection reports the
test remote secret removed, empty owned-container residue/removal/enumeration
errors, no core-scan failure, and one structural privacy finding:
`source-package.tar:private-network`. The source-input lifecycle is still unresolved;
no privacy validator or exclusion has been changed to hide this finding. The
adapter still refuses to manufacture a successful cleanup projection. These
later failures do not replace the original freeze-predecessor characterization
or establish a completed R3 repair. No forbidden environmental operation ran.

The privacy finding identifies a missing source-transfer input lifecycle, not a
reason to exempt source text from scanning. The next R3 change will bind the
transferred source archive as an exact resource in the existing cleanup journal
and remove only that verified staging copy through retained cleanup. The held
local assembly and its complete member/hash evidence remain retained. This
requires the existing cleanup-state module and its schema (already in the
candidate source closure) to recognize that specific resource role; it does not
add a package-owned cleanup implementation or change privacy acceptance.


The qualification-start controller node now passes (**1 passed in 52.73s**).
It executes the actual retained source archive verifier, host preflight,
host cleanup and provider `closeout_campaign` after the injected qualification
fault. The latter validates its own provider/security observation chain and
reports one termination request, zero remaining provider instances and restored
security under fake provider responses. The adapter maps the retained host and
provider results into the shared cleanup receipt; it does not assert firewall
restoration without that retained closeout. A later controller termination
request observes the retained absence without a duplicate provider mutation.
No condition runs, no freeze receipt is created, and this is one prefix proof,
not the required four-condition integrated campaign or a closed R3 matrix.

The passing dirty source and its actual phase/journal/provider evidence are
preserved privately as 375 regular files / 9,499,142 bytes. Inventory SHA-256:
`55c04e007601b5a16b4278873e04dfed15c26cfb5a604dbd6f5cf6ccfbe374e9`.
Candidate binding: `542d44756d26de8f41692ec8880b62bd684b0a23cac74ba8b8a82d1633272917`.
Source-member manifest: `8e85826b4a22c3ac9407a3dc3f127759db060ef5d5fc802f1e2c735f0426e2ba`.
Dirty delta: `3e507af6c13d62b603e28c5041ed6ccc2c4ecaebe361ddfee38c0fead4af5c26`.
Parent remains reviewed a98b4b8 / b75ce457, not a repaired commit.
The transfer, preflight and cleanup receipt file hashes are respectively
`e2668bb8ddeeb2eb6be998684731ef18011f5d34aef411bc760a02f9b60123b6`,
`08f0973064e92d69cadef4d4bf9e2c9d2a26a9dbe212ea652362ad52020f349d`,
`6bc76bde85ef771dfb6d3e0795f1d92a8933020b561d10c7ef28875521e0a022`.
Retained provider closeout file SHA-256:
`8661cc20d3169652e19d0f7e19165ded6d9fc4e47810509e8f4cbc2de0c25401`.
Every retained phase binds the same candidate digest. The fixture archive and
scientific/policy projection retain their earlier exact identities.

Two additional task-owned modified paths are
`src/giclab/harness/t09_cleanup_state.py` and
`schemas/t09-early-cleanup-state.schema.json`, bringing the explained continuation
to 39 paths. Both were already included in the candidate closure. The new
source-archive resource role uses the existing journal and retained cleanup;
provider continuation recognizes that specific remote-owned role. Its exact
hash/inode/parent identity is checked before removing the staging copy. Replacement
bytes, same-size bytes, replacement file/parent, symlink and missing ownership
are active negative cases. Repeated successful cleanup leaves the journal version
unchanged. The held local source archive and complete transfer evidence remain.

Targeted terminal/host-phase/cleanup-state tests: **48 passed in 2.90s**.
R1/R2/R5 plus archive-fixture selection: **87 passed in 6.17s**.
Focused four-module mypy and Ruff passed after correcting a redundant cast and
an undefined hash helper in the test receipt projection. A prior run reached
successful controller cleanup but failed its obsolete `not-run` projection
assertion (57.09s); another failed at that undefined helper (51.69s). Neither is
new behavioral red evidence. The corrected passing run above supersedes those
harness presentation errors only. Full gates, conformance success receipts,
implementation ancestor, Git commits/push and new CI remain not-run.


Complete candidate closure audit at dirty binding `f5465a065872349c70d1ad40354c343cb5083dd3b28a48ff2e8d1616a51b5d5d` (323 members).
This source snapshot was sealed before the preflight-start fault test; its test
result is separate from this input audit. Historical instrumentation bytes below
are read from `a235d1e6d287b5ea9daf5ca3787f9bbca278f3aa` and independently checked against all 23 frozen
V16 pins. Exactly the eight previously listed paths differ at reviewed HEAD.
Unpinned members are not assigned invented V16 expectations. The initial WIP
column uses the preserved 17-file source delta plus reviewed HEAD for all other
paths. The candidate column names actual sealed bytes, not historical acceptance.
Runtime paths are declared mappings; rows scanned only by validators are labelled
by role and do not claim execution or a container mount. All current phase workers
execute from the corresponding sealed local source paths. Generator/schema and
scientific projection digests remain in the bound manifest.

Private audit inventory SHA-256: `41b7e76b3ba90243b43c9cfc8b19c547f3f08829d982159bd4cfe6a64198fa38`.
The original small 151-member audit above remains historical development evidence;
this complete inventory includes active validator inputs and the added journal
regressions. The new task-owned test path `tests/test_t09_early_cleanup_state.py`
brings the explained Git delta to 40 paths; closure size is 323 members.

| Source path | Declared runtime/mount path | Consumer / role | V16 pin bytes / SHA | Reviewed HEAD bytes / SHA | Starting 17-file WIP bytes / SHA | Sealed candidate bytes / SHA | Scope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `.github/workflows/ci.yml` | `/opt/giclab-project/.github/workflows/ci.yml` | `control-validation-input` / control-validation-input | not an instrumentation pin | 1371 / `004c52a8047e0e02018430171679f3b315447cdebf06e7ffee41cbc4b97ef7a4` | 1371 / `004c52a8047e0e02018430171679f3b315447cdebf06e7ffee41cbc4b97ef7a4` | 1371 / `004c52a8047e0e02018430171679f3b315447cdebf06e7ffee41cbc4b97ef7a4` | unchanged dependency |
| `Makefile` | `/opt/giclab-project/Makefile` | `control-validation-input` / control-validation-input | not an instrumentation pin | 1548 / `14bd220c883191d44eb8e658924f293661197311f78f754c06461ae3cf77c658` | 1548 / `14bd220c883191d44eb8e658924f293661197311f78f754c06461ae3cf77c658` | 1548 / `14bd220c883191d44eb8e658924f293661197311f78f754c06461ae3cf77c658` | unchanged dependency |
| `containers/sira-smoke/bounded/browser_preflight.py` | `/opt/giclab-project/containers/sira-smoke/bounded/browser_preflight.py`<br>`/opt/giclab/browser_preflight.py` | `retained-entrypoint` / retained-entrypoint | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` | 7582 / `327ed96b46736d54e6c763a14733119bcd82e9fbfaa8a88c87c3ac163d17e77f` | unchanged dependency |
| `containers/sira-smoke/container_entrypoint.py` | `/opt/giclab-project/containers/sira-smoke/container_entrypoint.py`<br>`/opt/giclab/container_entrypoint.py` | `retained-entrypoint` / retained-entrypoint | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` | 6393 / `7d7c8b79a120708caa597e503b570fe971b4816ea3fe5ab3453d7d4b26f967a9` | unchanged dependency |
| `containers/sira-smoke/pragmatic/Containerfile.amd64` | `/opt/giclab-project/containers/sira-smoke/pragmatic/Containerfile.amd64` | `historical-template` / historical-template | not an instrumentation pin | 3239 / `7443af988256c6ce64e8f04d4797c7bae3bb3816c3d9f756d65d35ad5da3b4d8` | 3239 / `7443af988256c6ce64e8f04d4797c7bae3bb3816c3d9f756d65d35ad5da3b4d8` | 3239 / `7443af988256c6ce64e8f04d4797c7bae3bb3816c3d9f756d65d35ad5da3b4d8` | unchanged dependency |
| `containers/sira-smoke/pragmatic/materialize_openai_secret.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/materialize_openai_secret.py`<br>`/opt/giclab/materialize_openai_secret.py` | `retained-entrypoint` / retained-entrypoint | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` | 3359 / `6cd57c1be7af02e61e0ed9bffc0e6c4e93a78b9b3567a4bfa26fe6cc030095b6` | unchanged dependency |
| `containers/sira-smoke/pragmatic/python310_import_smoke.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/python310_import_smoke.py`<br>`/opt/giclab/python310_import_smoke.py` | `active-validation-input` / active-validation-input | not an instrumentation pin | 1896 / `106edbe7c6346e15e86c75fec6b87de17712de897c51a11f1ab3b14233d0811e` | 1896 / `106edbe7c6346e15e86c75fec6b87de17712de897c51a11f1ab3b14233d0811e` | 1896 / `106edbe7c6346e15e86c75fec6b87de17712de897c51a11f1ab3b14233d0811e` | unchanged dependency |
| `containers/sira-smoke/pragmatic/remote_runner.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/remote_runner.py`<br>`/opt/giclab/remote_runner.py` | `active-validation-input` / active-validation-input | not an instrumentation pin | 47449 / `9f9abcaa474880f0f292fc2e4475508d699dfa368b47cbc8ced9bbe87400c12d` | 47449 / `9f9abcaa474880f0f292fc2e4475508d699dfa368b47cbc8ced9bbe87400c12d` | 47449 / `9f9abcaa474880f0f292fc2e4475508d699dfa368b47cbc8ced9bbe87400c12d` | unchanged dependency |
| `containers/sira-smoke/pragmatic/runtime_preflight.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/runtime_preflight.py`<br>`/opt/giclab/runtime_preflight.py` | `retained-resource` / retained-resource | not an instrumentation pin | 10711 / `0530b3ad25fac1d3f9372d31da8046bec67b6c74eea3cdd3c8d91353948f1b3d` | 10711 / `0530b3ad25fac1d3f9372d31da8046bec67b6c74eea3cdd3c8d91353948f1b3d` | 10711 / `0530b3ad25fac1d3f9372d31da8046bec67b6c74eea3cdd3c8d91353948f1b3d` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_core_preflight.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_core_preflight.py`<br>`/opt/giclab/t09_core_preflight.py` | `retained-resource` / retained-resource | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` | 8458 / `c2221dd34c094003c47f07a1d1b0b3afae0201d02857e7f91907ed43ee60104e` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_evaluate_attempt.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_evaluate_attempt.py`<br>`/opt/giclab/t09_evaluate_attempt.py` | `retained-resource` / retained-resource | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` | 64497 / `e689a77997d2289a7621323f61d1283eaf45c3d6c887966360a692afea0f4662` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_finalizer_projection.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_finalizer_projection.py`<br>`/opt/giclab/t09_finalizer_projection.py` | `retained-resource` / retained-resource | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` | 24379 / `8a7eee55aca222a134b8f9075efb072fdeff86247c763245001c2efe3e3a3dc0` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_freeze_commands.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_freeze_commands.py`<br>`/opt/giclab/t09_freeze_commands.py` | `retained-resource` / retained-resource | 6695 / `4b593f68a45eccbe8e78df6192508e689448b7d61a41faa622e2ab191e4656ff` | 6812 / `45460760c3ee12e834c995d62e2b368e3ba8c55947fc75758be4324b096b0795` | 6812 / `45460760c3ee12e834c995d62e2b368e3ba8c55947fc75758be4324b096b0795` | 6965 / `0ce8c64a9e1acad7da79fcac8ca5332cca391714c032ba26fca976370edf820d` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py`<br>`/opt/giclab/t09_local_finalizer_qualification.py` | `retained-resource` / retained-resource | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` | 23846 / `a99b46bc73f7e2867e4b4a04771828840b5dda7908e0427a5a3495df3053fce0` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_postrun_evidence_repair.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_postrun_evidence_repair.py`<br>`/opt/giclab/t09_postrun_evidence_repair.py` | `active-validation-input` / active-validation-input | not an instrumentation pin | 39419 / `c2e9d01ffeaa8c11eda2be18afa55c43003fdd9cf0ab7e9bba9f88ab90759c6e` | 39419 / `c2e9d01ffeaa8c11eda2be18afa55c43003fdd9cf0ab7e9bba9f88ab90759c6e` | 39419 / `c2e9d01ffeaa8c11eda2be18afa55c43003fdd9cf0ab7e9bba9f88ab90759c6e` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_preflight.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_preflight.py`<br>`/opt/giclab/t09_preflight.py` | `retained-resource` / retained-resource | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` | 21123 / `fdb2459617c0f7613b2f5149b53c00bf631a20a9c0cd639c774aa8d38e7fcea5` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_prepare_v8.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_prepare_v8.py`<br>`/opt/giclab/t09_prepare_v8.py` | `active-validation-input` / active-validation-input | not an instrumentation pin | 17749 / `a51050afcb4f1f53711ea832a240d0fa4b721a007ade27b05a675e584bb0cfdb` | 17749 / `a51050afcb4f1f53711ea832a240d0fa4b721a007ade27b05a675e584bb0cfdb` | 17749 / `a51050afcb4f1f53711ea832a240d0fa4b721a007ade27b05a675e584bb0cfdb` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_prepare_v9.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_prepare_v9.py`<br>`/opt/giclab/t09_prepare_v9.py` | `active-validation-input` / active-validation-input | not an instrumentation pin | 14552 / `4e67f3eb060eaaa75994458176558c1c68e93bc90ffb00281a594207de4520e9` | 14552 / `4e67f3eb060eaaa75994458176558c1c68e93bc90ffb00281a594207de4520e9` | 14552 / `4e67f3eb060eaaa75994458176558c1c68e93bc90ffb00281a594207de4520e9` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_provider_accounting_preflight.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_provider_accounting_preflight.py`<br>`/opt/giclab/t09_provider_accounting_preflight.py` | `retained-resource` / retained-resource | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` | 6733 / `e74bbb440880c76131af2eead96050334562f81d79a85836489504566bb9f415` | unchanged dependency |
| `containers/sira-smoke/pragmatic/t09_real_evidence_regression.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_real_evidence_regression.py`<br>`/opt/giclab/t09_real_evidence_regression.py` | `retained-resource` / retained-resource | 21892 / `b6a8b571f275894473b81dc547bbacf44db5257cda00d81c22469af2ab31ca50` | 21892 / `b6a8b571f275894473b81dc547bbacf44db5257cda00d81c22469af2ab31ca50` | 24533 / `3e2896f88b3cb011b6970e4fc44057d97ca354ea552b5a686ec889d59637ab6c` | 24533 / `3e2896f88b3cb011b6970e4fc44057d97ca354ea552b5a686ec889d59637ab6c` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `containers/sira-smoke/pragmatic/t09_remote_runner.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_remote_runner.py`<br>`/opt/giclab/t09_remote_runner.py` | `retained-resource` / retained-resource | 1092957 / `ff7bbe48e2f790282a3cb012184653da237801433947391009b4df1f0225269e` | 1163386 / `39a6216acb02ebc86e1e1a07c4db5d4cb2562ba8bcda9acb29787f1941b7d6ef` | 1169602 / `5b3d72cb196c393a1c26289878d860c68366647496f4a8864deaad877b054023` | 1184320 / `c2894244ae06c04e35318af0be0d706144c43b3fd80d618e787ca4f61a3f580e` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `containers/sira-smoke/pragmatic/t09_secret_preflight.py` | `/opt/giclab-project/containers/sira-smoke/pragmatic/t09_secret_preflight.py`<br>`/opt/giclab/t09_secret_preflight.py` | `retained-resource` / retained-resource | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` | 2054 / `b4763ac8edc98b86c2f9f617f53cdb6be2ef9cb26d39aad660442e4c1a7506a4` | unchanged dependency |
| `control/goals/EXP-0001.yaml` | `/opt/giclab-project/control/goals/EXP-0001.yaml` | `control-validation-input` / control-validation-input | not an instrumentation pin | 2732 / `3d0f48adc39e8d553f173f96d4585dbf53f31ea05617b328ae275f33ff6e3ea4` | 3303 / `b34d625389215ae4320f651b7aff3bd4b8e7f8a89472a985527446e7aeb7449d` | 3305 / `34634138cd72a083f39f837a6f5d94ea2a9c4485c4dcdd2749304b1ce4f93ea8` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `control/incidents/INC-T09-CONTROL-FIXED-TARGET-SELECTION.json` | `/opt/giclab-project/control/incidents/INC-T09-CONTROL-FIXED-TARGET-SELECTION.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 2186 / `c7cf0d3f2b3c84e13a7f7877657535284d91cc7fac7a5b6e51c41729b5513681` | 2186 / `c7cf0d3f2b3c84e13a7f7877657535284d91cc7fac7a5b6e51c41729b5513681` | 2186 / `c7cf0d3f2b3c84e13a7f7877657535284d91cc7fac7a5b6e51c41729b5513681` | unchanged dependency |
| `control/incidents/INC-T09-CONTROL-LIVE-BOUNDARY-EXACT-HEAD-REVIEW.json` | `/opt/giclab-project/control/incidents/INC-T09-CONTROL-LIVE-BOUNDARY-EXACT-HEAD-REVIEW.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 5746 / `a78c5f9b6fe1b2274673089cab22ef325fafeebaec79a9d5e94fdca87597d112` | 5746 / `a78c5f9b6fe1b2274673089cab22ef325fafeebaec79a9d5e94fdca87597d112` | 5746 / `a78c5f9b6fe1b2274673089cab22ef325fafeebaec79a9d5e94fdca87597d112` | unchanged dependency |
| `control/incidents/INC-T09-CONTROL-SECOND-EXACT-HEAD-RESIDUAL-BOUNDARY.json` | `/opt/giclab-project/control/incidents/INC-T09-CONTROL-SECOND-EXACT-HEAD-RESIDUAL-BOUNDARY.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 4942 / `f33aada9e8504f7eaf6805ec6df2c561e0be82d523d350533e2c99952402fa66` | 4942 / `f33aada9e8504f7eaf6805ec6df2c561e0be82d523d350533e2c99952402fa66` | 4942 / `f33aada9e8504f7eaf6805ec6df2c561e0be82d523d350533e2c99952402fa66` | unchanged dependency |
| `control/incidents/INC-T09-CONTROL-SHADOW-SHAPED-LIVE-BOUNDARY.json` | `/opt/giclab-project/control/incidents/INC-T09-CONTROL-SHADOW-SHAPED-LIVE-BOUNDARY.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 3490 / `fe5f69d3241032e2216110d1a3a6b47f37b68efb99d54e3541d9825d2ce70a85` | 3490 / `fe5f69d3241032e2216110d1a3a6b47f37b68efb99d54e3541d9825d2ce70a85` | 3490 / `fe5f69d3241032e2216110d1a3a6b47f37b68efb99d54e3541d9825d2ce70a85` | unchanged dependency |
| `control/incidents/INC-T09-CONTROL-THIRD-EXACT-HEAD-RESIDUAL-BOUNDARY.json` | `/opt/giclab-project/control/incidents/INC-T09-CONTROL-THIRD-EXACT-HEAD-RESIDUAL-BOUNDARY.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 4379 / `0c5d3770aed00ada49e31f626287707f2b631ecc2430642d5801f5874d4067e7` | 4379 / `0c5d3770aed00ada49e31f626287707f2b631ecc2430642d5801f5874d4067e7` | 4379 / `0c5d3770aed00ada49e31f626287707f2b631ecc2430642d5801f5874d4067e7` | unchanged dependency |
| `control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json` | `/opt/giclab-project/control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | absent | 4306 / `a25884b25b06b706b43d15570c6b19322ed3a5d60fda713e4fee467e9d9899e4` | 4306 / `a25884b25b06b706b43d15570c6b19322ed3a5d60fda713e4fee467e9d9899e4` | new candidate input/test |
| `control/incidents/INC-T09-V16-LIFECYCLE-REGISTRY.json` | `/opt/giclab-project/control/incidents/INC-T09-V16-LIFECYCLE-REGISTRY.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 1926 / `8cf6280be678bd0cf10666d9b810b468432b60bd6a5dcfad8ac637a1f6449637` | 1926 / `8cf6280be678bd0cf10666d9b810b468432b60bd6a5dcfad8ac637a1f6449637` | 1926 / `8cf6280be678bd0cf10666d9b810b468432b60bd6a5dcfad8ac637a1f6449637` | unchanged dependency |
| `control/incidents/INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE.json` | `/opt/giclab-project/control/incidents/INC-T09-V17-PACKAGE-VIABILITY-SHARED-BRIDGE.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 3767 / `cb0ea2fd42689fe363face18afcf17a02aa8d500beaba0a04a8fe53a0f8ce029` | 3767 / `cb0ea2fd42689fe363face18afcf17a02aa8d500beaba0a04a8fe53a0f8ce029` | 3767 / `cb0ea2fd42689fe363face18afcf17a02aa8d500beaba0a04a8fe53a0f8ce029` | unchanged dependency |
| `docs/harness/T09_CONTROL_PLANE_STABILIZATION_IMPLEMENTATION_LEDGER.md` | `/opt/giclab-project/docs/harness/T09_CONTROL_PLANE_STABILIZATION_IMPLEMENTATION_LEDGER.md` | `control-validation-input` / control-validation-input | not an instrumentation pin | 78318 / `4a35985e0db7132f13ce8e2d16735f84b16015aec498cf71993e2482b59f07df` | 78318 / `4a35985e0db7132f13ce8e2d16735f84b16015aec498cf71993e2482b59f07df` | 78318 / `4a35985e0db7132f13ce8e2d16735f84b16015aec498cf71993e2482b59f07df` | unchanged dependency |
| `docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md` | `/opt/giclab-project/docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md` | `control-validation-input` / control-validation-input | not an instrumentation pin | 16607 / `b2b03c94a222341861aa4b1c1f30922f1dffccb047954ed8af43dbb29e7b7036` | 49363 / `f9864768c3da4720a2cf3c9ccd635af06998934a73ed2175119ce00610a99bb8` | 117038 / `048ec3c185c39a03a24e8c27ce452e3d186cbb79fd332166a7ebac40e1932282` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY4_FINALIZER_REGRESSION.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY4_FINALIZER_REGRESSION.json` | `historical-template` / historical-template | not an instrumentation pin | 8105 / `f6b6da5543dc6014c9069997cc2c4e2630640ec3bf3dbfcbe6b94d57d9565b6b` | 8105 / `f6b6da5543dc6014c9069997cc2c4e2630640ec3bf3dbfcbe6b94d57d9565b6b` | 8105 / `f6b6da5543dc6014c9069997cc2c4e2630640ec3bf3dbfcbe6b94d57d9565b6b` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/T09_V16_PREFLIGHT_STOPPED_DISPOSITION.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/T09_V16_PREFLIGHT_STOPPED_DISPOSITION.json` | `control-validation-input` / control-validation-input | not an instrumentation pin | 2603 / `2354c1aea50139044dcbc9bc8267cd328fba50f889e427dd59ccbd25280378ac` | 2603 / `2354c1aea50139044dcbc9bc8267cd328fba50f889e427dd59ccbd25280378ac` | 2603 / `2354c1aea50139044dcbc9bc8267cd328fba50f889e427dd59ccbd25280378ac` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_COMMAND_MANIFESTS.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_COMMAND_MANIFESTS.json` | `historical-template` / historical-template | not an instrumentation pin | 22501 / `957605950c5fa07840ebf7c2e0829161c0171c9931f6ecaf97e78b3d5c7f0dac` | 22501 / `957605950c5fa07840ebf7c2e0829161c0171c9931f6ecaf97e78b3d5c7f0dac` | 22501 / `957605950c5fa07840ebf7c2e0829161c0171c9931f6ecaf97e78b3d5c7f0dac` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_DATASET_CONTRACT.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_DATASET_CONTRACT.json` | `historical-template` / historical-template | not an instrumentation pin | 4413 / `fac0b6174b8697fd9390c7cf1b3badd6e1cbb2307e08d55e7d00f56e932527aa` | 4413 / `fac0b6174b8697fd9390c7cf1b3badd6e1cbb2307e08d55e7d00f56e932527aa` | 4413 / `fac0b6174b8697fd9390c7cf1b3badd6e1cbb2307e08d55e7d00f56e932527aa` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_EVALUATOR_CONTRACT.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_EVALUATOR_CONTRACT.json` | `historical-template` / historical-template | not an instrumentation pin | 6914 / `c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321` | 6914 / `c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321` | 6914 / `c28a802a45fc8d1e719f8c1bcb22315c2841df831c4ae161f12ab0f2fd08b321` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_EXECUTION_CONTRACT.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_EXECUTION_CONTRACT.json` | `historical-template` / historical-template | not an instrumentation pin | 28441 / `a06bfdc16d6a119474d51965ae2f3c40bf7355cb368313dc7380992c97d5ce36` | 28441 / `a06bfdc16d6a119474d51965ae2f3c40bf7355cb368313dc7380992c97d5ce36` | 28441 / `a06bfdc16d6a119474d51965ae2f3c40bf7355cb368313dc7380992c97d5ce36` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_V8_SCIENCE_PROJECTION.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_V8_SCIENCE_PROJECTION.json` | `historical-template` / historical-template | not an instrumentation pin | 4267 / `1868d73b00ca1afc23f4b010b7238b940bf56428ec32278ce0f98ba50728f8a0` | 4267 / `1868d73b00ca1afc23f4b010b7238b940bf56428ec32278ce0f98ba50728f8a0` | 4267 / `1868d73b00ca1afc23f4b010b7238b940bf56428ec32278ce0f98ba50728f8a0` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_V9_SCIENCE_PROJECTION.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/T09_PILOT_V9_SCIENCE_PROJECTION.json` | `historical-template` / historical-template | not an instrumentation pin | 4267 / `1868d73b00ca1afc23f4b010b7238b940bf56428ec32278ce0f98ba50728f8a0` | 4267 / `1868d73b00ca1afc23f4b010b7238b940bf56428ec32278ce0f98ba50728f8a0` | 4267 / `1868d73b00ca1afc23f4b010b7238b940bf56428ec32278ce0f98ba50728f8a0` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V10.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V10.json` | `historical-template` / historical-template | not an instrumentation pin | 22600 / `9217db4dda7bbf69911743da70e1aeef0507444a02c480ccc7484ec720383844` | 22600 / `9217db4dda7bbf69911743da70e1aeef0507444a02c480ccc7484ec720383844` | 22600 / `9217db4dda7bbf69911743da70e1aeef0507444a02c480ccc7484ec720383844` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V11.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V11.json` | `historical-template` / historical-template | not an instrumentation pin | 22600 / `c36e1417b4668f6a0ae99abd63e4f3c6344c2af6c0942e2ac036633b3817a4e1` | 22600 / `c36e1417b4668f6a0ae99abd63e4f3c6344c2af6c0942e2ac036633b3817a4e1` | 22600 / `c36e1417b4668f6a0ae99abd63e4f3c6344c2af6c0942e2ac036633b3817a4e1` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V12.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V12.json` | `historical-template` / historical-template | not an instrumentation pin | 22928 / `fbca4bced586375508e945cde23b60a62b491d306c7c3dd1405933360360a7d4` | 22928 / `fbca4bced586375508e945cde23b60a62b491d306c7c3dd1405933360360a7d4` | 22928 / `fbca4bced586375508e945cde23b60a62b491d306c7c3dd1405933360360a7d4` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V13.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V13.json` | `historical-template` / historical-template | not an instrumentation pin | 23521 / `b83b6ba6704e30048b11f68f498fadef7b6da2dbc71d2ce02f71db66bc090c28` | 23521 / `b83b6ba6704e30048b11f68f498fadef7b6da2dbc71d2ce02f71db66bc090c28` | 23521 / `b83b6ba6704e30048b11f68f498fadef7b6da2dbc71d2ce02f71db66bc090c28` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V14.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V14.json` | `historical-template` / historical-template | not an instrumentation pin | 23521 / `d8b8b46e04a59ceb49d333bc8a345055f60e8161ba0fea5ea4d260096fe5dddc` | 23521 / `d8b8b46e04a59ceb49d333bc8a345055f60e8161ba0fea5ea4d260096fe5dddc` | 23521 / `d8b8b46e04a59ceb49d333bc8a345055f60e8161ba0fea5ea4d260096fe5dddc` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V15.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V15.json` | `historical-template` / historical-template | not an instrumentation pin | 23521 / `533721a1665c1826502ece26b025859c6fb21b6f3b791d085d2ea294e3f88b4f` | 23521 / `533721a1665c1826502ece26b025859c6fb21b6f3b791d085d2ea294e3f88b4f` | 23521 / `533721a1665c1826502ece26b025859c6fb21b6f3b791d085d2ea294e3f88b4f` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V16.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_COMMAND_MANIFESTS_V16.json`<br>`/opt/giclab-contracts/commands.json` | `historical-template` / historical-template | not an instrumentation pin | 23521 / `377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b` | 23521 / `377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b` | 23521 / `377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V10.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V10.json` | `historical-template` / historical-template | not an instrumentation pin | 28571 / `41810898f2a10a2d328a4d82d338a3a65634c9031e2304a082c1baa50c004e62` | 28571 / `41810898f2a10a2d328a4d82d338a3a65634c9031e2304a082c1baa50c004e62` | 28571 / `41810898f2a10a2d328a4d82d338a3a65634c9031e2304a082c1baa50c004e62` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V11.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V11.json` | `historical-template` / historical-template | not an instrumentation pin | 28844 / `97a1c22064284d0f812e6cac87dae836ad516a423c7ad9f4a0039c696c22b43d` | 28844 / `97a1c22064284d0f812e6cac87dae836ad516a423c7ad9f4a0039c696c22b43d` | 28844 / `97a1c22064284d0f812e6cac87dae836ad516a423c7ad9f4a0039c696c22b43d` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V12.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V12.json` | `historical-template` / historical-template | not an instrumentation pin | 29667 / `3e5d932e0c5d76aa694376be702ce9fa2d681da110360ef21b5a1d23478b71d5` | 29667 / `3e5d932e0c5d76aa694376be702ce9fa2d681da110360ef21b5a1d23478b71d5` | 29667 / `3e5d932e0c5d76aa694376be702ce9fa2d681da110360ef21b5a1d23478b71d5` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V13.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V13.json` | `historical-template` / historical-template | not an instrumentation pin | 29767 / `08ef5ca21382c7cc5a407d79bb9f0d8c0ce61ac09c9d74e22b51ac64bd62b924` | 29767 / `08ef5ca21382c7cc5a407d79bb9f0d8c0ce61ac09c9d74e22b51ac64bd62b924` | 29767 / `08ef5ca21382c7cc5a407d79bb9f0d8c0ce61ac09c9d74e22b51ac64bd62b924` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V14.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V14.json` | `historical-template` / historical-template | not an instrumentation pin | 30541 / `c1cb61b2c6c912517184e493414e730784388dcdc969c31b898a11bf7922fec1` | 30541 / `c1cb61b2c6c912517184e493414e730784388dcdc969c31b898a11bf7922fec1` | 30541 / `c1cb61b2c6c912517184e493414e730784388dcdc969c31b898a11bf7922fec1` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V15.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V15.json` | `historical-template` / historical-template | not an instrumentation pin | 31487 / `a658081b26e0812874fdb3f195896f642283b677b814b0da025bf65b55989629` | 31487 / `a658081b26e0812874fdb3f195896f642283b677b814b0da025bf65b55989629` | 31487 / `a658081b26e0812874fdb3f195896f642283b677b814b0da025bf65b55989629` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V16.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_EXECUTION_CONTRACT_V16.json`<br>`/opt/giclab-contracts/execution.json` | `historical-template` / historical-template | not an instrumentation pin | 31649 / `a2bb10017263b1d3aab09f22a35854d3d78362fec500fbcd49a3d5053336d72e` | 31649 / `a2bb10017263b1d3aab09f22a35854d3d78362fec500fbcd49a3d5053336d72e` | 31649 / `a2bb10017263b1d3aab09f22a35854d3d78362fec500fbcd49a3d5053336d72e` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_RUNTIME_IDENTITY_V16.json` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/contracts/proposals/T09_PILOT_RUNTIME_IDENTITY_V16.json` | `historical-template` / historical-template | not an instrumentation pin | 11150 / `ab4c2f8a93d235c0c00fc24b4d6d10657528b1de9bee656ba611e3311f6fd1f2` | 11150 / `ab4c2f8a93d235c0c00fc24b4d6d10657528b1de9bee656ba611e3311f6fd1f2` | 11150 / `ab4c2f8a93d235c0c00fc24b4d6d10657528b1de9bee656ba611e3311f6fd1f2` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0000-reactive.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0000-reactive.yaml` | `historical-template` / historical-template | not an instrumentation pin | 1526 / `8c0b447b794853e9f69fe9fc665cde632e3c4d0aa9a99a4346d46f345aaf20bf` | 1526 / `8c0b447b794853e9f69fe9fc665cde632e3c4d0aa9a99a4346d46f345aaf20bf` | 1526 / `8c0b447b794853e9f69fe9fc665cde632e3c4d0aa9a99a4346d46f345aaf20bf` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0000-simulative.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0000-simulative.yaml` | `historical-template` / historical-template | not an instrumentation pin | 1532 / `30515859c919b5dd62a821b57efeb39135760c059ee9a05fbe1c6d54b269ca1c` | 1532 / `30515859c919b5dd62a821b57efeb39135760c059ee9a05fbe1c6d54b269ca1c` | 1532 / `30515859c919b5dd62a821b57efeb39135760c059ee9a05fbe1c6d54b269ca1c` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0001-reactive.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0001-reactive.yaml` | `historical-template` / historical-template | not an instrumentation pin | 1526 / `6a3bc1f4775bc27dcb8aaa19770ce43a72e03da0a7466a8eba978121a2d6170d` | 1526 / `6a3bc1f4775bc27dcb8aaa19770ce43a72e03da0a7466a8eba978121a2d6170d` | 1526 / `6a3bc1f4775bc27dcb8aaa19770ce43a72e03da0a7466a8eba978121a2d6170d` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0001-simulative.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/pilot-v16-task-0001-simulative.yaml` | `historical-template` / historical-template | not an instrumentation pin | 1532 / `081af4f0f0477f529b06df136a72042dd792508af33adb3a34bf31d7e3959378` | 1532 / `081af4f0f0477f529b06df136a72042dd792508af33adb3a34bf31d7e3959378` | 1532 / `081af4f0f0477f529b06df136a72042dd792508af33adb3a34bf31d7e3959378` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml` | `historical-template` / historical-template | not an instrumentation pin | 13478 / `28d41a2c2ba8e4b2e0460f78e348064847565e4287f07b685433cd99416c25f5` | 13478 / `28d41a2c2ba8e4b2e0460f78e348064847565e4287f07b685433cd99416c25f5` | 13478 / `28d41a2c2ba8e4b2e0460f78e348064847565e4287f07b685433cd99416c25f5` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V3.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V3.yaml` | `historical-template` / historical-template | not an instrumentation pin | 5270 / `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210` | 5270 / `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210` | 5270 / `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V4.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V4.yaml` | `historical-template` / historical-template | not an instrumentation pin | 6465 / `1ebfbb645ce337d9e99afa5654cddff84a612508d21b70d54cf21dfb99604b77` | 6465 / `1ebfbb645ce337d9e99afa5654cddff84a612508d21b70d54cf21dfb99604b77` | 6465 / `1ebfbb645ce337d9e99afa5654cddff84a612508d21b70d54cf21dfb99604b77` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V5.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V5.yaml` | `historical-template` / historical-template | not an instrumentation pin | 9051 / `e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c` | 9051 / `e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c` | 9051 / `e7e214500348c8b876beb034df7b592c84f5ab79788ab6f310ef187fd797613c` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V6.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V6.yaml` | `historical-template` / historical-template | not an instrumentation pin | 9366 / `d0294b3a1535c4fe4ddfcc856a6b923731a7fb0c7840dd161c5784db61f35d8c` | 9366 / `d0294b3a1535c4fe4ddfcc856a6b923731a7fb0c7840dd161c5784db61f35d8c` | 9366 / `d0294b3a1535c4fe4ddfcc856a6b923731a7fb0c7840dd161c5784db61f35d8c` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V7.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V7.yaml` | `historical-template` / historical-template | not an instrumentation pin | 14046 / `9f66f8f6ee9e137d27e86c5362187fe46d94b26a322994e55222e34c0c4c004e` | 14046 / `9f66f8f6ee9e137d27e86c5362187fe46d94b26a322994e55222e34c0c4c004e` | 14046 / `9f66f8f6ee9e137d27e86c5362187fe46d94b26a322994e55222e34c0c4c004e` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V8.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/PLAN-EXP0001-PILOT-V8.yaml` | `historical-template` / historical-template | not an instrumentation pin | 13456 / `5b77e29e1005979128fa24dbe809bd8b7f92139aa9a49afd68d1daf3de256125` | 13456 / `5b77e29e1005979128fa24dbe809bd8b7f92139aa9a49afd68d1daf3de256125` | 13456 / `5b77e29e1005979128fa24dbe809bd8b7f92139aa9a49afd68d1daf3de256125` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V10.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V10.yaml` | `historical-template` / historical-template | not an instrumentation pin | 13521 / `ef16e0d01227482cd5a99694dd71a0cec53ef28894d80f8665c3b5b1a5c30695` | 13521 / `ef16e0d01227482cd5a99694dd71a0cec53ef28894d80f8665c3b5b1a5c30695` | 13521 / `ef16e0d01227482cd5a99694dd71a0cec53ef28894d80f8665c3b5b1a5c30695` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V11.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V11.yaml` | `historical-template` / historical-template | not an instrumentation pin | 13826 / `726eeef3be208ad22b3279f8192fa55cfba259d14bf85424716b4f3e71a4a850` | 13826 / `726eeef3be208ad22b3279f8192fa55cfba259d14bf85424716b4f3e71a4a850` | 13826 / `726eeef3be208ad22b3279f8192fa55cfba259d14bf85424716b4f3e71a4a850` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V12.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V12.yaml` | `historical-template` / historical-template | not an instrumentation pin | 14485 / `0fd1ce4cd0fbeef41405ac4773d8d2a67b6c0414013b8c4fb4293c5d234446ba` | 14485 / `0fd1ce4cd0fbeef41405ac4773d8d2a67b6c0414013b8c4fb4293c5d234446ba` | 14485 / `0fd1ce4cd0fbeef41405ac4773d8d2a67b6c0414013b8c4fb4293c5d234446ba` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V13.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V13.yaml` | `historical-template` / historical-template | not an instrumentation pin | 14487 / `58159df775f8e3a30debdc327e8be29574ec68a5c34167012866382a09b75ca4` | 14487 / `58159df775f8e3a30debdc327e8be29574ec68a5c34167012866382a09b75ca4` | 14487 / `58159df775f8e3a30debdc327e8be29574ec68a5c34167012866382a09b75ca4` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V14.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V14.yaml` | `historical-template` / historical-template | not an instrumentation pin | 15176 / `b1b5dc0e71954fdcbfe9c5a315f45dfcb09bd3e569fd817cf86efa381a869ee7` | 15176 / `b1b5dc0e71954fdcbfe9c5a315f45dfcb09bd3e569fd817cf86efa381a869ee7` | 15176 / `b1b5dc0e71954fdcbfe9c5a315f45dfcb09bd3e569fd817cf86efa381a869ee7` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V15.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V15.yaml` | `historical-template` / historical-template | not an instrumentation pin | 15974 / `64075a67989522495145bf02c32544bd3a07f30c38d46daa4e9f5c16c65faa1d` | 15974 / `64075a67989522495145bf02c32544bd3a07f30c38d46daa4e9f5c16c65faa1d` | 15974 / `64075a67989522495145bf02c32544bd3a07f30c38d46daa4e9f5c16c65faa1d` | unchanged dependency |
| `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V16.yaml` | `/opt/giclab-project/experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/proposals/T09_PILOT_RUNTIME_PROFILE_V16.yaml` | `historical-template` / historical-template | not an instrumentation pin | 15897 / `80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a` | 15897 / `80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a` | 15897 / `80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a` | unchanged dependency |
| `pyproject.toml` | `/opt/giclab-project/pyproject.toml` | `historical-template` / historical-template | not an instrumentation pin | 1396 / `1e35d1ee8f3788950676aad1ad8200bfd1b1e01bae6e1032363677a1c0c41570` | 1396 / `1e35d1ee8f3788950676aad1ad8200bfd1b1e01bae6e1032363677a1c0c41570` | 1396 / `1e35d1ee8f3788950676aad1ad8200bfd1b1e01bae6e1032363677a1c0c41570` | unchanged dependency |
| `schemas/agent-incident.schema.json` | `/opt/giclab-project/schemas/agent-incident.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 14543 / `3bdb1ecbf8adc4013b280c2c34f3616296d4a9f892d0796be3cc15290a4bc039` | 14597 / `f4a458565d6560654300658878e6a2bf09e647322a7ad0ebc56a686a2c024a0f` | 14597 / `f4a458565d6560654300658878e6a2bf09e647322a7ad0ebc56a686a2c024a0f` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `schemas/agent-state-capsule.schema.json` | `/opt/giclab-project/schemas/agent-state-capsule.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 10875 / `3b87f236fd7f0cc2ebd0eff74fe220557e85fae47278d7dc173acbfe5fe3178d` | 12050 / `eddc056fe270d5813d6fbcea70d4cf74c44ec15c427584aa7c6c949564f0d473` | 12050 / `eddc056fe270d5813d6fbcea70d4cf74c44ec15c427584aa7c6c949564f0d473` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `schemas/artifact.schema.json` | `/opt/giclab-project/schemas/artifact.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2356 / `bc6661bfd857a0bc152248fdb86234781f762ecda6adb4603a81cbb2ddac6dc7` | 2356 / `bc6661bfd857a0bc152248fdb86234781f762ecda6adb4603a81cbb2ddac6dc7` | 2356 / `bc6661bfd857a0bc152248fdb86234781f762ecda6adb4603a81cbb2ddac6dc7` | unchanged dependency |
| `schemas/attempt-close-evidence.schema.json` | `/opt/giclab-project/schemas/attempt-close-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1186 / `66d462b99056df09169c51b2a380a06b0a9ce9f5d2238df329a607f782811935` | 1186 / `66d462b99056df09169c51b2a380a06b0a9ce9f5d2238df329a607f782811935` | 1186 / `66d462b99056df09169c51b2a380a06b0a9ce9f5d2238df329a607f782811935` | unchanged dependency |
| `schemas/cloud-run.schema.json` | `/opt/giclab-project/schemas/cloud-run.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4366 / `9c56416784ac557ee4c71bf3988a21f7c7e6c8f26a25b140041b8a99ede566e6` | 4366 / `9c56416784ac557ee4c71bf3988a21f7c7e6c8f26a25b140041b8a99ede566e6` | 4366 / `9c56416784ac557ee4c71bf3988a21f7c7e6c8f26a25b140041b8a99ede566e6` | unchanged dependency |
| `schemas/compute.schema.json` | `/opt/giclab-project/schemas/compute.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2639 / `4ae7e16140da49ae21229841cf6c3ed404ac7a7af413b7bdaacb876de317e8ef` | 2639 / `4ae7e16140da49ae21229841cf6c3ed404ac7a7af413b7bdaacb876de317e8ef` | 2639 / `4ae7e16140da49ae21229841cf6c3ed404ac7a7af413b7bdaacb876de317e8ef` | unchanged dependency |
| `schemas/container-attempt.schema.json` | `/opt/giclab-project/schemas/container-attempt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 6188 / `7b11b68ba302dd774e7014225c674b89a2d07e57ece533a23239550cb34fc351` | 6188 / `7b11b68ba302dd774e7014225c674b89a2d07e57ece533a23239550cb34fc351` | 6188 / `7b11b68ba302dd774e7014225c674b89a2d07e57ece533a23239550cb34fc351` | unchanged dependency |
| `schemas/container-image-provenance.schema.json` | `/opt/giclab-project/schemas/container-image-provenance.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3071 / `5857bfb88b7524a97290924892375a1fb1eb75615e48073792c99d422b5f99bb` | 3071 / `5857bfb88b7524a97290924892375a1fb1eb75615e48073792c99d422b5f99bb` | 3071 / `5857bfb88b7524a97290924892375a1fb1eb75615e48073792c99d422b5f99bb` | unchanged dependency |
| `schemas/container-materialization-plan.schema.json` | `/opt/giclab-project/schemas/container-materialization-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1484 / `125292f2f2242baf457ecd77e2b096585deb27023fdfa9dbea2217393ef12320` | 1484 / `125292f2f2242baf457ecd77e2b096585deb27023fdfa9dbea2217393ef12320` | 1484 / `125292f2f2242baf457ecd77e2b096585deb27023fdfa9dbea2217393ef12320` | unchanged dependency |
| `schemas/container-platform-decision.schema.json` | `/opt/giclab-project/schemas/container-platform-decision.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5276 / `e436f76c30563eede79196d5bc1d1e222ea703ba4d78db7750c94c2cb28cfcbc` | 5276 / `e436f76c30563eede79196d5bc1d1e222ea703ba4d78db7750c94c2cb28cfcbc` | 5276 / `e436f76c30563eede79196d5bc1d1e222ea703ba4d78db7750c94c2cb28cfcbc` | unchanged dependency |
| `schemas/docker-storage-placement-evidence.schema.json` | `/opt/giclab-project/schemas/docker-storage-placement-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2519 / `2aba7f1134ef5390d22bf04c6fd246e25a91517caf3d93ad17899f11888bc5e5` | 2519 / `2aba7f1134ef5390d22bf04c6fd246e25a91517caf3d93ad17899f11888bc5e5` | 2519 / `2aba7f1134ef5390d22bf04c6fd246e25a91517caf3d93ad17899f11888bc5e5` | unchanged dependency |
| `schemas/docker-storage-qualification-plan.schema.json` | `/opt/giclab-project/schemas/docker-storage-qualification-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 11055 / `4b5732b38fc48f025ea326757ebe54c328801db6bd831c59f39e769c7175c12c` | 11055 / `4b5732b38fc48f025ea326757ebe54c328801db6bd831c59f39e769c7175c12c` | 11055 / `4b5732b38fc48f025ea326757ebe54c328801db6bd831c59f39e769c7175c12c` | unchanged dependency |
| `schemas/experiment.schema.json` | `/opt/giclab-project/schemas/experiment.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5601 / `9bcd5be8f98e7fd3a08084ccef18edc52e1a6b72cadffbcf0907b093b1ff686f` | 5601 / `9bcd5be8f98e7fd3a08084ccef18edc52e1a6b72cadffbcf0907b093b1ff686f` | 5601 / `9bcd5be8f98e7fd3a08084ccef18edc52e1a6b72cadffbcf0907b093b1ff686f` | unchanged dependency |
| `schemas/harness-event.schema.json` | `/opt/giclab-project/schemas/harness-event.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 18998 / `0f5e0e29a516be129adce00f60d4f5ddadc4a24f6ca81b91bbf7e751b15fe84f` | 18998 / `0f5e0e29a516be129adce00f60d4f5ddadc4a24f6ca81b91bbf7e751b15fe84f` | 18998 / `0f5e0e29a516be129adce00f60d4f5ddadc4a24f6ca81b91bbf7e751b15fe84f` | unchanged dependency |
| `schemas/manifest.schema.json` | `/opt/giclab-project/schemas/manifest.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2498 / `cafee9dfa716a58335b5515997145c6b6faf8d84543aeb979f1bce1d95f6ea86` | 2498 / `cafee9dfa716a58335b5515997145c6b6faf8d84543aeb979f1bce1d95f6ea86` | 2498 / `cafee9dfa716a58335b5515997145c6b6faf8d84543aeb979f1bce1d95f6ea86` | unchanged dependency |
| `schemas/pricing.schema.json` | `/opt/giclab-project/schemas/pricing.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2562 / `6e2c892b0d022a99c52fb985e9b603b1a2e80c0edb44d72f98ad1ed76a205483` | 2562 / `6e2c892b0d022a99c52fb985e9b603b1a2e80c0edb44d72f98ad1ed76a205483` | 2562 / `6e2c892b0d022a99c52fb985e9b603b1a2e80c0edb44d72f98ad1ed76a205483` | unchanged dependency |
| `schemas/run-plan.schema.json` | `/opt/giclab-project/schemas/run-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 7202 / `f8e7dc18c932f6972bcba379233ebf5c0e2b2a6ba51c941bf12bb1023ec823ec` | 7202 / `f8e7dc18c932f6972bcba379233ebf5c0e2b2a6ba51c941bf12bb1023ec823ec` | 7202 / `f8e7dc18c932f6972bcba379233ebf5c0e2b2a6ba51c941bf12bb1023ec823ec` | unchanged dependency |
| `schemas/run-profile.schema.json` | `/opt/giclab-project/schemas/run-profile.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 36809 / `4dadbc430c15e42c0383ab2632fa64bd5b8096d5a350e7050ea8c5301ed49aa4` | 36809 / `4dadbc430c15e42c0383ab2632fa64bd5b8096d5a350e7050ea8c5301ed49aa4` | 36809 / `4dadbc430c15e42c0383ab2632fa64bd5b8096d5a350e7050ea8c5301ed49aa4` | unchanged dependency |
| `schemas/runtime-candidate-decision.schema.json` | `/opt/giclab-project/schemas/runtime-candidate-decision.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 6674 / `0e982793b14a0496c26aa1a352425b20de4cd09aaec5c69274f8370d48b357f2` | 6674 / `0e982793b14a0496c26aa1a352425b20de4cd09aaec5c69274f8370d48b357f2` | 6674 / `0e982793b14a0496c26aa1a352425b20de4cd09aaec5c69274f8370d48b357f2` | unchanged dependency |
| `schemas/runtime-rollback-evidence.schema.json` | `/opt/giclab-project/schemas/runtime-rollback-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1867 / `70de4d5c7b2fb5103879367e04955db3d79d757468cd823f5f4b2423cc07d5eb` | 1867 / `70de4d5c7b2fb5103879367e04955db3d79d757468cd823f5f4b2423cc07d5eb` | 1867 / `70de4d5c7b2fb5103879367e04955db3d79d757468cd823f5f4b2423cc07d5eb` | unchanged dependency |
| `schemas/sealed-artifact-copy.schema.json` | `/opt/giclab-project/schemas/sealed-artifact-copy.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1981 / `f8fa564fa0d5f8ea6758a44e29756baee18e1b88bdc3b8724ec5720f236b3ed8` | 1981 / `f8fa564fa0d5f8ea6758a44e29756baee18e1b88bdc3b8724ec5720f236b3ed8` | 1981 / `f8fa564fa0d5f8ea6758a44e29756baee18e1b88bdc3b8724ec5720f236b3ed8` | unchanged dependency |
| `schemas/t07-bounded-openai-secret-source.schema.json` | `/opt/giclab-project/schemas/t07-bounded-openai-secret-source.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4411 / `38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4` | 4411 / `38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4` | 4411 / `38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4` | unchanged dependency |
| `schemas/t07-bounded-private-security-binding.schema.json` | `/opt/giclab-project/schemas/t07-bounded-private-security-binding.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5425 / `ee09d8413b44dc66d1cefaad92b81f418e9e0ae0df98413a354a97ea32da350b` | 5425 / `ee09d8413b44dc66d1cefaad92b81f418e9e0ae0df98413a354a97ea32da350b` | 5425 / `ee09d8413b44dc66d1cefaad92b81f418e9e0ae0df98413a354a97ea32da350b` | unchanged dependency |
| `schemas/t07-bounded-smoke-authorization-v2.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-authorization-v2.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3293 / `cad71bc9e9ba365be30d8136d808f9ab51ed5fcfa57ee36437d730be46226dee` | 3293 / `cad71bc9e9ba365be30d8136d808f9ab51ed5fcfa57ee36437d730be46226dee` | 3293 / `cad71bc9e9ba365be30d8136d808f9ab51ed5fcfa57ee36437d730be46226dee` | unchanged dependency |
| `schemas/t07-bounded-smoke-authorization-v3.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-authorization-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3293 / `a11268f5abefd590223c370df9467bf3d8d6d641cfa1667c344f569666e464f0` | 3293 / `a11268f5abefd590223c370df9467bf3d8d6d641cfa1667c344f569666e464f0` | 3293 / `a11268f5abefd590223c370df9467bf3d8d6d641cfa1667c344f569666e464f0` | unchanged dependency |
| `schemas/t07-bounded-smoke-authorization.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-authorization.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3290 / `8b542cd152818304761a1bc11027a1abfa7187cf49698929fb11fedbfed13b09` | 3290 / `8b542cd152818304761a1bc11027a1abfa7187cf49698929fb11fedbfed13b09` | 3290 / `8b542cd152818304761a1bc11027a1abfa7187cf49698929fb11fedbfed13b09` | unchanged dependency |
| `schemas/t07-bounded-smoke-evidence-v2.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-evidence-v2.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1426 / `803d74577d6bb90daaee2b61c15c65abfff3680e4ebefea7137d81bb7d99ad49` | 1426 / `803d74577d6bb90daaee2b61c15c65abfff3680e4ebefea7137d81bb7d99ad49` | 1426 / `803d74577d6bb90daaee2b61c15c65abfff3680e4ebefea7137d81bb7d99ad49` | unchanged dependency |
| `schemas/t07-bounded-smoke-evidence-v3.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-evidence-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1426 / `05fb95e411eb7fba24fe96ab66323943622d4e10c8c2fcc1a5f2e599283f3e41` | 1426 / `05fb95e411eb7fba24fe96ab66323943622d4e10c8c2fcc1a5f2e599283f3e41` | 1426 / `05fb95e411eb7fba24fe96ab66323943622d4e10c8c2fcc1a5f2e599283f3e41` | unchanged dependency |
| `schemas/t07-bounded-smoke-evidence.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1423 / `3f1b710ca9256696a56936a8fcbb71f9eed7fc36392579ed50ca0767df30d22e` | 1423 / `3f1b710ca9256696a56936a8fcbb71f9eed7fc36392579ed50ca0767df30d22e` | 1423 / `3f1b710ca9256696a56936a8fcbb71f9eed7fc36392579ed50ca0767df30d22e` | unchanged dependency |
| `schemas/t07-bounded-smoke-observer-ledger-v2.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-observer-ledger-v2.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3315 / `44c71d2fea9b216badca84fa867ab95dedfaa4309455dba59c72e219c5e6c6b9` | 3315 / `44c71d2fea9b216badca84fa867ab95dedfaa4309455dba59c72e219c5e6c6b9` | 3315 / `44c71d2fea9b216badca84fa867ab95dedfaa4309455dba59c72e219c5e6c6b9` | unchanged dependency |
| `schemas/t07-bounded-smoke-observer-ledger-v3.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-observer-ledger-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3315 / `dc62fc35bc730920bf3548cf4cdb5efb5832c1aa3b7fffc7c44d1336e5efd687` | 3315 / `dc62fc35bc730920bf3548cf4cdb5efb5832c1aa3b7fffc7c44d1336e5efd687` | 3315 / `dc62fc35bc730920bf3548cf4cdb5efb5832c1aa3b7fffc7c44d1336e5efd687` | unchanged dependency |
| `schemas/t07-bounded-smoke-observer-ledger.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-observer-ledger.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3312 / `2d9ad9e1e43d7a229ee2ebfb44af82b5f7e6234300bd9a14d1072e0a53c4ad61` | 3312 / `2d9ad9e1e43d7a229ee2ebfb44af82b5f7e6234300bd9a14d1072e0a53c4ad61` | 3312 / `2d9ad9e1e43d7a229ee2ebfb44af82b5f7e6234300bd9a14d1072e0a53c4ad61` | unchanged dependency |
| `schemas/t07-bounded-smoke-plan-v2.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-plan-v2.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 12768 / `2d0bf1b934c6df81b0f9b6a9aa9e91ed6b2c61fb1641f15b55cca6038718978b` | 12768 / `2d0bf1b934c6df81b0f9b6a9aa9e91ed6b2c61fb1641f15b55cca6038718978b` | 12768 / `2d0bf1b934c6df81b0f9b6a9aa9e91ed6b2c61fb1641f15b55cca6038718978b` | unchanged dependency |
| `schemas/t07-bounded-smoke-plan-v3.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-plan-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 12768 / `782aad70602e6e9ccb9eef1ffeb7cb5a8a7ce3fd7bef0698acd19a49981128c3` | 12768 / `782aad70602e6e9ccb9eef1ffeb7cb5a8a7ce3fd7bef0698acd19a49981128c3` | 12768 / `782aad70602e6e9ccb9eef1ffeb7cb5a8a7ce3fd7bef0698acd19a49981128c3` | unchanged dependency |
| `schemas/t07-bounded-smoke-plan.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 11572 / `225c81bb21c5a361ec7c96adcd9eca29c0953b3874c657ed78cb2dc6bea0a71d` | 11572 / `225c81bb21c5a361ec7c96adcd9eca29c0953b3874c657ed78cb2dc6bea0a71d` | 11572 / `225c81bb21c5a361ec7c96adcd9eca29c0953b3874c657ed78cb2dc6bea0a71d` | unchanged dependency |
| `schemas/t07-bounded-smoke-private-binding.schema.json` | `/opt/giclab-project/schemas/t07-bounded-smoke-private-binding.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3415 / `39e9f8ea7205e924fef25995b6c801196b35f85473e32ce58d18ed110a857b43` | 3415 / `39e9f8ea7205e924fef25995b6c801196b35f85473e32ce58d18ed110a857b43` | 3415 / `39e9f8ea7205e924fef25995b6c801196b35f85473e32ce58d18ed110a857b43` | unchanged dependency |
| `schemas/t07-lambda-audit-structural-report.schema.json` | `/opt/giclab-project/schemas/t07-lambda-audit-structural-report.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2634 / `8ac8097b79e4e211ebf3cb1e9d39fcaad72f504f7bb9edc442f2cdb1440d1e08` | 2634 / `8ac8097b79e4e211ebf3cb1e9d39fcaad72f504f7bb9edc442f2cdb1440d1e08` | 2634 / `8ac8097b79e4e211ebf3cb1e9d39fcaad72f504f7bb9edc442f2cdb1440d1e08` | unchanged dependency |
| `schemas/t07-lambda-firewall-assessment.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-assessment.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3928 / `accb3017777429de71861018222190f17a7338d53d3515e624001a48393d5095` | 3928 / `accb3017777429de71861018222190f17a7338d53d3515e624001a48393d5095` | 3928 / `accb3017777429de71861018222190f17a7338d53d3515e624001a48393d5095` | unchanged dependency |
| `schemas/t07-lambda-firewall-baseline-capture-ledger.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-baseline-capture-ledger.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3107 / `3b0456ef742d8a02f5465dc04f176fe189b2f8538d2d4895a4098ea17c987ee0` | 3107 / `3b0456ef742d8a02f5465dc04f176fe189b2f8538d2d4895a4098ea17c987ee0` | 3107 / `3b0456ef742d8a02f5465dc04f176fe189b2f8538d2d4895a4098ea17c987ee0` | unchanged dependency |
| `schemas/t07-lambda-firewall-baseline.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-baseline.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5227 / `bc5865b12e6f0205e868f65eec8ad6107bf2e43a6ef07c9392b073f45b192b44` | 5227 / `bc5865b12e6f0205e868f65eec8ad6107bf2e43a6ef07c9392b073f45b192b44` | 5227 / `bc5865b12e6f0205e868f65eec8ad6107bf2e43a6ef07c9392b073f45b192b44` | unchanged dependency |
| `schemas/t07-lambda-firewall-canonical-report.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-canonical-report.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5262 / `3fad2ca8f48845fd7394cbd29357f47f9a6be2db90e740a5eb1faa915a8b9a22` | 5262 / `3fad2ca8f48845fd7394cbd29357f47f9a6be2db90e740a5eb1faa915a8b9a22` | 5262 / `3fad2ca8f48845fd7394cbd29357f47f9a6be2db90e740a5eb1faa915a8b9a22` | unchanged dependency |
| `schemas/t07-lambda-firewall-capture-adjudication.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-capture-adjudication.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4283 / `f6f1ed2d98bccccf15b74f62c365f3f4d4a50d86dc082b21ccbc466a0ff1a00c` | 4283 / `f6f1ed2d98bccccf15b74f62c365f3f4d4a50d86dc082b21ccbc466a0ff1a00c` | 4283 / `f6f1ed2d98bccccf15b74f62c365f3f4d4a50d86dc082b21ccbc466a0ff1a00c` | unchanged dependency |
| `schemas/t07-lambda-firewall-public-structural-report.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-public-structural-report.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4338 / `2a7eb28f6104d8b0664ca52f1e1ff96a7747e59b81efa421a6714f4e565cbc34` | 4338 / `2a7eb28f6104d8b0664ca52f1e1ff96a7747e59b81efa421a6714f4e565cbc34` | 4338 / `2a7eb28f6104d8b0664ca52f1e1ff96a7747e59b81efa421a6714f4e565cbc34` | unchanged dependency |
| `schemas/t07-lambda-firewall-restoration-payload.schema.json` | `/opt/giclab-project/schemas/t07-lambda-firewall-restoration-payload.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1412 / `b1dca29f4912cd24338b3475c667421eb10bae1ef64da67ce058a5299ce8261c` | 1412 / `b1dca29f4912cd24338b3475c667421eb10bae1ef64da67ce058a5299ce8261c` | 1412 / `b1dca29f4912cd24338b3475c667421eb10bae1ef64da67ce058a5299ce8261c` | unchanged dependency |
| `schemas/t07-lambda-host-qualification-incident.schema.json` | `/opt/giclab-project/schemas/t07-lambda-host-qualification-incident.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 16783 / `21c6402e38414dad1ba1f6dc17c5967d049654a83238a85a4f9c565d2afe0c1d` | 16783 / `21c6402e38414dad1ba1f6dc17c5967d049654a83238a85a4f9c565d2afe0c1d` | 16783 / `21c6402e38414dad1ba1f6dc17c5967d049654a83238a85a4f9c565d2afe0c1d` | unchanged dependency |
| `schemas/t07-lambda-host-qualification.schema.json` | `/opt/giclab-project/schemas/t07-lambda-host-qualification.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 31082 / `704d780acc7669025ca2ac8b41a1ad70446a0641688a151fecd0e8d18adc427a` | 31082 / `704d780acc7669025ca2ac8b41a1ad70446a0641688a151fecd0e8d18adc427a` | 31082 / `704d780acc7669025ca2ac8b41a1ad70446a0641688a151fecd0e8d18adc427a` | unchanged dependency |
| `schemas/t07-lambda-image-identity-adjudication.schema.json` | `/opt/giclab-project/schemas/t07-lambda-image-identity-adjudication.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4446 / `554f5ef4e456f75339ccf20eb2f44e9e0e7db7e6fefb0fbb4b41cefe2ad3d2ea` | 4446 / `554f5ef4e456f75339ccf20eb2f44e9e0e7db7e6fefb0fbb4b41cefe2ad3d2ea` | 4446 / `554f5ef4e456f75339ccf20eb2f44e9e0e7db7e6fefb0fbb4b41cefe2ad3d2ea` | unchanged dependency |
| `schemas/t07-lambda-inventory-v2.schema.json` | `/opt/giclab-project/schemas/t07-lambda-inventory-v2.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 14597 / `bbbe2516956658afa3d972c46a7a306eb769c4b17b95ec0171c85d29df161be6` | 14597 / `bbbe2516956658afa3d972c46a7a306eb769c4b17b95ec0171c85d29df161be6` | 14597 / `bbbe2516956658afa3d972c46a7a306eb769c4b17b95ec0171c85d29df161be6` | unchanged dependency |
| `schemas/t07-lambda-inventory-v3.schema.json` | `/opt/giclab-project/schemas/t07-lambda-inventory-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 21486 / `53db8500f6ef98f440cde80022442aa55dae26d4de5e703c014b744aa88b4c3b` | 21486 / `53db8500f6ef98f440cde80022442aa55dae26d4de5e703c014b744aa88b4c3b` | 21486 / `53db8500f6ef98f440cde80022442aa55dae26d4de5e703c014b744aa88b4c3b` | unchanged dependency |
| `schemas/t07-lambda-inventory.schema.json` | `/opt/giclab-project/schemas/t07-lambda-inventory.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 12959 / `180c634365edc83ebb8f3a9173a1856a00d0758e352e45439c67106f1763261e` | 12959 / `180c634365edc83ebb8f3a9173a1856a00d0758e352e45439c67106f1763261e` | 12959 / `180c634365edc83ebb8f3a9173a1856a00d0758e352e45439c67106f1763261e` | unchanged dependency |
| `schemas/t07-lambda-l2-host-evidence.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-host-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 6848 / `850f995b852cf874a437b1a70a590062985191ed736301857a80ad540bbee1ad` | 6848 / `850f995b852cf874a437b1a70a590062985191ed736301857a80ad540bbee1ad` | 6848 / `850f995b852cf874a437b1a70a590062985191ed736301857a80ad540bbee1ad` | unchanged dependency |
| `schemas/t07-lambda-l2-host-key-checkpoint.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-host-key-checkpoint.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1341 / `74d875ecd80c671d6a9908d9f471220bdf65e5dab293cbe53c1173a98075474a` | 1341 / `74d875ecd80c671d6a9908d9f471220bdf65e5dab293cbe53c1173a98075474a` | 1341 / `74d875ecd80c671d6a9908d9f471220bdf65e5dab293cbe53c1173a98075474a` | unchanged dependency |
| `schemas/t07-lambda-l2-human-decision.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-human-decision.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2367 / `b67c95702677aa285c3a017e36ae779b1418cf3919c1ad55ca9c6d729cdeadd0` | 2367 / `b67c95702677aa285c3a017e36ae779b1418cf3919c1ad55ca9c6d729cdeadd0` | 2367 / `b67c95702677aa285c3a017e36ae779b1418cf3919c1ad55ca9c6d729cdeadd0` | unchanged dependency |
| `schemas/t07-lambda-l2-incident.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-incident.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3754 / `18e0cc81273ecfeead1ae3130694ae7d599936fe76d863fd14e4bfb1cdd6166a` | 3754 / `18e0cc81273ecfeead1ae3130694ae7d599936fe76d863fd14e4bfb1cdd6166a` | 3754 / `18e0cc81273ecfeead1ae3130694ae7d599936fe76d863fd14e4bfb1cdd6166a` | unchanged dependency |
| `schemas/t07-lambda-l2-launch-recovery-decision.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-launch-recovery-decision.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2044 / `400e796e3082740a391a9055d8547cb684a6f7e18087a56627d2d5b97cc9f93f` | 2044 / `400e796e3082740a391a9055d8547cb684a6f7e18087a56627d2d5b97cc9f93f` | 2044 / `400e796e3082740a391a9055d8547cb684a6f7e18087a56627d2d5b97cc9f93f` | unchanged dependency |
| `schemas/t07-lambda-l2-plan.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4233 / `a89d218d263a54ea67efa281e8a48b22656963e3d518f9c8daa4543b7307a27c` | 4233 / `a89d218d263a54ea67efa281e8a48b22656963e3d518f9c8daa4543b7307a27c` | 4233 / `a89d218d263a54ea67efa281e8a48b22656963e3d518f9c8daa4543b7307a27c` | unchanged dependency |
| `schemas/t07-lambda-l2-private-parameters.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-private-parameters.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9107 / `53bb07e9654436eb9a3d940a3c5bd4c55eb7caf234198ee32e5bc04837ecab6b` | 9107 / `53bb07e9654436eb9a3d940a3c5bd4c55eb7caf234198ee32e5bc04837ecab6b` | 9107 / `53bb07e9654436eb9a3d940a3c5bd4c55eb7caf234198ee32e5bc04837ecab6b` | unchanged dependency |
| `schemas/t07-lambda-l2-provider-ledger.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-provider-ledger.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4314 / `4daae7f0fe480b57e00aa19091e75acd7d16e7a387dc5ff924961051a755521b` | 4314 / `4daae7f0fe480b57e00aa19091e75acd7d16e7a387dc5ff924961051a755521b` | 4314 / `4daae7f0fe480b57e00aa19091e75acd7d16e7a387dc5ff924961051a755521b` | unchanged dependency |
| `schemas/t07-lambda-l2-transaction-journal.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-transaction-journal.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3725 / `4bcd29ef24c53ff327be0ff47124cba23f576602e77658dabaa984337a07c7d4` | 3725 / `4bcd29ef24c53ff327be0ff47124cba23f576602e77658dabaa984337a07c7d4` | 3725 / `4bcd29ef24c53ff327be0ff47124cba23f576602e77658dabaa984337a07c7d4` | unchanged dependency |
| `schemas/t07-lambda-l2-watchdog-journal.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2-watchdog-journal.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3025 / `3d7bfc77b7acb4e07d5629bb86413742ea49df7d071e36b128792786016236a1` | 3025 / `3d7bfc77b7acb4e07d5629bb86413742ea49df7d071e36b128792786016236a1` | 3025 / `3d7bfc77b7acb4e07d5629bb86413742ea49df7d071e36b128792786016236a1` | unchanged dependency |
| `schemas/t07-lambda-l2m-checkpoint.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-checkpoint.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 15890 / `a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff` | 15890 / `a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff` | 15890 / `a55f9023f8cc8f530acebe31bbe7b50c57d1e1a01b959ced38876e43e0f108ff` | unchanged dependency |
| `schemas/t07-lambda-l2m-host-evidence.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-host-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 10572 / `5c74fb37b81be2ae3fa2563a5b7508f13d19d2dd764a475e5c07e45b369bd195` | 10572 / `5c74fb37b81be2ae3fa2563a5b7508f13d19d2dd764a475e5c07e45b369bd195` | 10572 / `5c74fb37b81be2ae3fa2563a5b7508f13d19d2dd764a475e5c07e45b369bd195` | unchanged dependency |
| `schemas/t07-lambda-l2m-human-decision.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-human-decision.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3183 / `7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79` | 3183 / `7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79` | 3183 / `7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79` | unchanged dependency |
| `schemas/t07-lambda-l2m-observer-journal.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-observer-journal.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 7005 / `5de43193d400e067ce84acd19dfba0128125cf79d3bc6d862176e7895d20473e` | 7005 / `5de43193d400e067ce84acd19dfba0128125cf79d3bc6d862176e7895d20473e` | 7005 / `5de43193d400e067ce84acd19dfba0128125cf79d3bc6d862176e7895d20473e` | unchanged dependency |
| `schemas/t07-lambda-l2m-private-decision-seal-v2.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-private-decision-seal-v2.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3716 / `6fb6cc73ccd4332287014ca5aea945485f6548b5052a2fdfc32378eef5403ead` | 3716 / `6fb6cc73ccd4332287014ca5aea945485f6548b5052a2fdfc32378eef5403ead` | 3716 / `6fb6cc73ccd4332287014ca5aea945485f6548b5052a2fdfc32378eef5403ead` | unchanged dependency |
| `schemas/t07-lambda-l2m-private-decision-seal-v3.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-private-decision-seal-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3716 / `d67f3cbd6811f0b8c965c84fc0cb62823981442de55cd7233f17689782b624ac` | 3716 / `d67f3cbd6811f0b8c965c84fc0cb62823981442de55cd7233f17689782b624ac` | 3716 / `d67f3cbd6811f0b8c965c84fc0cb62823981442de55cd7233f17689782b624ac` | unchanged dependency |
| `schemas/t07-lambda-l2m-private-decision-seal.schema.json` | `/opt/giclab-project/schemas/t07-lambda-l2m-private-decision-seal.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3713 / `e4bc66c5759fe700e62ba2bb54dec1c509c68f7f63308170195c6454c607ca3f` | 3713 / `e4bc66c5759fe700e62ba2bb54dec1c509c68f7f63308170195c6454c607ca3f` | 3713 / `e4bc66c5759fe700e62ba2bb54dec1c509c68f7f63308170195c6454c607ca3f` | unchanged dependency |
| `schemas/t07-lambda-owned-launch-marker.schema.json` | `/opt/giclab-project/schemas/t07-lambda-owned-launch-marker.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3205 / `09b57927f1988901b1c5b8304242aae940c6b21184d8ff70a93e0a4029e0677a` | 3205 / `09b57927f1988901b1c5b8304242aae940c6b21184d8ff70a93e0a4029e0677a` | 3205 / `09b57927f1988901b1c5b8304242aae940c6b21184d8ff70a93e0a4029e0677a` | unchanged dependency |
| `schemas/t07-lambda-request-ledger-v3.schema.json` | `/opt/giclab-project/schemas/t07-lambda-request-ledger-v3.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9683 / `aa3208546cfa3ba171bd6c7b5af67124260e25cb3d32c8989b34d0ad6ce89a0d` | 9683 / `aa3208546cfa3ba171bd6c7b5af67124260e25cb3d32c8989b34d0ad6ce89a0d` | 9683 / `aa3208546cfa3ba171bd6c7b5af67124260e25cb3d32c8989b34d0ad6ce89a0d` | unchanged dependency |
| `schemas/t07-lambda-request-ledger.schema.json` | `/opt/giclab-project/schemas/t07-lambda-request-ledger.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9746 / `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73` | 9746 / `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73` | 9746 / `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73` | unchanged dependency |
| `schemas/t07-lambda-resource-candidate-matrix.schema.json` | `/opt/giclab-project/schemas/t07-lambda-resource-candidate-matrix.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5059 / `d7d6e34e4f0ed15e9edc7083002527eb38f5694d268102a6d29a0d47f53b674f` | 5059 / `d7d6e34e4f0ed15e9edc7083002527eb38f5694d268102a6d29a0d47f53b674f` | 5059 / `d7d6e34e4f0ed15e9edc7083002527eb38f5694d268102a6d29a0d47f53b674f` | unchanged dependency |
| `schemas/t07-lambda-schema-extension-report.schema.json` | `/opt/giclab-project/schemas/t07-lambda-schema-extension-report.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2444 / `74ac1e1d2c5f7bb761335206543648a3ddcfb94149a5268e61c669d14777ed64` | 2444 / `74ac1e1d2c5f7bb761335206543648a3ddcfb94149a5268e61c669d14777ed64` | 2444 / `74ac1e1d2c5f7bb761335206543648a3ddcfb94149a5268e61c669d14777ed64` | unchanged dependency |
| `schemas/t07-lambda-ssh-key-fingerprint.schema.json` | `/opt/giclab-project/schemas/t07-lambda-ssh-key-fingerprint.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 6472 / `a7a940a12f4a77895661b9e11883495c7f1efc89a4e65609e842777d8c8864a7` | 6472 / `a7a940a12f4a77895661b9e11883495c7f1efc89a4e65609e842777d8c8864a7` | 6472 / `a7a940a12f4a77895661b9e11883495c7f1efc89a4e65609e842777d8c8864a7` | unchanged dependency |
| `schemas/t07-lambda-ssh-key-match.schema.json` | `/opt/giclab-project/schemas/t07-lambda-ssh-key-match.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3092 / `44a09e82b14bca6cf0609c2942402141b41850799123e0efd32156609dea6bac` | 3092 / `44a09e82b14bca6cf0609c2942402141b41850799123e0efd32156609dea6bac` | 3092 / `44a09e82b14bca6cf0609c2942402141b41850799123e0efd32156609dea6bac` | unchanged dependency |
| `schemas/t07-lambda-ssh-key-request-ledger.schema.json` | `/opt/giclab-project/schemas/t07-lambda-ssh-key-request-ledger.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 6066 / `4f2916e96a4453370f9621b7c78e4e53f7bb67a296e379bff4a79b5fe71d8557` | 6066 / `4f2916e96a4453370f9621b7c78e4e53f7bb67a296e379bff4a79b5fe71d8557` | 6066 / `4f2916e96a4453370f9621b7c78e4e53f7bb67a296e379bff4a79b5fe71d8557` | unchanged dependency |
| `schemas/t07-local-public-key-match.schema.json` | `/opt/giclab-project/schemas/t07-local-public-key-match.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3023 / `666ef981556b3f90759d45b7a48b6627951dd7f10518f9de748f4c1e5ac09925` | 3023 / `666ef981556b3f90759d45b7a48b6627951dd7f10518f9de748f4c1e5ac09925` | 3023 / `666ef981556b3f90759d45b7a48b6627951dd7f10518f9de748f4c1e5ac09925` | unchanged dependency |
| `schemas/t08-sira-smoke-adjudication.schema.json` | `/opt/giclab-project/schemas/t08-sira-smoke-adjudication.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 16942 / `6ca8d709fe59262bc19349d73bad819260569648e07cf71d617262432755013f` | 16942 / `6ca8d709fe59262bc19349d73bad819260569648e07cf71d617262432755013f` | 16942 / `6ca8d709fe59262bc19349d73bad819260569648e07cf71d617262432755013f` | unchanged dependency |
| `schemas/t08-sira-smoke-pair-diff.schema.json` | `/opt/giclab-project/schemas/t08-sira-smoke-pair-diff.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3496 / `0971a91698b66af51cf8c686f798d83144ce8c517000d528a6f764396766eeee` | 3496 / `0971a91698b66af51cf8c686f798d83144ce8c517000d528a6f764396766eeee` | 3496 / `0971a91698b66af51cf8c686f798d83144ce8c517000d528a6f764396766eeee` | unchanged dependency |
| `schemas/t09-active-version-lint-receipt.schema.json` | `/opt/giclab-project/schemas/t09-active-version-lint-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1578 / `cf907af3fe7d904e7665fbf00a587b61d96641071fc3a5f88c4e42a514b6633f` | 1578 / `cf907af3fe7d904e7665fbf00a587b61d96641071fc3a5f88c4e42a514b6633f` | 1578 / `cf907af3fe7d904e7665fbf00a587b61d96641071fc3a5f88c4e42a514b6633f` | unchanged dependency |
| `schemas/t09-agent-check-receipt.schema.json` | `/opt/giclab-project/schemas/t09-agent-check-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5396 / `6a6bd2aba66978ce5a78398d53759c10d685b68c556daf9fa99ddb339ba6b7f7` | 5396 / `6a6bd2aba66978ce5a78398d53759c10d685b68c556daf9fa99ddb339ba6b7f7` | 5396 / `6a6bd2aba66978ce5a78398d53759c10d685b68c556daf9fa99ddb339ba6b7f7` | unchanged dependency |
| `schemas/t09-anti-shadow-lint-receipt.schema.json` | `/opt/giclab-project/schemas/t09-anti-shadow-lint-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 8591 / `20df97d4fbf9c5443e2cf610012b6edbd3387b55732634a646296f35513f2f39` | 8591 / `20df97d4fbf9c5443e2cf610012b6edbd3387b55732634a646296f35513f2f39` | 8591 / `20df97d4fbf9c5443e2cf610012b6edbd3387b55732634a646296f35513f2f39` | unchanged dependency |
| `schemas/t09-category3-shadow-receipt.schema.json` | `/opt/giclab-project/schemas/t09-category3-shadow-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9173 / `7a74af233666fde629c52f73950dfcfb76dd7930c1e71cf94eaef6d28b9719c8` | 9173 / `7a74af233666fde629c52f73950dfcfb76dd7930c1e71cf94eaef6d28b9719c8` | 9173 / `7a74af233666fde629c52f73950dfcfb76dd7930c1e71cf94eaef6d28b9719c8` | unchanged dependency |
| `schemas/t09-cleanup-export-handoff.schema.json` | `/opt/giclab-project/schemas/t09-cleanup-export-handoff.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5738 / `fc5fd18d35239aabf1a02caa10c56ecce2a2ad073a94f0f0b282e77a75f801e9` | 5738 / `fc5fd18d35239aabf1a02caa10c56ecce2a2ad073a94f0f0b282e77a75f801e9` | 5738 / `fc5fd18d35239aabf1a02caa10c56ecce2a2ad073a94f0f0b282e77a75f801e9` | unchanged dependency |
| `schemas/t09-condition-duplex-frame.schema.json` | `/opt/giclab-project/schemas/t09-condition-duplex-frame.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2643 / `190757e75e09c50a8a7e82258880b3d2ba28deaf72c0b4f54dad39ae091492af` | 2643 / `190757e75e09c50a8a7e82258880b3d2ba28deaf72c0b4f54dad39ae091492af` | 2643 / `190757e75e09c50a8a7e82258880b3d2ba28deaf72c0b4f54dad39ae091492af` | unchanged dependency |
| `schemas/t09-condition-duplex-transcript.schema.json` | `/opt/giclab-project/schemas/t09-condition-duplex-transcript.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2574 / `7f2e5b3d5d6bc955132217948b99654d85c3588c032a57f2e877a60a2753d07c` | 2574 / `7f2e5b3d5d6bc955132217948b99654d85c3588c032a57f2e877a60a2753d07c` | 2574 / `7f2e5b3d5d6bc955132217948b99654d85c3588c032a57f2e877a60a2753d07c` | unchanged dependency |
| `schemas/t09-condition-host-terminal-receipt.schema.json` | `/opt/giclab-project/schemas/t09-condition-host-terminal-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2455 / `8dfc659a94f27c3906606d5e8e463e6a18bbbdeefa10b4d6a7ee8689542760e6` | 2455 / `8dfc659a94f27c3906606d5e8e463e6a18bbbdeefa10b4d6a7ee8689542760e6` | 2455 / `8dfc659a94f27c3906606d5e8e463e6a18bbbdeefa10b4d6a7ee8689542760e6` | unchanged dependency |
| `schemas/t09-condition-runtime-detachment.schema.json` | `/opt/giclab-project/schemas/t09-condition-runtime-detachment.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1189 / `d65e09cf916b568494da945088ff51440826702fea3036512f818357d7397a7d` | 1189 / `d65e09cf916b568494da945088ff51440826702fea3036512f818357d7397a7d` | 1189 / `d65e09cf916b568494da945088ff51440826702fea3036512f818357d7397a7d` | unchanged dependency |
| `schemas/t09-condition-session-terminal-receipt.schema.json` | `/opt/giclab-project/schemas/t09-condition-session-terminal-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2615 / `2804edf3875a257ada60eab5f00ac7fac1e80e9344d54867a7a51539ef181cf7` | 2615 / `2804edf3875a257ada60eab5f00ac7fac1e80e9344d54867a7a51539ef181cf7` | 2615 / `2804edf3875a257ada60eab5f00ac7fac1e80e9344d54867a7a51539ef181cf7` | unchanged dependency |
| `schemas/t09-control-composition-receipt.schema.json` | `/opt/giclab-project/schemas/t09-control-composition-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3051 / `a394ed475d2c319454821c46a4a75b5b33c6a9bbf1df32b2c14c49cb10bf0012` | 3051 / `a394ed475d2c319454821c46a4a75b5b33c6a9bbf1df32b2c14c49cb10bf0012` | 3051 / `a394ed475d2c319454821c46a4a75b5b33c6a9bbf1df32b2c14c49cb10bf0012` | unchanged dependency |
| `schemas/t09-control-plane-source-binding.schema.json` | `/opt/giclab-project/schemas/t09-control-plane-source-binding.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1609 / `f801d7587d38b7c7a7be94c061d52c6c489a450479ba8ade16dd8f4300fb1fae` | 1609 / `f801d7587d38b7c7a7be94c061d52c6c489a450479ba8ade16dd8f4300fb1fae` | 1609 / `f801d7587d38b7c7a7be94c061d52c6c489a450479ba8ade16dd8f4300fb1fae` | unchanged dependency |
| `schemas/t09-control-receipt-bindings.schema.json` | `/opt/giclab-project/schemas/t09-control-receipt-bindings.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 8485 / `bb69128e15cbdb377c3416f207d904380c1d80bbee53996a46b740fe5180a29d` | 8485 / `bb69128e15cbdb377c3416f207d904380c1d80bbee53996a46b740fe5180a29d` | 8485 / `bb69128e15cbdb377c3416f207d904380c1d80bbee53996a46b740fe5180a29d` | unchanged dependency |
| `schemas/t09-control-registry-receipt.schema.json` | `/opt/giclab-project/schemas/t09-control-registry-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1693 / `09811de1f906f4d7caae38104578750324f7d5a86d96cf6e9569dc7f53487a49` | 1693 / `09811de1f906f4d7caae38104578750324f7d5a86d96cf6e9569dc7f53487a49` | 1693 / `09811de1f906f4d7caae38104578750324f7d5a86d96cf6e9569dc7f53487a49` | unchanged dependency |
| `schemas/t09-control-target.schema.json` | `/opt/giclab-project/schemas/t09-control-target.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2100 / `0337c5fdc1d1c87b3700575dd1261fdb91c1d847ccd7f53f69a59e4333eb32b1` | 2100 / `0337c5fdc1d1c87b3700575dd1261fdb91c1d847ccd7f53f69a59e4333eb32b1` | 2100 / `0337c5fdc1d1c87b3700575dd1261fdb91c1d847ccd7f53f69a59e4333eb32b1` | unchanged dependency |
| `schemas/t09-early-cleanup-state.schema.json` | `/opt/giclab-project/schemas/t09-early-cleanup-state.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5162 / `1e041fe3197ed7c53f80e782c727f1dfb9e6d27ec9476543466711948b018edf` | 5162 / `1e041fe3197ed7c53f80e782c727f1dfb9e6d27ec9476543466711948b018edf` | 5255 / `c15beee060610fbc7d2ba1370598212678ec66268621badd909ce28e2f3cee0e` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `schemas/t09-effect-authorization-context.schema.json` | `/opt/giclab-project/schemas/t09-effect-authorization-context.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2989 / `6e0075353daf77a5a786a5203935f18f579a5850436ec75510df2756c16c1aef` | 2989 / `6e0075353daf77a5a786a5203935f18f579a5850436ec75510df2756c16c1aef` | 2989 / `6e0075353daf77a5a786a5203935f18f579a5850436ec75510df2756c16c1aef` | unchanged dependency |
| `schemas/t09-essential-failure-complete.schema.json` | `/opt/giclab-project/schemas/t09-essential-failure-complete.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1651 / `4b85240e1567b569dca70a4f95e70a76510ec89d4919f1d5972de2791feea5be` | 1651 / `4b85240e1567b569dca70a4f95e70a76510ec89d4919f1d5972de2791feea5be` | 1651 / `4b85240e1567b569dca70a4f95e70a76510ec89d4919f1d5972de2791feea5be` | unchanged dependency |
| `schemas/t09-essential-failure-export-acknowledgement.schema.json` | `/opt/giclab-project/schemas/t09-essential-failure-export-acknowledgement.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1614 / `a147416647bc5cb387aa1f4de53301f7e8079930eaf1ff6e44eea7c8db6e417a` | 1614 / `a147416647bc5cb387aa1f4de53301f7e8079930eaf1ff6e44eea7c8db6e417a` | 1614 / `a147416647bc5cb387aa1f4de53301f7e8079930eaf1ff6e44eea7c8db6e417a` | unchanged dependency |
| `schemas/t09-essential-failure-manifest.schema.json` | `/opt/giclab-project/schemas/t09-essential-failure-manifest.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2676 / `8eb960d4418bf0f42b40ef10c4ca7c1ab4e366c5ff61724eda690972679536b4` | 2676 / `8eb960d4418bf0f42b40ef10c4ca7c1ab4e366c5ff61724eda690972679536b4` | 2676 / `8eb960d4418bf0f42b40ef10c4ca7c1ab4e366c5ff61724eda690972679536b4` | unchanged dependency |
| `schemas/t09-full-dynamic-frozen-manifest.schema.json` | `/opt/giclab-project/schemas/t09-full-dynamic-frozen-manifest.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5591 / `ba9b7e39342c493b5a1aeb0a0ea3416f108147cc7a0e566d2bd85fa1c97e3472` | 5591 / `ba9b7e39342c493b5a1aeb0a0ea3416f108147cc7a0e566d2bd85fa1c97e3472` | 5591 / `ba9b7e39342c493b5a1aeb0a0ea3416f108147cc7a0e566d2bd85fa1c97e3472` | unchanged dependency |
| `schemas/t09-host-phase-receipt.schema.json` | `/opt/giclab-project/schemas/t09-host-phase-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2183 / `0da3cf2ce824e79eede3efcdd46052462c9db8daef7257665091285439b6b7e7` | 2183 / `0da3cf2ce824e79eede3efcdd46052462c9db8daef7257665091285439b6b7e7` | 2183 / `0da3cf2ce824e79eede3efcdd46052462c9db8daef7257665091285439b6b7e7` | unchanged dependency |
| `schemas/t09-host-phase-request.schema.json` | `/opt/giclab-project/schemas/t09-host-phase-request.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3525 / `ac9834094c451082f186d2c52d7e0503c75240cde0c823d1312402cd847fb2ce` | 3525 / `ac9834094c451082f186d2c52d7e0503c75240cde0c823d1312402cd847fb2ce` | 3626 / `d40ca9359c545480701083681478128dad0aee812e005860321b6cbb68326284` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `schemas/t09-incident-completeness-receipt.schema.json` | `/opt/giclab-project/schemas/t09-incident-completeness-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1920 / `2258f2467d48f517c76adb4f14be259fc807b5499e4ad88ecfeda9fcdfec9e8e` | 1920 / `2258f2467d48f517c76adb4f14be259fc807b5499e4ad88ecfeda9fcdfec9e8e` | 1920 / `2258f2467d48f517c76adb4f14be259fc807b5499e4ad88ecfeda9fcdfec9e8e` | unchanged dependency |
| `schemas/t09-live-effect-conformance-receipt.schema.json` | `/opt/giclab-project/schemas/t09-live-effect-conformance-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 29544 / `1df6ce62a816c08ac54d99493731c41c9ab11013994f8e2fc69c49f17ffc1ab5` | 29544 / `1df6ce62a816c08ac54d99493731c41c9ab11013994f8e2fc69c49f17ffc1ab5` | 29544 / `1df6ce62a816c08ac54d99493731c41c9ab11013994f8e2fc69c49f17ffc1ab5` | unchanged dependency |
| `schemas/t09-live-method-map.schema.json` | `/opt/giclab-project/schemas/t09-live-method-map.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2588 / `ade03d252e591e1e33bf22cb7c1bf5fbda487ee61d6bf98e4d5e5c6189d46050` | 2588 / `ade03d252e591e1e33bf22cb7c1bf5fbda487ee61d6bf98e4d5e5c6189d46050` | 2588 / `ade03d252e591e1e33bf22cb7c1bf5fbda487ee61d6bf98e4d5e5c6189d46050` | unchanged dependency |
| `schemas/t09-live-method-viability.schema.json` | `/opt/giclab-project/schemas/t09-live-method-viability.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3514 / `fd0a17d41ea40a81bec1aac8d04022cf68d138b1703913980ded7fd0851c4854` | 3514 / `fd0a17d41ea40a81bec1aac8d04022cf68d138b1703913980ded7fd0851c4854` | 3514 / `fd0a17d41ea40a81bec1aac8d04022cf68d138b1703913980ded7fd0851c4854` | unchanged dependency |
| `schemas/t09-model-metadata-receipt.schema.json` | `/opt/giclab-project/schemas/t09-model-metadata-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2649 / `8b61a8f7e572abfd5ed6347998c2829af0f114c6b7ca457e81e8691c5574a70a` | 2649 / `8b61a8f7e572abfd5ed6347998c2829af0f114c6b7ca457e81e8691c5574a70a` | 2649 / `8b61a8f7e572abfd5ed6347998c2829af0f114c6b7ca457e81e8691c5574a70a` | unchanged dependency |
| `schemas/t09-offline-refinalization-receipt.schema.json` | `/opt/giclab-project/schemas/t09-offline-refinalization-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9032 / `4965287881472b0605678223173e15ac870eebe894f95cae2609b390daf801e9` | 9032 / `4965287881472b0605678223173e15ac870eebe894f95cae2609b390daf801e9` | 9032 / `4965287881472b0605678223173e15ac870eebe894f95cae2609b390daf801e9` | unchanged dependency |
| `schemas/t09-private-condition-socket-binding.schema.json` | `/opt/giclab-project/schemas/t09-private-condition-socket-binding.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 1369 / `45bb526628a33c71cd32db3965242de6885550ff0b4e86df51af38e1be9aa85b` | 1369 / `45bb526628a33c71cd32db3965242de6885550ff0b4e86df51af38e1be9aa85b` | 1369 / `45bb526628a33c71cd32db3965242de6885550ff0b4e86df51af38e1be9aa85b` | unchanged dependency |
| `schemas/t09-remote-execution-bridge-conformance.schema.json` | `/opt/giclab-project/schemas/t09-remote-execution-bridge-conformance.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 8742 / `678fcd14160568f77d7e67570aed85ad78d589b0e02d41410f5af681be4db442` | 8742 / `678fcd14160568f77d7e67570aed85ad78d589b0e02d41410f5af681be4db442` | 8742 / `678fcd14160568f77d7e67570aed85ad78d589b0e02d41410f5af681be4db442` | unchanged dependency |
| `schemas/t09-sira-pilot-evidence.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-evidence.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 8579 / `e0a3d158a9ba27df01f302197511cc29d069e3d94b4d7a974593fe0aefa2b1db` | 8579 / `e0a3d158a9ba27df01f302197511cc29d069e3d94b4d7a974593fe0aefa2b1db` | 8579 / `e0a3d158a9ba27df01f302197511cc29d069e3d94b4d7a974593fe0aefa2b1db` | unchanged dependency |
| `schemas/t09-sira-pilot-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9230 / `55d5e4c80546f5af58ab707f847fc156cd9bd3da9ca76e6c7d5c19bcecf0a004` | 9230 / `55d5e4c80546f5af58ab707f847fc156cd9bd3da9ca76e6c7d5c19bcecf0a004` | 9230 / `55d5e4c80546f5af58ab707f847fc156cd9bd3da9ca76e6c7d5c19bcecf0a004` | unchanged dependency |
| `schemas/t09-sira-pilot-score.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-score.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 3779 / `1f2e85eba21b2bce7a56448e44682e6c00155744ab9a2fa3308dffe3442e7746` | 3779 / `1f2e85eba21b2bce7a56448e44682e6c00155744ab9a2fa3308dffe3442e7746` | 3779 / `1f2e85eba21b2bce7a56448e44682e6c00155744ab9a2fa3308dffe3442e7746` | unchanged dependency |
| `schemas/t09-sira-pilot-v10-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v10-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9298 / `19aa66563bac64d40233e8b4c70a7b94418d0402a11dff61993c2dd878ec448a` | 9298 / `19aa66563bac64d40233e8b4c70a7b94418d0402a11dff61993c2dd878ec448a` | 9298 / `19aa66563bac64d40233e8b4c70a7b94418d0402a11dff61993c2dd878ec448a` | unchanged dependency |
| `schemas/t09-sira-pilot-v11-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v11-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 9809 / `096e0a589a102b5cbf270eb3f8a14d9b9dd6cf7a48fb9397b1f126b1af8b6525` | 9809 / `096e0a589a102b5cbf270eb3f8a14d9b9dd6cf7a48fb9397b1f126b1af8b6525` | 9809 / `096e0a589a102b5cbf270eb3f8a14d9b9dd6cf7a48fb9397b1f126b1af8b6525` | unchanged dependency |
| `schemas/t09-sira-pilot-v12-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v12-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 11169 / `dbfe483f5238fa03b97e4e0f0d4846d4312f58ab46dbbea10017080604c6fbb1` | 11169 / `dbfe483f5238fa03b97e4e0f0d4846d4312f58ab46dbbea10017080604c6fbb1` | 11169 / `dbfe483f5238fa03b97e4e0f0d4846d4312f58ab46dbbea10017080604c6fbb1` | unchanged dependency |
| `schemas/t09-sira-pilot-v13-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v13-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 11169 / `65bd4fa0cf2ef72873adca85afa2c0b6c825b4503ea7fed34d713124d81e9db0` | 11169 / `65bd4fa0cf2ef72873adca85afa2c0b6c825b4503ea7fed34d713124d81e9db0` | 11169 / `65bd4fa0cf2ef72873adca85afa2c0b6c825b4503ea7fed34d713124d81e9db0` | unchanged dependency |
| `schemas/t09-sira-pilot-v14-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v14-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 11164 / `2a457caf35b81d3158dde5e16b4b3d2a68777e646dd61924bdc6de0aa4b0806b` | 11164 / `2a457caf35b81d3158dde5e16b4b3d2a68777e646dd61924bdc6de0aa4b0806b` | 11164 / `2a457caf35b81d3158dde5e16b4b3d2a68777e646dd61924bdc6de0aa4b0806b` | unchanged dependency |
| `schemas/t09-sira-pilot-v15-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v15-execution.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 12217 / `e2c3008a0bd29390d65ad9f238a84b0e042cc84db0c7a1b31fe81f456ae22304` | 12217 / `e2c3008a0bd29390d65ad9f238a84b0e042cc84db0c7a1b31fe81f456ae22304` | 12217 / `e2c3008a0bd29390d65ad9f238a84b0e042cc84db0c7a1b31fe81f456ae22304` | unchanged dependency |
| `schemas/t09-sira-pilot-v16-execution.schema.json` | `/opt/giclab-project/schemas/t09-sira-pilot-v16-execution.schema.json` | `historical-template` / historical-template | not an instrumentation pin | 12217 / `22ff91eb1de34edc890c81eeb242b40418acf0671bbfcfab36fefc43df138a3d` | 12217 / `22ff91eb1de34edc890c81eeb242b40418acf0671bbfcfab36fefc43df138a3d` | 12217 / `22ff91eb1de34edc890c81eeb242b40418acf0671bbfcfab36fefc43df138a3d` | unchanged dependency |
| `schemas/t09-v10-plan.schema.json` | `/opt/giclab-project/schemas/t09-v10-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 20979 / `7d0f2a6c9d0b5106f111c799aa29ef55012d12596f4819d27dbc9c57ced5285e` | 20979 / `7d0f2a6c9d0b5106f111c799aa29ef55012d12596f4819d27dbc9c57ced5285e` | 20979 / `7d0f2a6c9d0b5106f111c799aa29ef55012d12596f4819d27dbc9c57ced5285e` | unchanged dependency |
| `schemas/t09-v11-plan.schema.json` | `/opt/giclab-project/schemas/t09-v11-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 23345 / `3291af39c50ce4f186008adc56d79fc1715adc539a1faea92c2fb3bff4988a7f` | 23345 / `3291af39c50ce4f186008adc56d79fc1715adc539a1faea92c2fb3bff4988a7f` | 23345 / `3291af39c50ce4f186008adc56d79fc1715adc539a1faea92c2fb3bff4988a7f` | unchanged dependency |
| `schemas/t09-v12-plan.schema.json` | `/opt/giclab-project/schemas/t09-v12-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 27632 / `bf799255b12def214689f0a0ad7c18f7dda9bd0d19876c6414159c4bb3209908` | 27632 / `bf799255b12def214689f0a0ad7c18f7dda9bd0d19876c6414159c4bb3209908` | 27632 / `bf799255b12def214689f0a0ad7c18f7dda9bd0d19876c6414159c4bb3209908` | unchanged dependency |
| `schemas/t09-v13-model-metadata-receipt.schema.json` | `/opt/giclab-project/schemas/t09-v13-model-metadata-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2653 / `b30dae9e4d703e12bcbc7757a3afe266af6f911dfb0d6adbb8a7f28986e81cae` | 2653 / `b30dae9e4d703e12bcbc7757a3afe266af6f911dfb0d6adbb8a7f28986e81cae` | 2653 / `b30dae9e4d703e12bcbc7757a3afe266af6f911dfb0d6adbb8a7f28986e81cae` | unchanged dependency |
| `schemas/t09-v13-plan.schema.json` | `/opt/giclab-project/schemas/t09-v13-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 29512 / `7435fc2c126dcf1166f46a3b86218800765dcb9c590eb75bc8ad9e460e2073f3` | 29512 / `7435fc2c126dcf1166f46a3b86218800765dcb9c590eb75bc8ad9e460e2073f3` | 29512 / `7435fc2c126dcf1166f46a3b86218800765dcb9c590eb75bc8ad9e460e2073f3` | unchanged dependency |
| `schemas/t09-v14-model-metadata-receipt.schema.json` | `/opt/giclab-project/schemas/t09-v14-model-metadata-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2653 / `e01925b516d78774802149ddd887e4371d41eda00524f38d45737d4b256f941a` | 2653 / `e01925b516d78774802149ddd887e4371d41eda00524f38d45737d4b256f941a` | 2653 / `e01925b516d78774802149ddd887e4371d41eda00524f38d45737d4b256f941a` | unchanged dependency |
| `schemas/t09-v14-plan.schema.json` | `/opt/giclab-project/schemas/t09-v14-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 31604 / `6e9715b463a6b82fae1a0f05c1197498d3ff5628a26502d7827d5c63efefca30` | 31604 / `6e9715b463a6b82fae1a0f05c1197498d3ff5628a26502d7827d5c63efefca30` | 31604 / `6e9715b463a6b82fae1a0f05c1197498d3ff5628a26502d7827d5c63efefca30` | unchanged dependency |
| `schemas/t09-v15-model-metadata-receipt.schema.json` | `/opt/giclab-project/schemas/t09-v15-model-metadata-receipt.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 2653 / `46354e75701317392f7f4dd3696735ebc244431c26fea0a81197a11a67733b0b` | 2653 / `46354e75701317392f7f4dd3696735ebc244431c26fea0a81197a11a67733b0b` | 2653 / `46354e75701317392f7f4dd3696735ebc244431c26fea0a81197a11a67733b0b` | unchanged dependency |
| `schemas/t09-v15-plan.schema.json` | `/opt/giclab-project/schemas/t09-v15-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 33667 / `9b33079566253926432b4f8ee3830ff7bcd45114796637e74aa8b2ebd2f98ebd` | 33667 / `9b33079566253926432b4f8ee3830ff7bcd45114796637e74aa8b2ebd2f98ebd` | 33667 / `9b33079566253926432b4f8ee3830ff7bcd45114796637e74aa8b2ebd2f98ebd` | unchanged dependency |
| `schemas/t09-v16-model-metadata-receipt.schema.json` | `/opt/giclab-project/schemas/t09-v16-model-metadata-receipt.schema.json` | `historical-template` / historical-template | not an instrumentation pin | 2653 / `4e135f5059a9d446499cb3972ce474b7f2cc78fb8b91df451bbb045e295c0ea3` | 2653 / `4e135f5059a9d446499cb3972ce474b7f2cc78fb8b91df451bbb045e295c0ea3` | 2653 / `4e135f5059a9d446499cb3972ce474b7f2cc78fb8b91df451bbb045e295c0ea3` | unchanged dependency |
| `schemas/t09-v16-plan.schema.json` | `/opt/giclab-project/schemas/t09-v16-plan.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 41933 / `15381514c0ec7b51da55bf62d34fb23fde43866f018d2750cd952d63702a5d54` | 41933 / `15381514c0ec7b51da55bf62d34fb23fde43866f018d2750cd952d63702a5d54` | 41933 / `15381514c0ec7b51da55bf62d34fb23fde43866f018d2750cd952d63702a5d54` | unchanged dependency |
| `schemas/terminal-execution-control.schema.json` | `/opt/giclab-project/schemas/terminal-execution-control.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 5274 / `0b1ec3678678d72665fcb4414c113b8f0e93e88925f5354ca902fe152e13805d` | 5274 / `0b1ec3678678d72665fcb4414c113b8f0e93e88925f5354ca902fe152e13805d` | 5274 / `0b1ec3678678d72665fcb4414c113b8f0e93e88925f5354ca902fe152e13805d` | unchanged dependency |
| `schemas/transition.schema.json` | `/opt/giclab-project/schemas/transition.schema.json` | `retained-resource` / retained-resource | not an instrumentation pin | 4132 / `ea0af5472c5773a50a6f7719aa4992e84fef2939d9cf4dbb9be34aa0ea1b9ee6` | 4132 / `ea0af5472c5773a50a6f7719aa4992e84fef2939d9cf4dbb9be34aa0ea1b9ee6` | 4132 / `ea0af5472c5773a50a6f7719aa4992e84fef2939d9cf4dbb9be34aa0ea1b9ee6` | unchanged dependency |
| `src/giclab/__init__.py` | `/opt/giclab-project/src/giclab/__init__.py`<br>`/opt/giclab-src/giclab/__init__.py`<br>`/opt/giclab-accounting-src/giclab/__init__.py` | `giclab` / import-package | not an instrumentation pin | 66 / `1ba2dce15386a0abda4d8c35e38158220523ecdb3523638c9790be13dabeb872` | 66 / `1ba2dce15386a0abda4d8c35e38158220523ecdb3523638c9790be13dabeb872` | 66 / `1ba2dce15386a0abda4d8c35e38158220523ecdb3523638c9790be13dabeb872` | unchanged dependency |
| `src/giclab/ci_pytest_parity.py` | `/opt/giclab-project/src/giclab/ci_pytest_parity.py`<br>`/opt/giclab-src/giclab/ci_pytest_parity.py`<br>`/opt/giclab-accounting-src/giclab/ci_pytest_parity.py` | `giclab.ci_pytest_parity` / active-validation-input | not an instrumentation pin | 22068 / `157bef1af8f9b6bf029e539ff20963c08645f4a7f643afa9582efb0bfcfec506` | 22068 / `157bef1af8f9b6bf029e539ff20963c08645f4a7f643afa9582efb0bfcfec506` | 22068 / `157bef1af8f9b6bf029e539ff20963c08645f4a7f643afa9582efb0bfcfec506` | unchanged dependency |
| `src/giclab/control/__init__.py` | `/opt/giclab-project/src/giclab/control/__init__.py`<br>`/opt/giclab-src/giclab/control/__init__.py`<br>`/opt/giclab-accounting-src/giclab/control/__init__.py` | `giclab.control` / import-package | not an instrumentation pin | 192 / `b3250bf7d8c6e894cdb53903359885eeb25dd02e115a9064e614ba23a712f2b7` | 192 / `b3250bf7d8c6e894cdb53903359885eeb25dd02e115a9064e614ba23a712f2b7` | 192 / `b3250bf7d8c6e894cdb53903359885eeb25dd02e115a9064e614ba23a712f2b7` | unchanged dependency |
| `src/giclab/control/adapters.py` | `/opt/giclab-project/src/giclab/control/adapters.py`<br>`/opt/giclab-src/giclab/control/adapters.py`<br>`/opt/giclab-accounting-src/giclab/control/adapters.py` | `giclab.control.adapters` / import-dependency | not an instrumentation pin | 8578 / `f6124e51763c2440c312f9b570e40fa4d9ed28292e8a323ee5ea151477093f42` | 8578 / `f6124e51763c2440c312f9b570e40fa4d9ed28292e8a323ee5ea151477093f42` | 8578 / `f6124e51763c2440c312f9b570e40fa4d9ed28292e8a323ee5ea151477093f42` | unchanged dependency |
| `src/giclab/control/agent_check.py` | `/opt/giclab-project/src/giclab/control/agent_check.py`<br>`/opt/giclab-src/giclab/control/agent_check.py`<br>`/opt/giclab-accounting-src/giclab/control/agent_check.py` | `giclab.control.agent_check` / active-validation-input | not an instrumentation pin | 16564 / `76fd1e2f63bb2cd09e43cc2e1d67244f5b009ec8956857285575ce009db078d0` | 16564 / `76fd1e2f63bb2cd09e43cc2e1d67244f5b009ec8956857285575ce009db078d0` | 16564 / `76fd1e2f63bb2cd09e43cc2e1d67244f5b009ec8956857285575ce009db078d0` | unchanged dependency |
| `src/giclab/control/anti_shadow_lint.py` | `/opt/giclab-project/src/giclab/control/anti_shadow_lint.py`<br>`/opt/giclab-src/giclab/control/anti_shadow_lint.py`<br>`/opt/giclab-accounting-src/giclab/control/anti_shadow_lint.py` | `giclab.control.anti_shadow_lint` / import-dependency | not an instrumentation pin | 52412 / `d1004584cfae4d1f8685b73c39c9c1dcbe1f296591b8322c61b198c4c4d4fe2d` | 52412 / `d1004584cfae4d1f8685b73c39c9c1dcbe1f296591b8322c61b198c4c4d4fe2d` | 52412 / `d1004584cfae4d1f8685b73c39c9c1dcbe1f296591b8322c61b198c4c4d4fe2d` | unchanged dependency |
| `src/giclab/control/category3.py` | `/opt/giclab-project/src/giclab/control/category3.py`<br>`/opt/giclab-src/giclab/control/category3.py`<br>`/opt/giclab-accounting-src/giclab/control/category3.py` | `giclab.control.category3` / import-dependency | not an instrumentation pin | 44743 / `965d2f635e1c0dbde6d898d90d25fb8a857385f5d8e66c0bb78ec53510ce14a6` | 44743 / `965d2f635e1c0dbde6d898d90d25fb8a857385f5d8e66c0bb78ec53510ce14a6` | 45802 / `7d43e742bf1e46f3d6f49be7fc060dd70df7b271578969154c533f265a91d2f9` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/cli.py` | `/opt/giclab-project/src/giclab/control/cli.py`<br>`/opt/giclab-src/giclab/control/cli.py`<br>`/opt/giclab-accounting-src/giclab/control/cli.py` | `giclab.control.cli` / active-validation-input | not an instrumentation pin | 37214 / `9b0ee33ce90286f8d816e5325cd5cdf2c1d4213e4ffa98761d235ac3d18302ba` | 37214 / `9b0ee33ce90286f8d816e5325cd5cdf2c1d4213e4ffa98761d235ac3d18302ba` | 37214 / `9b0ee33ce90286f8d816e5325cd5cdf2c1d4213e4ffa98761d235ac3d18302ba` | unchanged dependency |
| `src/giclab/control/composition.py` | `/opt/giclab-project/src/giclab/control/composition.py`<br>`/opt/giclab-src/giclab/control/composition.py`<br>`/opt/giclab-accounting-src/giclab/control/composition.py` | `giclab.control.composition` / import-dependency | not an instrumentation pin | 14162 / `ea2f5ea3bae9a0a0dd241bc8a08255e84775c006f7d1bd3c59c733635726473d` | 14162 / `ea2f5ea3bae9a0a0dd241bc8a08255e84775c006f7d1bd3c59c733635726473d` | 14474 / `509a777b9652d087d7259fa634c9e1a0ed6713093e800f9a9c7426d04e06fee6` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/consumers.py` | `/opt/giclab-project/src/giclab/control/consumers.py`<br>`/opt/giclab-src/giclab/control/consumers.py`<br>`/opt/giclab-accounting-src/giclab/control/consumers.py` | `giclab.control.consumers` / import-dependency | not an instrumentation pin | 16974 / `a02492bd29148fd75ae30bc45459718534187efdab9023ed7b45003dc6fbf7e6` | 16974 / `a02492bd29148fd75ae30bc45459718534187efdab9023ed7b45003dc6fbf7e6` | 18047 / `4cf41b11e1b3aa2c437a804128decd6ed2badc4637ea708dccc3c9fdbeb6bb7d` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/contracts.py` | `/opt/giclab-project/src/giclab/control/contracts.py`<br>`/opt/giclab-src/giclab/control/contracts.py`<br>`/opt/giclab-accounting-src/giclab/control/contracts.py` | `giclab.control.contracts` / import-dependency | not an instrumentation pin | 2045 / `11091738583b1df60a4949e4aba206861549aed6412a503e0a747c5157fec7bf` | 2045 / `11091738583b1df60a4949e4aba206861549aed6412a503e0a747c5157fec7bf` | 2045 / `11091738583b1df60a4949e4aba206861549aed6412a503e0a747c5157fec7bf` | unchanged dependency |
| `src/giclab/control/effects.py` | `/opt/giclab-project/src/giclab/control/effects.py`<br>`/opt/giclab-src/giclab/control/effects.py`<br>`/opt/giclab-accounting-src/giclab/control/effects.py` | `giclab.control.effects` / import-dependency | not an instrumentation pin | 92297 / `1aec331d62cc02e13f9dded6dd87ad7bbeabeae4ba4f95379b81019d48588be7` | 92297 / `1aec331d62cc02e13f9dded6dd87ad7bbeabeae4ba4f95379b81019d48588be7` | 93448 / `650e7fd8488f87138432f421417f755fd947f559ad7e7e6eb9e3511cff59b05f` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/incidents.py` | `/opt/giclab-project/src/giclab/control/incidents.py`<br>`/opt/giclab-src/giclab/control/incidents.py`<br>`/opt/giclab-accounting-src/giclab/control/incidents.py` | `giclab.control.incidents` / import-dependency | not an instrumentation pin | 5845 / `7c95d15c1c0ea2b531940029b99980e845ac5bdcbebb8fcca2e7dd18c712a5d0` | 5845 / `7c95d15c1c0ea2b531940029b99980e845ac5bdcbebb8fcca2e7dd18c712a5d0` | 5845 / `7c95d15c1c0ea2b531940029b99980e845ac5bdcbebb8fcca2e7dd18c712a5d0` | unchanged dependency |
| `src/giclab/control/live_conformance.py` | `/opt/giclab-project/src/giclab/control/live_conformance.py`<br>`/opt/giclab-src/giclab/control/live_conformance.py`<br>`/opt/giclab-accounting-src/giclab/control/live_conformance.py` | `giclab.control.live_conformance` / active-validation-input | not an instrumentation pin | 67287 / `8c29753b24d2c0732aa07575c46db202a19f0fdaf6d0a85c98def4c9dd420c15` | 67287 / `8c29753b24d2c0732aa07575c46db202a19f0fdaf6d0a85c98def4c9dd420c15` | 67287 / `8c29753b24d2c0732aa07575c46db202a19f0fdaf6d0a85c98def4c9dd420c15` | unchanged dependency |
| `src/giclab/control/live_method_viability.py` | `/opt/giclab-project/src/giclab/control/live_method_viability.py`<br>`/opt/giclab-src/giclab/control/live_method_viability.py`<br>`/opt/giclab-accounting-src/giclab/control/live_method_viability.py` | `giclab.control.live_method_viability` / active-validation-input | not an instrumentation pin | 13209 / `c81decb3e1c2de723c872a0a346a3f2e802816f10f3e34c1f310ccdc76970056` | 13209 / `c81decb3e1c2de723c872a0a346a3f2e802816f10f3e34c1f310ccdc76970056` | 13209 / `c81decb3e1c2de723c872a0a346a3f2e802816f10f3e34c1f310ccdc76970056` | unchanged dependency |
| `src/giclab/control/production.py` | `/opt/giclab-project/src/giclab/control/production.py`<br>`/opt/giclab-src/giclab/control/production.py`<br>`/opt/giclab-accounting-src/giclab/control/production.py` | `giclab.control.production` / retained-entrypoint | not an instrumentation pin | 280246 / `09347a65ccbc1c3e0794fb8cb1109a03585892e31c09e48aa4418b568fd75e36` | 280246 / `09347a65ccbc1c3e0794fb8cb1109a03585892e31c09e48aa4418b568fd75e36` | 282517 / `1c9aab0c6653930699edae597033b0178aa7fc36cfd3dcacaac93295c8afd9b4` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/proofs.py` | `/opt/giclab-project/src/giclab/control/proofs.py`<br>`/opt/giclab-src/giclab/control/proofs.py`<br>`/opt/giclab-accounting-src/giclab/control/proofs.py` | `giclab.control.proofs` / import-dependency | not an instrumentation pin | 77725 / `5b1aba3cd3f5eea1c133b4670818edf75b477f7bd0eec52b57d7979429f92004` | 77725 / `5b1aba3cd3f5eea1c133b4670818edf75b477f7bd0eec52b57d7979429f92004` | 78194 / `93d66fea0cc3376fec401b6c2b2fa03e04ee9908c682b148650cb4b8084ec5e3` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/registry_validation.py` | `/opt/giclab-project/src/giclab/control/registry_validation.py`<br>`/opt/giclab-src/giclab/control/registry_validation.py`<br>`/opt/giclab-accounting-src/giclab/control/registry_validation.py` | `giclab.control.registry_validation` / import-dependency | not an instrumentation pin | 17629 / `4a455c4faf78996838e8e5081bb0872e6a10e2a8ad2bff5db0afac72317733a1` | 17629 / `4a455c4faf78996838e8e5081bb0872e6a10e2a8ad2bff5db0afac72317733a1` | 19119 / `f80ff0ee87a3794ab521743b583581c66c6e93c8b2ad565353e1092f677448b1` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/remote_bridge.py` | `/opt/giclab-project/src/giclab/control/remote_bridge.py`<br>`/opt/giclab-src/giclab/control/remote_bridge.py`<br>`/opt/giclab-accounting-src/giclab/control/remote_bridge.py` | `giclab.control.remote_bridge` / import-dependency | not an instrumentation pin | 102837 / `ca48a145927fc158476d76b9bf113c9550e1eba52ee6d56897fd6915bd1a0ee6` | 104098 / `708e24064767cd625deef8d5e9181430b0b85a1feefb9345bc20d277b3ca8381` | 104098 / `708e24064767cd625deef8d5e9181430b0b85a1feefb9345bc20d277b3ca8381` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/remote_execution_conformance.py` | `/opt/giclab-project/src/giclab/control/remote_execution_conformance.py`<br>`/opt/giclab-src/giclab/control/remote_execution_conformance.py`<br>`/opt/giclab-accounting-src/giclab/control/remote_execution_conformance.py` | `giclab.control.remote_execution_conformance` / active-validation-input | not an instrumentation pin | 61205 / `5cc82578156c2398e07d1b6e8d2589dfd851e67f4dd8f64624aa0cfa24f82bf6` | 61359 / `265da733dcb6d27c23b9e853de2c905ec33721d28d87e72cc1c3751995aac300` | 61359 / `265da733dcb6d27c23b9e853de2c905ec33721d28d87e72cc1c3751995aac300` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/scenarios.py` | `/opt/giclab-project/src/giclab/control/scenarios.py`<br>`/opt/giclab-src/giclab/control/scenarios.py`<br>`/opt/giclab-accounting-src/giclab/control/scenarios.py` | `giclab.control.scenarios` / import-dependency | not an instrumentation pin | 729 / `4cf66a4f0ec37bc8405777794af3d5dbbaf5feafbbb661d5d62c4aa5b1298a5c` | 729 / `4cf66a4f0ec37bc8405777794af3d5dbbaf5feafbbb661d5d62c4aa5b1298a5c` | 729 / `4cf66a4f0ec37bc8405777794af3d5dbbaf5feafbbb661d5d62c4aa5b1298a5c` | unchanged dependency |
| `src/giclab/control/shadow.py` | `/opt/giclab-project/src/giclab/control/shadow.py`<br>`/opt/giclab-src/giclab/control/shadow.py`<br>`/opt/giclab-accounting-src/giclab/control/shadow.py` | `giclab.control.shadow` / active-validation-input | not an instrumentation pin | 16351 / `5a91f31eda21ed6784a1a1aecc876b943e19d48ff47ae6e1e8990c62ef5e11f8` | 16351 / `5a91f31eda21ed6784a1a1aecc876b943e19d48ff47ae6e1e8990c62ef5e11f8` | 16351 / `5a91f31eda21ed6784a1a1aecc876b943e19d48ff47ae6e1e8990c62ef5e11f8` | unchanged dependency |
| `src/giclab/control/shadow_effects.py` | `/opt/giclab-project/src/giclab/control/shadow_effects.py`<br>`/opt/giclab-src/giclab/control/shadow_effects.py`<br>`/opt/giclab-accounting-src/giclab/control/shadow_effects.py` | `giclab.control.shadow_effects` / import-dependency | not an instrumentation pin | 109038 / `a9f5d0c42871871907fc6620e11309c423af8050556d1b8b5384c94a57df4921` | 109038 / `a9f5d0c42871871907fc6620e11309c423af8050556d1b8b5384c94a57df4921` | 109956 / `2f70983847e53e73b8b8124526dd65a8c973fa57f9a7044b904202f317e51984` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/state_capsule.py` | `/opt/giclab-project/src/giclab/control/state_capsule.py`<br>`/opt/giclab-src/giclab/control/state_capsule.py`<br>`/opt/giclab-accounting-src/giclab/control/state_capsule.py` | `giclab.control.state_capsule` / import-dependency | not an instrumentation pin | 8229 / `8898862f080a574e93c13d4a9ded6a1cd6a2d6c77a866e0447fbfece9a6d6870` | 8229 / `8898862f080a574e93c13d4a9ded6a1cd6a2d6c77a866e0447fbfece9a6d6870` | 8554 / `7624265f65699db68a5cde83d645be3bbe8438b0cf02f2a8aacbbd7d8b7e6f4b` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/control/target.py` | `/opt/giclab-project/src/giclab/control/target.py`<br>`/opt/giclab-src/giclab/control/target.py`<br>`/opt/giclab-accounting-src/giclab/control/target.py` | `giclab.control.target` / import-dependency | not an instrumentation pin | 23710 / `e354aa938c3f37ac56c6cd45ca672c497014ac3c09200771c23431b057e70ca7` | 23710 / `e354aa938c3f37ac56c6cd45ca672c497014ac3c09200771c23431b057e70ca7` | 23710 / `e354aa938c3f37ac56c6cd45ca672c497014ac3c09200771c23431b057e70ca7` | unchanged dependency |
| `src/giclab/control/version_lint.py` | `/opt/giclab-project/src/giclab/control/version_lint.py`<br>`/opt/giclab-src/giclab/control/version_lint.py`<br>`/opt/giclab-accounting-src/giclab/control/version_lint.py` | `giclab.control.version_lint` / import-dependency | not an instrumentation pin | 13530 / `e148b51125d085e7c2f0f6b558d24b34af07eddfb4f6c866341c2ea54fe37b49` | 13530 / `e148b51125d085e7c2f0f6b558d24b34af07eddfb4f6c866341c2ea54fe37b49` | 13749 / `811dd05fbd49c7b63977d22de4bc6f5c3332a28bfb44fe45bc4b94e8eeb2b920` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/harness/__init__.py` | `/opt/giclab-project/src/giclab/harness/__init__.py`<br>`/opt/giclab-src/giclab/harness/__init__.py`<br>`/opt/giclab-accounting-src/giclab/harness/__init__.py` | `giclab.harness` / import-package | not an instrumentation pin | 3669 / `9cb096df25019fbb4e6c61a55b46cf4bb38ebe6b650248f1f0623347cf568c97` | 3669 / `9cb096df25019fbb4e6c61a55b46cf4bb38ebe6b650248f1f0623347cf568c97` | 3669 / `9cb096df25019fbb4e6c61a55b46cf4bb38ebe6b650248f1f0623347cf568c97` | unchanged dependency |
| `src/giclab/harness/adapters/__init__.py` | `/opt/giclab-project/src/giclab/harness/adapters/__init__.py`<br>`/opt/giclab-src/giclab/harness/adapters/__init__.py`<br>`/opt/giclab-accounting-src/giclab/harness/adapters/__init__.py` | `giclab.harness.adapters` / import-package | not an instrumentation pin | 1749 / `f241a205c6c4a616418b5ac6cd8fb25b6c3a135decb0e35dacb9954e540095af` | 1749 / `f241a205c6c4a616418b5ac6cd8fb25b6c3a135decb0e35dacb9954e540095af` | 1749 / `f241a205c6c4a616418b5ac6cd8fb25b6c3a135decb0e35dacb9954e540095af` | unchanged dependency |
| `src/giclab/harness/adapters/base.py` | `/opt/giclab-project/src/giclab/harness/adapters/base.py`<br>`/opt/giclab-src/giclab/harness/adapters/base.py`<br>`/opt/giclab-accounting-src/giclab/harness/adapters/base.py` | `giclab.harness.adapters.base` / import-dependency | not an instrumentation pin | 2430 / `22e6a4c84b0d8b583bd3055d115a4a2e61a9555e466f076d79a91520aa3b985e` | 2430 / `22e6a4c84b0d8b583bd3055d115a4a2e61a9555e466f076d79a91520aa3b985e` | 2430 / `22e6a4c84b0d8b583bd3055d115a4a2e61a9555e466f076d79a91520aa3b985e` | unchanged dependency |
| `src/giclab/harness/adapters/sira.py` | `/opt/giclab-project/src/giclab/harness/adapters/sira.py`<br>`/opt/giclab-src/giclab/harness/adapters/sira.py`<br>`/opt/giclab-accounting-src/giclab/harness/adapters/sira.py` | `giclab.harness.adapters.sira` / import-dependency | not an instrumentation pin | 78882 / `5da13853584caa1f680536f719a873b860031c2648a88f9812d67163ba7be5bc` | 78882 / `5da13853584caa1f680536f719a873b860031c2648a88f9812d67163ba7be5bc` | 78882 / `5da13853584caa1f680536f719a873b860031c2648a88f9812d67163ba7be5bc` | unchanged dependency |
| `src/giclab/harness/artifacts.py` | `/opt/giclab-project/src/giclab/harness/artifacts.py`<br>`/opt/giclab-src/giclab/harness/artifacts.py`<br>`/opt/giclab-accounting-src/giclab/harness/artifacts.py` | `giclab.harness.artifacts` / import-dependency | not an instrumentation pin | 20779 / `643f02b893694c947d7cd4c29f374a158caf54b167f3d8d192b36e1a6eae2c3d` | 20779 / `643f02b893694c947d7cd4c29f374a158caf54b167f3d8d192b36e1a6eae2c3d` | 20779 / `643f02b893694c947d7cd4c29f374a158caf54b167f3d8d192b36e1a6eae2c3d` | unchanged dependency |
| `src/giclab/harness/budget.py` | `/opt/giclab-project/src/giclab/harness/budget.py`<br>`/opt/giclab-src/giclab/harness/budget.py`<br>`/opt/giclab-accounting-src/giclab/harness/budget.py` | `giclab.harness.budget` / import-dependency | not an instrumentation pin | 5400 / `376ad8f491940a0758b49d6bc597e182a69af0459ace9d06c7e652d76ad9bc2a` | 5400 / `376ad8f491940a0758b49d6bc597e182a69af0459ace9d06c7e652d76ad9bc2a` | 5400 / `376ad8f491940a0758b49d6bc597e182a69af0459ace9d06c7e652d76ad9bc2a` | unchanged dependency |
| `src/giclab/harness/cli.py` | `/opt/giclab-project/src/giclab/harness/cli.py`<br>`/opt/giclab-src/giclab/harness/cli.py`<br>`/opt/giclab-accounting-src/giclab/harness/cli.py` | `giclab.harness.cli` / active-validation-input | not an instrumentation pin | 9640 / `d3439dd53336a2e74776453c5b7fcb5fe686cba6d71c1657c7925115d6413646` | 9640 / `d3439dd53336a2e74776453c5b7fcb5fe686cba6d71c1657c7925115d6413646` | 9640 / `d3439dd53336a2e74776453c5b7fcb5fe686cba6d71c1657c7925115d6413646` | unchanged dependency |
| `src/giclab/harness/events.py` | `/opt/giclab-project/src/giclab/harness/events.py`<br>`/opt/giclab-src/giclab/harness/events.py`<br>`/opt/giclab-accounting-src/giclab/harness/events.py` | `giclab.harness.events` / import-dependency | not an instrumentation pin | 12542 / `b6a4c529d9bc3939c552891e75083bd0d7420744b5948a4739165c861992a29d` | 12542 / `b6a4c529d9bc3939c552891e75083bd0d7420744b5948a4739165c861992a29d` | 12542 / `b6a4c529d9bc3939c552891e75083bd0d7420744b5948a4739165c861992a29d` | unchanged dependency |
| `src/giclab/harness/executor.py` | `/opt/giclab-project/src/giclab/harness/executor.py`<br>`/opt/giclab-src/giclab/harness/executor.py`<br>`/opt/giclab-accounting-src/giclab/harness/executor.py` | `giclab.harness.executor` / import-dependency | not an instrumentation pin | 70144 / `007c627e42ba53db0009f31ec2594ede8f40bfc690f027109068fd5f37189a70` | 70144 / `007c627e42ba53db0009f31ec2594ede8f40bfc690f027109068fd5f37189a70` | 70144 / `007c627e42ba53db0009f31ec2594ede8f40bfc690f027109068fd5f37189a70` | unchanged dependency |
| `src/giclab/harness/lambda_archive.py` | `/opt/giclab-project/src/giclab/harness/lambda_archive.py`<br>`/opt/giclab-src/giclab/harness/lambda_archive.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_archive.py` | `giclab.harness.lambda_archive` / import-dependency | not an instrumentation pin | 27340 / `2004f5c9b23a41a040baad766516e0f2d62e6edf440a4571b484ee061b2d1c4c` | 27340 / `2004f5c9b23a41a040baad766516e0f2d62e6edf440a4571b484ee061b2d1c4c` | 27340 / `2004f5c9b23a41a040baad766516e0f2d62e6edf440a4571b484ee061b2d1c4c` | unchanged dependency |
| `src/giclab/harness/lambda_archive_v2.py` | `/opt/giclab-project/src/giclab/harness/lambda_archive_v2.py`<br>`/opt/giclab-src/giclab/harness/lambda_archive_v2.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_archive_v2.py` | `giclab.harness.lambda_archive_v2` / active-validation-input | not an instrumentation pin | 38311 / `5ef7ab402784dc915461fa05af41c73977936b2f53daabfbfe14e1e442d93945` | 38311 / `5ef7ab402784dc915461fa05af41c73977936b2f53daabfbfe14e1e442d93945` | 38311 / `5ef7ab402784dc915461fa05af41c73977936b2f53daabfbfe14e1e442d93945` | unchanged dependency |
| `src/giclab/harness/lambda_archive_v3.py` | `/opt/giclab-project/src/giclab/harness/lambda_archive_v3.py`<br>`/opt/giclab-src/giclab/harness/lambda_archive_v3.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_archive_v3.py` | `giclab.harness.lambda_archive_v3` / import-dependency | not an instrumentation pin | 43290 / `29e59e6c9e71c45211322b10c365d6044445658d7e3b317f4d0017b17d6b0f50` | 43290 / `29e59e6c9e71c45211322b10c365d6044445658d7e3b317f4d0017b17d6b0f50` | 43290 / `29e59e6c9e71c45211322b10c365d6044445658d7e3b317f4d0017b17d6b0f50` | unchanged dependency |
| `src/giclab/harness/lambda_campaign_lifecycle.py` | `/opt/giclab-project/src/giclab/harness/lambda_campaign_lifecycle.py`<br>`/opt/giclab-src/giclab/harness/lambda_campaign_lifecycle.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_campaign_lifecycle.py` | `giclab.harness.lambda_campaign_lifecycle` / import-dependency | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` | 13269 / `6f0f74354f15766466480c498b4ab5af6887e337c5197416bb9dedf3ff78200b` | unchanged dependency |
| `src/giclab/harness/lambda_cloud.py` | `/opt/giclab-project/src/giclab/harness/lambda_cloud.py`<br>`/opt/giclab-src/giclab/harness/lambda_cloud.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_cloud.py` | `giclab.harness.lambda_cloud` / import-dependency | not an instrumentation pin | 103598 / `69aa0c54e48f9f49f9dd7d297af12e41468ed6d0c7b9a36e89ba10d3d668c51c` | 103598 / `69aa0c54e48f9f49f9dd7d297af12e41468ed6d0c7b9a36e89ba10d3d668c51c` | 103598 / `69aa0c54e48f9f49f9dd7d297af12e41468ed6d0c7b9a36e89ba10d3d668c51c` | unchanged dependency |
| `src/giclab/harness/lambda_cloud_v3.py` | `/opt/giclab-project/src/giclab/harness/lambda_cloud_v3.py`<br>`/opt/giclab-src/giclab/harness/lambda_cloud_v3.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_cloud_v3.py` | `giclab.harness.lambda_cloud_v3` / import-dependency | not an instrumentation pin | 56507 / `4ffb4f649e6fdd3e3e2d058f7b009aa9f64d5c9e4d32874ff0e24754ec3dfae6` | 56507 / `4ffb4f649e6fdd3e3e2d058f7b009aa9f64d5c9e4d32874ff0e24754ec3dfae6` | 56507 / `4ffb4f649e6fdd3e3e2d058f7b009aa9f64d5c9e4d32874ff0e24754ec3dfae6` | unchanged dependency |
| `src/giclab/harness/lambda_firewall_baseline.py` | `/opt/giclab-project/src/giclab/harness/lambda_firewall_baseline.py`<br>`/opt/giclab-src/giclab/harness/lambda_firewall_baseline.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_firewall_baseline.py` | `giclab.harness.lambda_firewall_baseline` / import-dependency | not an instrumentation pin | 108400 / `fe736fb42136ce56ab1a81dc5a2face6e3c5be8855bba496878fe5ac2bd579e3` | 108400 / `fe736fb42136ce56ab1a81dc5a2face6e3c5be8855bba496878fe5ac2bd579e3` | 108400 / `fe736fb42136ce56ab1a81dc5a2face6e3c5be8855bba496878fe5ac2bd579e3` | unchanged dependency |
| `src/giclab/harness/lambda_inventory.py` | `/opt/giclab-project/src/giclab/harness/lambda_inventory.py`<br>`/opt/giclab-src/giclab/harness/lambda_inventory.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_inventory.py` | `giclab.harness.lambda_inventory` / active-validation-input | not an instrumentation pin | 31648 / `cc4da6a4c346c07a7a9e809dcaf214e83b9fdaee269068ca2f7701f2606f6f42` | 31648 / `cc4da6a4c346c07a7a9e809dcaf214e83b9fdaee269068ca2f7701f2606f6f42` | 31648 / `cc4da6a4c346c07a7a9e809dcaf214e83b9fdaee269068ca2f7701f2606f6f42` | unchanged dependency |
| `src/giclab/harness/lambda_inventory_plan.py` | `/opt/giclab-project/src/giclab/harness/lambda_inventory_plan.py`<br>`/opt/giclab-src/giclab/harness/lambda_inventory_plan.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_inventory_plan.py` | `giclab.harness.lambda_inventory_plan` / active-validation-input | not an instrumentation pin | 32770 / `c0f8d96433106162ecb90b6fc3e53f596f9f2db55e5b325794a5193e4a663083` | 32770 / `c0f8d96433106162ecb90b6fc3e53f596f9f2db55e5b325794a5193e4a663083` | 32770 / `c0f8d96433106162ecb90b6fc3e53f596f9f2db55e5b325794a5193e4a663083` | unchanged dependency |
| `src/giclab/harness/lambda_inventory_plan_v3.py` | `/opt/giclab-project/src/giclab/harness/lambda_inventory_plan_v3.py`<br>`/opt/giclab-src/giclab/harness/lambda_inventory_plan_v3.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_inventory_plan_v3.py` | `giclab.harness.lambda_inventory_plan_v3` / import-dependency | not an instrumentation pin | 37867 / `80c3b39ec904b3a5cfb03118a1173b67b22ce0d7e4fb325fdc4195a308c57d1b` | 37867 / `80c3b39ec904b3a5cfb03118a1173b67b22ce0d7e4fb325fdc4195a308c57d1b` | 37867 / `80c3b39ec904b3a5cfb03118a1173b67b22ce0d7e4fb325fdc4195a308c57d1b` | unchanged dependency |
| `src/giclab/harness/lambda_inventory_v2.py` | `/opt/giclab-project/src/giclab/harness/lambda_inventory_v2.py`<br>`/opt/giclab-src/giclab/harness/lambda_inventory_v2.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_inventory_v2.py` | `giclab.harness.lambda_inventory_v2` / active-validation-input | not an instrumentation pin | 48919 / `14b0288f4a6e215077d40f6bb7053dac5f9d6ad87ed07d97383e4cd5a5abef90` | 48919 / `14b0288f4a6e215077d40f6bb7053dac5f9d6ad87ed07d97383e4cd5a5abef90` | 48919 / `14b0288f4a6e215077d40f6bb7053dac5f9d6ad87ed07d97383e4cd5a5abef90` | unchanged dependency |
| `src/giclab/harness/lambda_inventory_v3.py` | `/opt/giclab-project/src/giclab/harness/lambda_inventory_v3.py`<br>`/opt/giclab-src/giclab/harness/lambda_inventory_v3.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_inventory_v3.py` | `giclab.harness.lambda_inventory_v3` / active-validation-input | not an instrumentation pin | 50720 / `f88f719c483863e2147e3dbe1055b6291e2963687e98e67382683247e2180253` | 50720 / `f88f719c483863e2147e3dbe1055b6291e2963687e98e67382683247e2180253` | 50720 / `f88f719c483863e2147e3dbe1055b6291e2963687e98e67382683247e2180253` | unchanged dependency |
| `src/giclab/harness/lambda_l13_security.py` | `/opt/giclab-project/src/giclab/harness/lambda_l13_security.py`<br>`/opt/giclab-src/giclab/harness/lambda_l13_security.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l13_security.py` | `giclab.harness.lambda_l13_security` / import-dependency | not an instrumentation pin | 93281 / `1f2736ae223649f86bb18621b008f06bf9fd0d82af6d28ed904f53e8b0111fd0` | 93281 / `1f2736ae223649f86bb18621b008f06bf9fd0d82af6d28ed904f53e8b0111fd0` | 93281 / `1f2736ae223649f86bb18621b008f06bf9fd0d82af6d28ed904f53e8b0111fd0` | unchanged dependency |
| `src/giclab/harness/lambda_l20_plan.py` | `/opt/giclab-project/src/giclab/harness/lambda_l20_plan.py`<br>`/opt/giclab-src/giclab/harness/lambda_l20_plan.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l20_plan.py` | `giclab.harness.lambda_l20_plan` / import-dependency | not an instrumentation pin | 128149 / `e4c7ad2aa7c41520a47bd41c3faaaf204fc2e0a5ce6dc1299e688f1f8e98cc7c` | 128149 / `e4c7ad2aa7c41520a47bd41c3faaaf204fc2e0a5ce6dc1299e688f1f8e98cc7c` | 128149 / `e4c7ad2aa7c41520a47bd41c3faaaf204fc2e0a5ce6dc1299e688f1f8e98cc7c` | unchanged dependency |
| `src/giclab/harness/lambda_l23_manual_plan.py` | `/opt/giclab-project/src/giclab/harness/lambda_l23_manual_plan.py`<br>`/opt/giclab-src/giclab/harness/lambda_l23_manual_plan.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l23_manual_plan.py` | `giclab.harness.lambda_l23_manual_plan` / active-validation-input | not an instrumentation pin | 91667 / `bf82ce5b0e938f55d2923945fefefc3917bcb5acf24646d9596f912075a911d8` | 91667 / `bf82ce5b0e938f55d2923945fefefc3917bcb5acf24646d9596f912075a911d8` | 91667 / `bf82ce5b0e938f55d2923945fefefc3917bcb5acf24646d9596f912075a911d8` | unchanged dependency |
| `src/giclab/harness/lambda_l23_manual_supervisor.py` | `/opt/giclab-project/src/giclab/harness/lambda_l23_manual_supervisor.py`<br>`/opt/giclab-src/giclab/harness/lambda_l23_manual_supervisor.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l23_manual_supervisor.py` | `giclab.harness.lambda_l23_manual_supervisor` / active-validation-input | not an instrumentation pin | 64296 / `6f67f81a79343dc977f5464cc415914bcc6a11d0f53028f25add6db7783b40cb` | 64296 / `6f67f81a79343dc977f5464cc415914bcc6a11d0f53028f25add6db7783b40cb` | 64296 / `6f67f81a79343dc977f5464cc415914bcc6a11d0f53028f25add6db7783b40cb` | unchanged dependency |
| `src/giclab/harness/lambda_l2_evidence.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2_evidence.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2_evidence.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2_evidence.py` | `giclab.harness.lambda_l2_evidence` / active-validation-input | not an instrumentation pin | 16390 / `1e84e086659a19d29de119f7de613ab3ebb1c447c934a836d6357809044a62e0` | 16390 / `1e84e086659a19d29de119f7de613ab3ebb1c447c934a836d6357809044a62e0` | 16390 / `1e84e086659a19d29de119f7de613ab3ebb1c447c934a836d6357809044a62e0` | unchanged dependency |
| `src/giclab/harness/lambda_l2_execution.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2_execution.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2_execution.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2_execution.py` | `giclab.harness.lambda_l2_execution` / active-validation-input | not an instrumentation pin | 20866 / `c862397207e6afc9373bee8b061f098e9e5d525eeda0a3d9c5ff12569be22397` | 20866 / `c862397207e6afc9373bee8b061f098e9e5d525eeda0a3d9c5ff12569be22397` | 20866 / `c862397207e6afc9373bee8b061f098e9e5d525eeda0a3d9c5ff12569be22397` | unchanged dependency |
| `src/giclab/harness/lambda_l2_ownership.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2_ownership.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2_ownership.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2_ownership.py` | `giclab.harness.lambda_l2_ownership` / active-validation-input | not an instrumentation pin | 18040 / `bca8449939fa360a68532abd5035667235dd40baae190d3c7dd7401bc23d4065` | 18040 / `bca8449939fa360a68532abd5035667235dd40baae190d3c7dd7401bc23d4065` | 18040 / `bca8449939fa360a68532abd5035667235dd40baae190d3c7dd7401bc23d4065` | unchanged dependency |
| `src/giclab/harness/lambda_l2_supervisor.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2_supervisor.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2_supervisor.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2_supervisor.py` | `giclab.harness.lambda_l2_supervisor` / active-validation-input | not an instrumentation pin | 78277 / `c1c974dffc9a8c0d2b3dde52cf0f2437a5451479481166910dcc1dfe945b23e4` | 78277 / `c1c974dffc9a8c0d2b3dde52cf0f2437a5451479481166910dcc1dfe945b23e4` | 78277 / `c1c974dffc9a8c0d2b3dde52cf0f2437a5451479481166910dcc1dfe945b23e4` | unchanged dependency |
| `src/giclab/harness/lambda_l2_watchdog.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2_watchdog.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2_watchdog.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2_watchdog.py` | `giclab.harness.lambda_l2_watchdog` / active-validation-input | not an instrumentation pin | 31816 / `ca28fd860267f5fdf4ae61ebdd324acc09e3f04c6ea373c70ab8756acd12e473` | 31816 / `ca28fd860267f5fdf4ae61ebdd324acc09e3f04c6ea373c70ab8756acd12e473` | 31816 / `ca28fd860267f5fdf4ae61ebdd324acc09e3f04c6ea373c70ab8756acd12e473` | unchanged dependency |
| `src/giclab/harness/lambda_l2m_checkpoints.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2m_checkpoints.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2m_checkpoints.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2m_checkpoints.py` | `giclab.harness.lambda_l2m_checkpoints` / import-dependency | not an instrumentation pin | 33515 / `3c8ae545c4d39b633bdd9e02ae3d79a704d0eda5f0a70b0378dd3d32e6afe0f0` | 33515 / `3c8ae545c4d39b633bdd9e02ae3d79a704d0eda5f0a70b0378dd3d32e6afe0f0` | 33515 / `3c8ae545c4d39b633bdd9e02ae3d79a704d0eda5f0a70b0378dd3d32e6afe0f0` | unchanged dependency |
| `src/giclab/harness/lambda_l2m_observer.py` | `/opt/giclab-project/src/giclab/harness/lambda_l2m_observer.py`<br>`/opt/giclab-src/giclab/harness/lambda_l2m_observer.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_l2m_observer.py` | `giclab.harness.lambda_l2m_observer` / import-dependency | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` | 320452 / `3ad5d56abd2b4d115b479c9cf7f0f5202e715d07c1b4842c82dc894fbe8bf6c9` | unchanged dependency |
| `src/giclab/harness/lambda_request_ledger.py` | `/opt/giclab-project/src/giclab/harness/lambda_request_ledger.py`<br>`/opt/giclab-src/giclab/harness/lambda_request_ledger.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_request_ledger.py` | `giclab.harness.lambda_request_ledger` / active-validation-input | not an instrumentation pin | 52154 / `fc16790b01a291f5412b9dff31f56110793fd0e8593dfac808386975b51a0a64` | 52154 / `fc16790b01a291f5412b9dff31f56110793fd0e8593dfac808386975b51a0a64` | 52154 / `fc16790b01a291f5412b9dff31f56110793fd0e8593dfac808386975b51a0a64` | unchanged dependency |
| `src/giclab/harness/lambda_request_ledger_v3.py` | `/opt/giclab-project/src/giclab/harness/lambda_request_ledger_v3.py`<br>`/opt/giclab-src/giclab/harness/lambda_request_ledger_v3.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_request_ledger_v3.py` | `giclab.harness.lambda_request_ledger_v3` / import-dependency | not an instrumentation pin | 52146 / `4e3f15c8d1651f18cc64d7c9dd47bc15d655bac5b3a348d74b364c12687dfd4c` | 52146 / `4e3f15c8d1651f18cc64d7c9dd47bc15d655bac5b3a348d74b364c12687dfd4c` | 52146 / `4e3f15c8d1651f18cc64d7c9dd47bc15d655bac5b3a348d74b364c12687dfd4c` | unchanged dependency |
| `src/giclab/harness/lambda_ssh_key_archive.py` | `/opt/giclab-project/src/giclab/harness/lambda_ssh_key_archive.py`<br>`/opt/giclab-src/giclab/harness/lambda_ssh_key_archive.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_ssh_key_archive.py` | `giclab.harness.lambda_ssh_key_archive` / active-validation-input | not an instrumentation pin | 42077 / `568a191f1745d8861a1a8847e8bf9e7da81b4b1a36c7fb5de8f173364644ab90` | 42077 / `568a191f1745d8861a1a8847e8bf9e7da81b4b1a36c7fb5de8f173364644ab90` | 42077 / `568a191f1745d8861a1a8847e8bf9e7da81b4b1a36c7fb5de8f173364644ab90` | unchanged dependency |
| `src/giclab/harness/lambda_ssh_key_executor.py` | `/opt/giclab-project/src/giclab/harness/lambda_ssh_key_executor.py`<br>`/opt/giclab-src/giclab/harness/lambda_ssh_key_executor.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_ssh_key_executor.py` | `giclab.harness.lambda_ssh_key_executor` / active-validation-input | not an instrumentation pin | 32360 / `7360939c1ee7cf7875d0425ff51c1354c3b5799463c1d76f95ad2eec5e73ecfd` | 32360 / `7360939c1ee7cf7875d0425ff51c1354c3b5799463c1d76f95ad2eec5e73ecfd` | 32360 / `7360939c1ee7cf7875d0425ff51c1354c3b5799463c1d76f95ad2eec5e73ecfd` | unchanged dependency |
| `src/giclab/harness/lambda_ssh_key_fingerprint.py` | `/opt/giclab-project/src/giclab/harness/lambda_ssh_key_fingerprint.py`<br>`/opt/giclab-src/giclab/harness/lambda_ssh_key_fingerprint.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_ssh_key_fingerprint.py` | `giclab.harness.lambda_ssh_key_fingerprint` / import-dependency | not an instrumentation pin | 42587 / `89570f118d9bd860b1b251fdaa9b3b28e80e5a4476ccffe6607763643967320a` | 42587 / `89570f118d9bd860b1b251fdaa9b3b28e80e5a4476ccffe6607763643967320a` | 42587 / `89570f118d9bd860b1b251fdaa9b3b28e80e5a4476ccffe6607763643967320a` | unchanged dependency |
| `src/giclab/harness/lambda_ssh_key_match.py` | `/opt/giclab-project/src/giclab/harness/lambda_ssh_key_match.py`<br>`/opt/giclab-src/giclab/harness/lambda_ssh_key_match.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_ssh_key_match.py` | `giclab.harness.lambda_ssh_key_match` / active-validation-input | not an instrumentation pin | 26172 / `8634e71383e4cfb39c8dfeb356f1da738e130a622ce4601239532733223f9c63` | 26172 / `8634e71383e4cfb39c8dfeb356f1da738e130a622ce4601239532733223f9c63` | 26172 / `8634e71383e4cfb39c8dfeb356f1da738e130a622ce4601239532733223f9c63` | unchanged dependency |
| `src/giclab/harness/lambda_ssh_key_request_ledger.py` | `/opt/giclab-project/src/giclab/harness/lambda_ssh_key_request_ledger.py`<br>`/opt/giclab-src/giclab/harness/lambda_ssh_key_request_ledger.py`<br>`/opt/giclab-accounting-src/giclab/harness/lambda_ssh_key_request_ledger.py` | `giclab.harness.lambda_ssh_key_request_ledger` / active-validation-input | not an instrumentation pin | 30123 / `19433aa77041365f20c4d43d25b3f1419380239d68a8893a18e15f0eaf4924e4` | 30123 / `19433aa77041365f20c4d43d25b3f1419380239d68a8893a18e15f0eaf4924e4` | 30123 / `19433aa77041365f20c4d43d25b3f1419380239d68a8893a18e15f0eaf4924e4` | unchanged dependency |
| `src/giclab/harness/models.py` | `/opt/giclab-project/src/giclab/harness/models.py`<br>`/opt/giclab-src/giclab/harness/models.py`<br>`/opt/giclab-accounting-src/giclab/harness/models.py` | `giclab.harness.models` / import-dependency | not an instrumentation pin | 49840 / `79de878cba256283a7bf360c8e1930ed67fdab9145059c509281c9752cadb739` | 49840 / `79de878cba256283a7bf360c8e1930ed67fdab9145059c509281c9752cadb739` | 49840 / `79de878cba256283a7bf360c8e1930ed67fdab9145059c509281c9752cadb739` | unchanged dependency |
| `src/giclab/harness/plan.py` | `/opt/giclab-project/src/giclab/harness/plan.py`<br>`/opt/giclab-src/giclab/harness/plan.py`<br>`/opt/giclab-accounting-src/giclab/harness/plan.py` | `giclab.harness.plan` / import-dependency | not an instrumentation pin | 12402 / `3ffbfea3ca16aacba6fab2db88e3f103888cb698294e45c94be2698864dd2f13` | 12402 / `3ffbfea3ca16aacba6fab2db88e3f103888cb698294e45c94be2698864dd2f13` | 12402 / `3ffbfea3ca16aacba6fab2db88e3f103888cb698294e45c94be2698864dd2f13` | unchanged dependency |
| `src/giclab/harness/policy.py` | `/opt/giclab-project/src/giclab/harness/policy.py`<br>`/opt/giclab-src/giclab/harness/policy.py`<br>`/opt/giclab-accounting-src/giclab/harness/policy.py` | `giclab.harness.policy` / import-dependency | not an instrumentation pin | 50697 / `e6a48e19b169c586123e30243837e2349c5767b57dd852daf953e2bb249cdc1b` | 50697 / `e6a48e19b169c586123e30243837e2349c5767b57dd852daf953e2bb249cdc1b` | 50697 / `e6a48e19b169c586123e30243837e2349c5767b57dd852daf953e2bb249cdc1b` | unchanged dependency |
| `src/giclab/harness/regulation.py` | `/opt/giclab-project/src/giclab/harness/regulation.py`<br>`/opt/giclab-src/giclab/harness/regulation.py`<br>`/opt/giclab-accounting-src/giclab/harness/regulation.py` | `giclab.harness.regulation` / import-dependency | not an instrumentation pin | 17438 / `02418042e29678d05774f123f829daa85e94f09c3f5839acafa558bc921e7001` | 17438 / `02418042e29678d05774f123f829daa85e94f09c3f5839acafa558bc921e7001` | 17438 / `02418042e29678d05774f123f829daa85e94f09c3f5839acafa558bc921e7001` | unchanged dependency |
| `src/giclab/harness/safety.py` | `/opt/giclab-project/src/giclab/harness/safety.py`<br>`/opt/giclab-src/giclab/harness/safety.py`<br>`/opt/giclab-accounting-src/giclab/harness/safety.py` | `giclab.harness.safety` / import-dependency | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` | 5802 / `12529af51aea206e02a531abea4959d80976bd271567f05c75e903654527d34c` | unchanged dependency |
| `src/giclab/harness/sira_colima.py` | `/opt/giclab-project/src/giclab/harness/sira_colima.py`<br>`/opt/giclab-src/giclab/harness/sira_colima.py`<br>`/opt/giclab-accounting-src/giclab/harness/sira_colima.py` | `giclab.harness.sira_colima` / import-dependency | not an instrumentation pin | 46831 / `b5c50dbe04f84de24aa1566603ae09f4c8cf8bf7a3d3398e3412ed7bbaf8c999` | 46831 / `b5c50dbe04f84de24aa1566603ae09f4c8cf8bf7a3d3398e3412ed7bbaf8c999` | 46831 / `b5c50dbe04f84de24aa1566603ae09f4c8cf8bf7a3d3398e3412ed7bbaf8c999` | unchanged dependency |
| `src/giclab/harness/sira_container.py` | `/opt/giclab-project/src/giclab/harness/sira_container.py`<br>`/opt/giclab-src/giclab/harness/sira_container.py`<br>`/opt/giclab-accounting-src/giclab/harness/sira_container.py` | `giclab.harness.sira_container` / active-validation-input | not an instrumentation pin | 147186 / `87efcd3f0d4ae327eade3c0005a3d4e42e331fe72c39ff6c398d7938383c302c` | 147186 / `87efcd3f0d4ae327eade3c0005a3d4e42e331fe72c39ff6c398d7938383c302c` | 147186 / `87efcd3f0d4ae327eade3c0005a3d4e42e331fe72c39ff6c398d7938383c302c` | unchanged dependency |
| `src/giclab/harness/sira_gate_a.py` | `/opt/giclab-project/src/giclab/harness/sira_gate_a.py`<br>`/opt/giclab-src/giclab/harness/sira_gate_a.py`<br>`/opt/giclab-accounting-src/giclab/harness/sira_gate_a.py` | `giclab.harness.sira_gate_a` / import-dependency | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` | 55897 / `edbda143d4a4271ad49d9b888a943192d4427395b79b14775312b27f10707c3d` | unchanged dependency |
| `src/giclab/harness/sira_gate_a_runtime.py` | `/opt/giclab-project/src/giclab/harness/sira_gate_a_runtime.py`<br>`/opt/giclab-src/giclab/harness/sira_gate_a_runtime.py`<br>`/opt/giclab-accounting-src/giclab/harness/sira_gate_a_runtime.py` | `giclab.harness.sira_gate_a_runtime` / import-dependency | 51033 / `0f1cd94fe048102704c9a4c461c6a3bf457ca53eb5586291441a675cd6b256a0` | 55760 / `7ff27906f6d1e8f83f434ad0dbae7800958cb18d5d01f56fa77b7f13b1560df6` | 56123 / `2ff3e50f4e45cea89cb17749205028afdf4e145534a6bc696662496c32df6b34` | 56123 / `2ff3e50f4e45cea89cb17749205028afdf4e145534a6bc696662496c32df6b34` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/harness/sira_storage.py` | `/opt/giclab-project/src/giclab/harness/sira_storage.py`<br>`/opt/giclab-src/giclab/harness/sira_storage.py`<br>`/opt/giclab-accounting-src/giclab/harness/sira_storage.py` | `giclab.harness.sira_storage` / import-dependency | not an instrumentation pin | 131263 / `0c8b111a657288278b519351d1a0973641c6897245bccc61228d90ddb5294c11` | 131263 / `0c8b111a657288278b519351d1a0973641c6897245bccc61228d90ddb5294c11` | 131263 / `0c8b111a657288278b519351d1a0973641c6897245bccc61228d90ddb5294c11` | unchanged dependency |
| `src/giclab/harness/t07_bounded_smoke.py` | `/opt/giclab-project/src/giclab/harness/t07_bounded_smoke.py`<br>`/opt/giclab-src/giclab/harness/t07_bounded_smoke.py`<br>`/opt/giclab-accounting-src/giclab/harness/t07_bounded_smoke.py` | `giclab.harness.t07_bounded_smoke` / active-validation-input | not an instrumentation pin | 79119 / `2ef4af297f7d1b8a577d9d6a970d5e678f4e852cd10c4dfa55fd836640f18e43` | 79119 / `2ef4af297f7d1b8a577d9d6a970d5e678f4e852cd10c4dfa55fd836640f18e43` | 79119 / `2ef4af297f7d1b8a577d9d6a970d5e678f4e852cd10c4dfa55fd836640f18e43` | unchanged dependency |
| `src/giclab/harness/t07_bounded_supervisor.py` | `/opt/giclab-project/src/giclab/harness/t07_bounded_supervisor.py`<br>`/opt/giclab-src/giclab/harness/t07_bounded_supervisor.py`<br>`/opt/giclab-accounting-src/giclab/harness/t07_bounded_supervisor.py` | `giclab.harness.t07_bounded_supervisor` / active-validation-input | not an instrumentation pin | 372594 / `eb22da1780112d11e4757570f855452b2063df498c2ccc7076f37089a1ce40c6` | 372594 / `eb22da1780112d11e4757570f855452b2063df498c2ccc7076f37089a1ce40c6` | 372594 / `eb22da1780112d11e4757570f855452b2063df498c2ccc7076f37089a1ce40c6` | unchanged dependency |
| `src/giclab/harness/t07_high_assurance_closeout.py` | `/opt/giclab-project/src/giclab/harness/t07_high_assurance_closeout.py`<br>`/opt/giclab-src/giclab/harness/t07_high_assurance_closeout.py`<br>`/opt/giclab-accounting-src/giclab/harness/t07_high_assurance_closeout.py` | `giclab.harness.t07_high_assurance_closeout` / active-validation-input | not an instrumentation pin | 34809 / `8234af2493824f914560cb9fd9a526d47a2a3795cc98609411c3c0c771b3987f` | 34809 / `8234af2493824f914560cb9fd9a526d47a2a3795cc98609411c3c0c771b3987f` | 34809 / `8234af2493824f914560cb9fd9a526d47a2a3795cc98609411c3c0c771b3987f` | unchanged dependency |
| `src/giclab/harness/t08_sira_smoke.py` | `/opt/giclab-project/src/giclab/harness/t08_sira_smoke.py`<br>`/opt/giclab-src/giclab/harness/t08_sira_smoke.py`<br>`/opt/giclab-accounting-src/giclab/harness/t08_sira_smoke.py` | `giclab.harness.t08_sira_smoke` / active-validation-input | not an instrumentation pin | 88099 / `2e12792066a4915981a2963a679e97c9c32252d7c0669cf364bfe4b8ee931588` | 88099 / `2e12792066a4915981a2963a679e97c9c32252d7c0669cf364bfe4b8ee931588` | 88099 / `2e12792066a4915981a2963a679e97c9c32252d7c0669cf364bfe4b8ee931588` | unchanged dependency |
| `src/giclab/harness/t09_candidate_inputs.py` | `/opt/giclab-project/src/giclab/harness/t09_candidate_inputs.py`<br>`/opt/giclab-src/giclab/harness/t09_candidate_inputs.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_candidate_inputs.py` | `giclab.harness.t09_candidate_inputs` / candidate-binding-input | not an instrumentation pin | absent | absent | 33407 / `ade76e3e203e7b18b6b954d97660eaaad767aa46c50a2acef7ae8cadbbcc3edc` | new candidate input/test |
| `src/giclab/harness/t09_cleanup_state.py` | `/opt/giclab-project/src/giclab/harness/t09_cleanup_state.py`<br>`/opt/giclab-src/giclab/harness/t09_cleanup_state.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_cleanup_state.py` | `giclab.harness.t09_cleanup_state` / import-dependency | 55024 / `39a4d698b8184c4d6652294f32e07911b2998b1a6326ad280353ba5f505e387e` | 55515 / `97163a2508680fbb1a766d23bd542b4feb242cd0037f146ee715b0fc96d7d711` | 55515 / `97163a2508680fbb1a766d23bd542b4feb242cd0037f146ee715b0fc96d7d711` | 58053 / `8fcc5d68676916e1a1cf728c719897cf38f8a69e8384a61bbf9e194a7456ee26` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/harness/t09_model_metadata_receipt.py` | `/opt/giclab-project/src/giclab/harness/t09_model_metadata_receipt.py`<br>`/opt/giclab-src/giclab/harness/t09_model_metadata_receipt.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_model_metadata_receipt.py` | `giclab.harness.t09_model_metadata_receipt` / import-dependency | 43545 / `88e39033963378454cfcb14f0d8d19dda1c72dc779e24696313f008e707363b5` | 43659 / `6ec6810ce5c0cad1d5a8fe7470c1f70d9d6449f56289f2e7edb8ff9813df404b` | 43659 / `6ec6810ce5c0cad1d5a8fe7470c1f70d9d6449f56289f2e7edb8ff9813df404b` | 43659 / `6ec6810ce5c0cad1d5a8fe7470c1f70d9d6449f56289f2e7edb8ff9813df404b` | unchanged dependency |
| `src/giclab/harness/t09_pragmatic_provider.py` | `/opt/giclab-project/src/giclab/harness/t09_pragmatic_provider.py`<br>`/opt/giclab-src/giclab/harness/t09_pragmatic_provider.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_pragmatic_provider.py` | `giclab.harness.t09_pragmatic_provider` / import-dependency | 372381 / `8ac3b563842ab994e86c96921e46e292195a8e8c9962165cfe22d8b0a5f1294f` | 384727 / `f406a40a5b800dbe19335d818e9e524f7bf0533c1b421091aaf85f6b144da512` | 384727 / `f406a40a5b800dbe19335d818e9e524f7bf0533c1b421091aaf85f6b144da512` | 386152 / `ac5b3ba7d9f901885f52068d80ade15c4df55206d3dafe69741906ddd3c8b3da` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/harness/t09_provider_contracts.py` | `/opt/giclab-project/src/giclab/harness/t09_provider_contracts.py`<br>`/opt/giclab-src/giclab/harness/t09_provider_contracts.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_provider_contracts.py` | `giclab.harness.t09_provider_contracts` / import-dependency | 47052 / `9c3ad548894c3ea52b151524d265cd158a10733d62183bd763aec33d116b615c` | 64903 / `024dbcfa3c343539fafb474fe48ffcf0fd6b5012746919fd35df4f89fb71210c` | 64903 / `024dbcfa3c343539fafb474fe48ffcf0fd6b5012746919fd35df4f89fb71210c` | 64903 / `024dbcfa3c343539fafb474fe48ffcf0fd6b5012746919fd35df4f89fb71210c` | unchanged dependency |
| `src/giclab/harness/t09_qualification_fixture.py` | `/opt/giclab-project/src/giclab/harness/t09_qualification_fixture.py`<br>`/opt/giclab-src/giclab/harness/t09_qualification_fixture.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_qualification_fixture.py` | `giclab.harness.t09_qualification_fixture` / retained-entrypoint | not an instrumentation pin | absent | 10709 / `ba4d8e8361cbec8d0e3b8055f8a4f9175ae42fc49cef737be401a560fd6f27dd` | 10709 / `ba4d8e8361cbec8d0e3b8055f8a4f9175ae42fc49cef737be401a560fd6f27dd` | new candidate input/test |
| `src/giclab/harness/t09_remote_host_phases.py` | `/opt/giclab-project/src/giclab/harness/t09_remote_host_phases.py`<br>`/opt/giclab-src/giclab/harness/t09_remote_host_phases.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_remote_host_phases.py` | `giclab.harness.t09_remote_host_phases` / import-dependency | not an instrumentation pin | 43450 / `b0721c5855ccb32d72ffe39afe5a5d72f8faab4a2c76fadbd07b992aa92004bc` | 43450 / `b0721c5855ccb32d72ffe39afe5a5d72f8faab4a2c76fadbd07b992aa92004bc` | 48057 / `b8996204393591052b34df3697234dd32f74b0401b7bb9fdd52334320b201fea` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/harness/t09_runtime_admission.py` | `/opt/giclab-project/src/giclab/harness/t09_runtime_admission.py`<br>`/opt/giclab-src/giclab/harness/t09_runtime_admission.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_runtime_admission.py` | `giclab.harness.t09_runtime_admission` / import-dependency | not an instrumentation pin | 31066 / `918a79ce52afce3957763d2b55e9b8ea5c22904bceeed35ae611ab8968f8c3bd` | 31587 / `6ef3c8f00904124cddd486de9775df8f6ee43d930708fe026a4e778bb3efb52f` | 31587 / `6ef3c8f00904124cddd486de9775df8f6ee43d930708fe026a4e778bb3efb52f` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `src/giclab/harness/t09_sira_pilot.py` | `/opt/giclab-project/src/giclab/harness/t09_sira_pilot.py`<br>`/opt/giclab-src/giclab/harness/t09_sira_pilot.py`<br>`/opt/giclab-accounting-src/giclab/harness/t09_sira_pilot.py` | `giclab.harness.t09_sira_pilot` / import-dependency | 150090 / `6e0574bddbb1585399ed9c19531b9191b571c483621a3585abe3c40d38a6c017` | 155554 / `7b197e0ed4b0cea214a8a27306616f0827b1e09e04ab003b73c4ee76dc390aa9` | 155554 / `7b197e0ed4b0cea214a8a27306616f0827b1e09e04ab003b73c4ee76dc390aa9` | 155554 / `7b197e0ed4b0cea214a8a27306616f0827b1e09e04ab003b73c4ee76dc390aa9` | unchanged dependency |
| `src/giclab/harness/task_source.py` | `/opt/giclab-project/src/giclab/harness/task_source.py`<br>`/opt/giclab-src/giclab/harness/task_source.py`<br>`/opt/giclab-accounting-src/giclab/harness/task_source.py` | `giclab.harness.task_source` / import-dependency | not an instrumentation pin | 601 / `fb0631241e134c58914d4c6cf9c8617313dbdb5a3b5472af2333fc674052639b` | 601 / `fb0631241e134c58914d4c6cf9c8617313dbdb5a3b5472af2333fc674052639b` | 601 / `fb0631241e134c58914d4c6cf9c8617313dbdb5a3b5472af2333fc674052639b` | unchanged dependency |
| `src/giclab/plans.py` | `/opt/giclab-project/src/giclab/plans.py`<br>`/opt/giclab-src/giclab/plans.py`<br>`/opt/giclab-accounting-src/giclab/plans.py` | `giclab.plans` / import-dependency | not an instrumentation pin | 1947 / `f7bcc8054788b64aa79c7d17d379730bf52448a9c0d1f04eb0e8d4faba657400` | 1947 / `f7bcc8054788b64aa79c7d17d379730bf52448a9c0d1f04eb0e8d4faba657400` | 1947 / `f7bcc8054788b64aa79c7d17d379730bf52448a9c0d1f04eb0e8d4faba657400` | unchanged dependency |
| `src/giclab/registry.py` | `/opt/giclab-project/src/giclab/registry.py`<br>`/opt/giclab-src/giclab/registry.py`<br>`/opt/giclab-accounting-src/giclab/registry.py` | `giclab.registry` / import-dependency | not an instrumentation pin | 5801 / `dd97677ffd28dd6e576fcac6507728acd59405236747d5b1beab61aecd731af4` | 5801 / `dd97677ffd28dd6e576fcac6507728acd59405236747d5b1beab61aecd731af4` | 5801 / `dd97677ffd28dd6e576fcac6507728acd59405236747d5b1beab61aecd731af4` | unchanged dependency |
| `src/giclab/sitegen.py` | `/opt/giclab-project/src/giclab/sitegen.py`<br>`/opt/giclab-src/giclab/sitegen.py`<br>`/opt/giclab-accounting-src/giclab/sitegen.py` | `giclab.sitegen` / import-dependency | not an instrumentation pin | 5645 / `90e929340d53fdcdaa2ce113234d0bf6cc2eb28ff43bf6fe7385c180b03f5b97` | 5645 / `90e929340d53fdcdaa2ce113234d0bf6cc2eb28ff43bf6fe7385c180b03f5b97` | 5645 / `90e929340d53fdcdaa2ce113234d0bf6cc2eb28ff43bf6fe7385c180b03f5b97` | unchanged dependency |
| `src/giclab/validation.py` | `/opt/giclab-project/src/giclab/validation.py`<br>`/opt/giclab-src/giclab/validation.py`<br>`/opt/giclab-accounting-src/giclab/validation.py` | `giclab.validation` / import-dependency | not an instrumentation pin | 185729 / `596fd8cd2960604bc925455a0c76dd174230ad673a66d18a03cca87a66a1dad3` | 185729 / `596fd8cd2960604bc925455a0c76dd174230ad673a66d18a03cca87a66a1dad3` | 185729 / `596fd8cd2960604bc925455a0c76dd174230ad673a66d18a03cca87a66a1dad3` | unchanged dependency |
| `tests/control/candidate_bootstrap.py` | `/opt/giclab-project/tests/control/candidate_bootstrap.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | absent | 17228 / `b6dcfb04139866df132d798322301da79cc843d709f9efb861f81e3490ba52db` | new candidate input/test |
| `tests/control/retained_candidate_effects.py` | `/opt/giclab-project/tests/control/retained_candidate_effects.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | absent | 21904 / `09be6f529859368063f71654606145c74c31ca298775ab8242ea5c40cfdae419` | new candidate input/test |
| `tests/control/test_candidate_inputs.py` | `/opt/giclab-project/tests/control/test_candidate_inputs.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | absent | 14960 / `8df14f581e856795c0b9a2b7b22f85720816cfdb821355fac24a37c0f6b49d6d` | new candidate input/test |
| `tests/control/test_qualification_fixture.py` | `/opt/giclab-project/tests/control/test_qualification_fixture.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | 9186 / `ba6a5451144ae486cbc661f2d827aa3f6e7cf27bd5a904be756d1c318d87e81d` | 9186 / `ba6a5451144ae486cbc661f2d827aa3f6e7cf27bd5a904be756d1c318d87e81d` | new candidate input/test |
| `tests/control/test_remote_bridge.py` | `/opt/giclab-project/tests/control/test_remote_bridge.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | 36551 / `36239320d099ebbe084a55a7b6897554afe929fb254f5e5908790c2b7b8c161d` | 39272 / `cae80d354235971d6d249325af32151539adb58e504d31ab9a947c64ecc4db9d` | 39272 / `cae80d354235971d6d249325af32151539adb58e504d31ab9a947c64ecc4db9d` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `tests/control/test_remote_host_phases.py` | `/opt/giclab-project/tests/control/test_remote_host_phases.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | 27188 / `9ced7e92e5aa1894420fe51e1b6271f9a8970ca4e0c8ef23bced585246829ca6` | 27188 / `9ced7e92e5aa1894420fe51e1b6271f9a8970ca4e0c8ef23bced585246829ca6` | 32343 / `70d77c157bb84d773d63e4922ce37d36ebc4b34ea89bc1f15134d7d3ed520cfd` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `tests/control/test_remote_terminal_review.py` | `/opt/giclab-project/tests/control/test_remote_terminal_review.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | 5042 / `6ace5c168377b8129d5975fe056c041ccdd44bb552ffffe49758102fd9adcf3f` | 7676 / `c39ac43043e2588fa2b26a3e9fa0d62586296e10a71b4cc117c7ab7603c7ffd1` | new candidate input/test |
| `tests/control/test_remote_transaction_review.py` | `/opt/giclab-project/tests/control/test_remote_transaction_review.py` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | 11652 / `b050579bf3083a411ad29096ff30d504801be50497ef2a1c3680d717f11aa2ee` | 11652 / `b050579bf3083a411ad29096ff30d504801be50497ef2a1c3680d717f11aa2ee` | new candidate input/test |
| `tests/fixtures/t09/fanout-two-task-fixture.json` | `/opt/giclab-project/tests/fixtures/t09/fanout-two-task-fixture.json` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 4941 / `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9` | 4941 / `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9` | 4941 / `5beff220f4d68bcf78d7a9767b5eb09b36e56944a563a8807220168c56f0eea9` | unchanged dependency |
| `tests/fixtures/t09/finalizer-raw-shape/host-cleanup-receipt.json` | `/opt/giclab-project/tests/fixtures/t09/finalizer-raw-shape/host-cleanup-receipt.json` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 400 / `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` | 400 / `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` | 400 / `d64c6075013cbde329f2ab5d1e216abb09f95285ce8fed1091256ff98aa72a47` | unchanged dependency |
| `tests/fixtures/t09/finalizer-raw-shape/normalized-events.jsonl` | `/opt/giclab-project/tests/fixtures/t09/finalizer-raw-shape/normalized-events.jsonl` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 855 / `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` | 855 / `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` | 855 / `b018fd63bc8fc8a1a302580c151aa2915d4c83c057a6f3fa6fbf116188a9a1df` | unchanged dependency |
| `tests/fixtures/t09/finalizer-raw-shape/provider-budget.json` | `/opt/giclab-project/tests/fixtures/t09/finalizer-raw-shape/provider-budget.json` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 435 / `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` | 435 / `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` | 435 / `f61417e1429c155ebc303a262003aa0ec237f4e31299a52432f2430431dfdb1c` | unchanged dependency |
| `tests/fixtures/t09/finalizer-raw-shape/provider-call-lifecycle.json` | `/opt/giclab-project/tests/fixtures/t09/finalizer-raw-shape/provider-call-lifecycle.json` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 2453 / `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` | 2453 / `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` | 2453 / `d92f4aaa60bd730ec0e8debcb20e69092e396ef7500b0e76985ecfe775ef8d16` | unchanged dependency |
| `tests/fixtures/t09/finalizer-raw-shape/runtime-environment.json` | `/opt/giclab-project/tests/fixtures/t09/finalizer-raw-shape/runtime-environment.json` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 220 / `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` | 220 / `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` | 220 / `0ab4e18c61f646a6876bb6218e0e807a168a378688f0f4ba38cf6a7c409de1f1` | unchanged dependency |
| `tests/fixtures/t09/finalizer-raw-shape/sira-output/PRIVACY-SAFE-FINALIZER-FIXTURE.json` | `/opt/giclab-project/tests/fixtures/t09/finalizer-raw-shape/sira-output/PRIVACY-SAFE-FINALIZER-FIXTURE.json` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 318 / `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` | 318 / `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` | 318 / `439d337b6fce3135f52594366068668f4c19836fed2746b58dd86ded546120d6` | unchanged dependency |
| `tests/fixtures/t09/offline-candidate-closure.json` | `/opt/giclab-project/tests/fixtures/t09/offline-candidate-closure.json` | `candidate-binding-input` / candidate-binding-input | not an instrumentation pin | absent | absent | 38390 / `1223f87e16a765d3bbc63aefecd21a2b264be19cb9fe3bf961871dcae66c0873` | new candidate input/test |
| `tests/fixtures/t09/pinned-evaluator/evaluator.py` | `/opt/giclab-project/tests/fixtures/t09/pinned-evaluator/evaluator.py` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 6776 / `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` | 6776 / `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` | 6776 / `2f99ec6ca40a5d5b49beea61c71d55a85652697b07f92a1c2aaefe85e727ab79` | unchanged dependency |
| `tests/fixtures/t09/pinned-evaluator/run.py` | `/opt/giclab-project/tests/fixtures/t09/pinned-evaluator/run.py` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 1537 / `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` | 1537 / `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` | 1537 / `e6741326a4b0d3a1fe542748d03c86f1e15f87c3de25b4937e17b3e2472afd17` | unchanged dependency |
| `tests/fixtures/t09/pinned-evaluator/utils/helpers.py` | `/opt/giclab-project/tests/fixtures/t09/pinned-evaluator/utils/helpers.py` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 1892 / `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` | 1892 / `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` | 1892 / `e816bb09d232d820edfc090ff7b2f8f5a4674f27e30b87a9a8d876ffd82c681e` | unchanged dependency |
| `tests/fixtures/t09/pinned-evaluator/utils/models.py` | `/opt/giclab-project/tests/fixtures/t09/pinned-evaluator/utils/models.py` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 1092 / `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` | 1092 / `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` | 1092 / `9638bc652ced674d3c6ff4b63148a913070cee01f350ca773dcbfa2ed1b01cd3` | unchanged dependency |
| `tests/fixtures/t09/pinned-evaluator/utils/norm.py` | `/opt/giclab-project/tests/fixtures/t09/pinned-evaluator/utils/norm.py` | `qualification-fixture-input` / qualification-fixture-input | not an instrumentation pin | 1897 / `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` | 1897 / `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` | 1897 / `c0a5da77ab7014bbb86e8310310b538881f01129d594afc537dd17d565b40eff` | unchanged dependency |
| `tests/test_t09_early_cleanup_state.py` | `/opt/giclab-project/tests/test_t09_early_cleanup_state.py` | `active-validation-input` / active-validation-input | not an instrumentation pin | 15898 / `98013715ba49e02b110f66f9120cca8f26030357c996dbccfd16b25cb185b690` | 15898 / `98013715ba49e02b110f66f9120cca8f26030357c996dbccfd16b25cb185b690` | 17751 / `23c4fb613396c213670bf26ea9abd05ffa7817500cd3600dd16a3ed32978c3c2` | R1–R6 repair/input propagation or active evidence; see path ledger |
| `uv.lock` | `/opt/giclab-project/uv.lock` | `historical-template` / historical-template | not an instrumentation pin | 418224 / `bec09cf0d326c56af9f717782eef9160579e7720dff701083570df9aa712b34b` | 418224 / `bec09cf0d326c56af9f717782eef9160579e7720dff701083570df9aa712b34b` | 418224 / `bec09cf0d326c56af9f717782eef9160579e7720dff701083570df9aa712b34b` | unchanged dependency |


### R3 continuation: early terminal ownership and freeze publication (development)

The 41st changed path, `tests/test_t09_v14_cleanup_lifecycle.py`, adds active
publication-contradiction and missing-publication regressions and updates existing
post-freeze fixtures to record the actual journal publication transition. Existing
unsafe-manifest assertions and node identities remain intact. The candidate closure
now contains 324 members; the preceding sealed 323-member audit remains historical
development evidence, not a claim about this later test delta.

The actual controller preflight-start failure initially reached retained early
cleanup but lacked the pilot cleanup document: 1 failed in 47.16 seconds. The
retained wrapper now binds its terminal observation to the actual early-journal
closeout or pilot cleanup source, with the same source verified downstream. After
that repair, the harness exposed that `_establish_provider` had already terminated
and cleared its provider handle before ordinary terminal host cleanup. That function
was AST-identical to the reviewed head before this repair. Ordinary failures now
retain the exact handle for the existing terminal cleanup path; the bounded
replacement branch retains its existing replacement handling. Neither change adds
a cleanup owner or a controller.

The two full-controller fault nodes
`tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[preflight-start-failure]`
and
`tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[qualification-start-failure]`
then passed together: **2 passed in 113.17 seconds**. Each reaches retained external
host cleanup and retained provider closeout with fake environmental effects and no
condition entry. This is a transaction prefix, not the required four-condition proof.

The journal now records freeze publication intent before the retained writer
publishes the manifest. Missing evidence after that intent remains unresolved;
legacy absent intent is unknown, not proof of no publication. The new node
`tests/test_t09_v14_cleanup_lifecycle.py::test_published_manifest_cannot_contradict_tracked_no_publication`
first failed at DID NOT RAISE, while its missing-manifest companion passed. The
lifecycle validator now rejects a present manifest when durable state says
publication never started. Existing unsafe-identity cases still test their original
specific rejection after their fixture records publication intent.

Latest focused validation after that change:
`tests/test_t09_v14_cleanup_lifecycle.py`,
`tests/test_t09_early_cleanup_state.py`,
`tests/control/test_remote_terminal_review.py`, and
`tests/control/test_remote_host_phases.py`: **75 passed in 2.60 seconds**, no skips or
xfails. The paired controller pass predates the final contradiction change and must
be regenerated with the final source ancestor. No full gates, parity, commits,
receipt publication, push, or new CI are claimed.

Remaining R3 limits include the complete pre-transfer/partial-transfer/freeze-attempt
matrix, exact replacement-directory/credential handling, and interrupted cleanup
through this joined harness. R1–R6 remain unresolved as complete findings. Historical
exact replay and live qualification remain not run; no scientific result is derived.


### Owner instruction: GitHub-hosted CI spending suspended

The current owner instruction suspends obtaining, dispatching, rerunning, or waiting
for GitHub-hosted CI for this repair. Hosted CI for repaired source is **not run by
owner instruction**, not passed. Historical run `33977310188` / job `101336174251`
remains evidence only for committed head
`a98b4b875ab4d101709d62bc7222b5c90681a893` and is not reused for changed source.

All pushes are held until the separate workflow-pause task reports verified
completion. No such completion has been received in this task as of this entry.
This task must not re-enable workflows, create replacement workflows, or fabricate
checks. Implementation, R1–R6 behavioral evidence, source binding, all required local
full-suite/parity/static/privacy/site gates, and independent exact-head review remain
required. No merge, science, provider, or live-execution authority is added. The
repair remains Category 1 and is continuing locally.


### Candidate local qualification and retained image-input continuation

Accepted additional paths are
`containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py` (42nd changed
path, explicit candidate input propagation and early ordinary-entry rejection) and
`tests/fixtures/t09/offline-candidate-historical-build-inputs.json` (43rd, exact
historical build-source inventory consumed by the no-network test worker).
The candidate source closure now contains 325 members. No experiment/manifest
scientific file has changed. The 17-file starting snapshot remains
`40934a7ee935ea0de7b27366e54626b6835d0553b1c44eb9ca317940e0a6864b`;
the original seven-file inventory remains
`6a3597adedbfec4eb0ba138ccb354077683b0b7177141f4697ea6c9cb038c1c7`.
Both private preservation roots were rechecked without alteration.

The new ordinary-entry node
`tests/control/test_candidate_inputs.py::test_normal_local_qualifier_rejects_candidate_before_runtime_access`
failed at the intended assertion (`['interpreter'] != []`, 1 failed in 5.50 seconds),
then passed in 5.50 seconds after candidate rejection moved ahead of runtime access.
This is a candidate-boundary regression, not an additional R1–R6 closure claim.
The producer now takes the same explicit candidate/qualification objects through
its private dependency seam; no normal CLI option or environment selects them.
The unchanged qualification fixture supplies its exact dataset/evaluator members.
Its actual input digest is separate from the frozen template dataset digest, and
candidate receipt provenance explicitly denies historical replay/live qualification.
The normal historical constants and scientific package projection stay unchanged.

The isolated local-qualification node executes the retained producer, actual fixture
regression and actual host qualifier validator. Only installed-package environmental
metadata is substituted: test-owned dist-info files are serialized and the retained
producer inventories their bytes. The local Python launcher is actually observed;
no model, browser or scientific evaluation is run by this qualifier. The first
wiring attempt used a wrong projection-source path (a prerequisite/harness error,
not behavioral evidence); correcting it to the retained source constant produced
1 pass in 16.81 seconds. Producer/consumer agreement subsequently passed in 16.17
seconds, then six receipt mutations plus historical-path rejection passed within
the same node in 16.99 seconds. These remain component results.

Joined `[transaction]` first entered actual external `_live_host_qualification`
and failed for its missing local qualifier input (1 failed in 62.95 seconds), with
retained cleanup/provider terminal verification passing. After the real test local
qualifier was wired before provider entry and its copied output bytes bound into
the phase request, that validation passed in the transaction. Subsequent failures
were guard rejections of as-yet-unbound environmental image inspection and historical
Git archive machinery (1 failed in 60.24 and 60.42 seconds). These are test wiring
prerequisites, not behavioral R4 evidence and not successful qualification. No
condition/freeze was reached. The same retained cleanup path remained successful.

The image fallback source inventory was generated from actual immutable commit
`5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23`, tree
`02060afa138ccb74385775c36db7b745c79aa8cc`: 65 regular files, 3,034,523 bytes,
member-manifest SHA-256
`86975bd9715b2f03bd4297e5dc0e6dcb6c7b37a1028f479dcba34fedd9893da2`,
tracked inventory-file SHA-256
`0d0a67325597aabfceb6b519cb4c0d64e9280a6be184876bef0488f665264909`.
Every path, byte count, SHA-256 and Git blob is in that inventory. These are historical
build inputs, not candidate instrumentation or the qualification archive. The
isolated worker admits only the exact retained local archive command, redirects its
repository locator to the immutable parent object store, and compares every archived
member with that inventory. Retained archive extraction and image orchestration
remain in the path. Git fetch/curl/Docker execution remain denied; no historical
archive identity is replaced by fixture bytes.

Latest focused component selection: **89 passed in 31.05 seconds**, including prior
R1/R2/R5, archive fixture, local qualifier producer/consumer and normal rejection.
The cleanup/lifecycle selection passed **75 tests in 3.12 seconds**. No skips/xfails
were introduced. Focused Ruff passed. Mypy on the local qualifier passed; the broader
host-module check still reports eight outstanding diagnostics, without claiming
baseline parity or a clean host-module typecheck. Cleanup-return and phase-result
annotations introduced by this repair were corrected. Full gates remain deferred
until behavioral/integration requirements pass.

A source-inspection correction: `execute_condition` can return a plain nonzero
process code after raw sealing; nonzero exit alone does not invariably take the
essential-exception branch. That branch still needs answer/error/exit preservation
coverage when it is taken. The existing partial-exit terminal component test is
valid for its documented substituted execution producer, not proof of every live
retained failure classification.


### Preserved image-input stop and local validation checkpoint

The next joined `[transaction]` attempt failed in 67.43 seconds after actual
historical Git archive generation, complete member verification and retained safe
extraction. Its source archive was 3,102,720 bytes with SHA-256
`5d455b86a30787576d6c1ce073bbc5da0b4b0494aecebbd60762ba6e15973391`.
The environmental guard then rejected the `git init` command in
`materialize_replacement_image` before execution. An ordinary temporary Git command
is not itself an authority conflict. The unresolved dependency is the subsequent
pinned upstream source/wheel materialization: the current test binding does not
supply those exact bytes, and the fallback would fetch/download them. This is a
blocked test prerequisite, not behavioral R4 failure evidence.

The required retained image archive is 1,207,128,576 bytes, SHA-256
`623e717c2182eca9cee2f471b7ecd9a57bead2f5263dee64aa5cd954eae5ddb0`.
It was absent at the explicit source-declared local locator. The fallback requires
SiRA commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`, tree
`6a6d9068b94d7632d3533a3d6f013d4de6ff76e8`, and the UV 0.11.7 wheel with SHA-256
`4e4d5e31bea86e1b6e0f5a0f95e14e80018e6f6c0129256d2915a4b3d793644d`.
The SiRA commit was absent from the already-authorized parent object store
(`git cat-file -e` returned 128). No open-ended search, download, real Docker
execution, invented tree/hash, or qualification-archive substitution was performed.
The existing 2,034-byte qualification fixture and candidate source snapshot are
separate roles and do not close this image-input requirement. The narrow missing
capability is reproducible offline exact image/build inputs, or an explicitly
separate image-input fixture contract that preserves normal historical acceptance;
this handoff does not implement or grant that additional contract.

The failed candidate binding was
`21f003e73305ee882d2fc2dfd7b80c1eb033bc1c981a9e57be2fbae0df82b6f5`.

Its source-member manifest digest was
`bdc83bd5209c5f1e6bd4b9af651219e3575a8883c0f250c44dcd65064210be4e`,
and dirty-delta digest was
`7a235387c7d74532ec37cb6d79c11392c0441efaf8dd8bbe52861caa2b8ae3c1`.
This was a dirty development snapshot above `a98b4b875ab4d101709d62bc7222b5c90681a893`,
tree `b75ce4579c934440c7679cbf289b3294d01d6caf`, not a committed/reviewed candidate.
The actual controller phase return codes were transfer 0, preflight 0,
qualification 1, cleanup 0. Provider terminal verification passed; no freeze or
condition executed. Retained receipt file/semantic SHA-256 pairs were:

| Phase | File SHA-256 | Semantic SHA-256 |
| --- | --- | --- |
| Transfer | `22e3a013d6d596d5bcc17ffafdf426740ff2b90440a0439a4f62a8c1abfe2ba4` | `041f02ef3750384e125ab4bd32bc894009362ad09be84930b5158d6c56efb178` |
| Preflight | `a914e6b05c87aea87fa3e161aade95ca6d92bc3d83c549b7a0d4c1e94b36a65a` | `aa2eb7f6538ecb201d42cd47f23bd932785b6147ffbedca675b07a83d1863076` |
| Cleanup | `1c984d17b01222991636117141447d7baf5612889e840544de595b283eeb914e` | `28ca752a370f5c7d64d689ad7e71f355f3411a2e6a022ba36f9cfac56a8592db` |

A final focused selection completed **5 passed in 156.73 seconds**:

- `tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[local-qualification]`
- `tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[preflight-start-failure]`
- `tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[qualification-start-failure]`
- `tests/control/test_candidate_inputs.py::test_normal_local_qualifier_rejects_candidate_before_runtime_access`
- `tests/control/test_candidate_inputs.py::test_candidate_snapshot_round_trip_and_deterministic_inputs`

These passes confirm those components and controller prefixes only. R6 remains
source-observed post-hoc reconciliation without a behavioral runtime-writer
characterization or repair; no direct observer-only call is presented as that
missing proof. R1/R2/R5 still need their joined campaign/downstream/timeout evidence.
R3 lacks its full lifecycle matrix. R4 lacks a four-condition causal transaction.
All six remain open; no success receipts or readiness claims are generated.

The failed transaction, exact candidate source and complete 43-path continuation
were retained outside Git in a private task-owned snapshot. Its inventory SHA-256 is
`45428c2b9f8401377f6711a0b75cd3bb334cd14c2598ea33a2b0454081dace95`;
383 records cover 13,094,729 copied bytes, including source/evidence, empty staged
patch and unstaged patch. Every retained file was rehashed after copying and again
at this checkpoint. The original seven- and 17-file snapshots remain unchanged.
The following inventory describes the preserved pre-checkpoint delta, not the
subsequent ledger/incident documentation bytes. All members are regular files;
modes are original source modes. No private path or credential is published here.

| Repository path | Mode | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `containers/sira-smoke/pragmatic/t09_freeze_commands.py` | `0644` | 6965 | `0ce8c64a9e1acad7da79fcac8ca5332cca391714c032ba26fca976370edf820d` |
| `containers/sira-smoke/pragmatic/t09_local_finalizer_qualification.py` | `0644` | 27550 | `049ce1d87655bafdc865e4b127692b52e0014d29e4f7bd10e6a2db60a944dab9` |
| `containers/sira-smoke/pragmatic/t09_real_evidence_regression.py` | `0644` | 24533 | `3e2896f88b3cb011b6970e4fc44057d97ca354ea552b5a686ec889d59637ab6c` |
| `containers/sira-smoke/pragmatic/t09_remote_runner.py` | `0644` | 1190666 | `41e88eae349d5fed82e3d88a4fc631c60d08a0836420cd521e8acadd70c32ba4` |
| `control/goals/EXP-0001.yaml` | `0644` | 3305 | `34634138cd72a083f39f837a6f5d94ea2a9c4485c4dcdd2749304b1ce4f93ea8` |
| `docs/PROJECT_STATE.yaml` | `0644` | 24833 | `957d85745a08c3685caa2fccb72c3f04687d2425983a0de7c49494e34a7bf7bf` |
| `docs/harness/T09_REMOTE_EXECUTION_BRIDGE_IMPLEMENTATION_LEDGER.md` | `0644` | 292214 | `2b210d18ef62f108291c0a8abb4c2b9dc3e8a7477b825eb225278a95efbb6fdc` |
| `schemas/agent-incident.schema.json` | `0644` | 14597 | `f4a458565d6560654300658878e6a2bf09e647322a7ad0ebc56a686a2c024a0f` |
| `schemas/agent-state-capsule.schema.json` | `0644` | 12050 | `eddc056fe270d5813d6fbcea70d4cf74c44ec15c427584aa7c6c949564f0d473` |
| `schemas/t09-early-cleanup-state.schema.json` | `0644` | 5255 | `c15beee060610fbc7d2ba1370598212678ec66268621badd909ce28e2f3cee0e` |
| `schemas/t09-host-phase-request.schema.json` | `0644` | 3626 | `d40ca9359c545480701083681478128dad0aee812e005860321b6cbb68326284` |
| `src/giclab/control/category3.py` | `0644` | 45961 | `cab19bfbf0877b0d05947e51afa6f253dc2deeab843339292c248e947788879f` |
| `src/giclab/control/composition.py` | `0644` | 14474 | `509a777b9652d087d7259fa634c9e1a0ed6713093e800f9a9c7426d04e06fee6` |
| `src/giclab/control/consumers.py` | `0644` | 18047 | `4cf41b11e1b3aa2c437a804128decd6ed2badc4637ea708dccc3c9fdbeb6bb7d` |
| `src/giclab/control/effects.py` | `0644` | 93448 | `650e7fd8488f87138432f421417f755fd947f559ad7e7e6eb9e3511cff59b05f` |
| `src/giclab/control/production.py` | `0644` | 282517 | `1c9aab0c6653930699edae597033b0178aa7fc36cfd3dcacaac93295c8afd9b4` |
| `src/giclab/control/proofs.py` | `0644` | 78194 | `93d66fea0cc3376fec401b6c2b2fa03e04ee9908c682b148650cb4b8084ec5e3` |
| `src/giclab/control/registry_validation.py` | `0644` | 19119 | `f80ff0ee87a3794ab521743b583581c66c6e93c8b2ad565353e1092f677448b1` |
| `src/giclab/control/remote_bridge.py` | `0644` | 104098 | `708e24064767cd625deef8d5e9181430b0b85a1feefb9345bc20d277b3ca8381` |
| `src/giclab/control/remote_execution_conformance.py` | `0644` | 61359 | `265da733dcb6d27c23b9e853de2c905ec33721d28d87e72cc1c3751995aac300` |
| `src/giclab/control/shadow_effects.py` | `0644` | 109956 | `2f70983847e53e73b8b8124526dd65a8c973fa57f9a7044b904202f317e51984` |
| `src/giclab/control/state_capsule.py` | `0644` | 8554 | `7624265f65699db68a5cde83d645be3bbe8438b0cf02f2a8aacbbd7d8b7e6f4b` |
| `src/giclab/control/version_lint.py` | `0644` | 13749 | `811dd05fbd49c7b63977d22de4bc6f5c3332a28bfb44fe45bc4b94e8eeb2b920` |
| `src/giclab/harness/sira_gate_a_runtime.py` | `0644` | 56123 | `2ff3e50f4e45cea89cb17749205028afdf4e145534a6bc696662496c32df6b34` |
| `src/giclab/harness/t09_cleanup_state.py` | `0644` | 58053 | `8fcc5d68676916e1a1cf728c719897cf38f8a69e8384a61bbf9e194a7456ee26` |
| `src/giclab/harness/t09_pragmatic_provider.py` | `0644` | 386152 | `ac5b3ba7d9f901885f52068d80ade15c4df55206d3dafe69741906ddd3c8b3da` |
| `src/giclab/harness/t09_remote_host_phases.py` | `0644` | 50113 | `0f3bf9b314b44ac91541f1534ea66216eaac281b270eac7f46650d1e8df5eb07` |
| `src/giclab/harness/t09_runtime_admission.py` | `0644` | 31587 | `6ef3c8f00904124cddd486de9775df8f6ee43d930708fe026a4e778bb3efb52f` |
| `tests/control/test_remote_bridge.py` | `0644` | 39272 | `cae80d354235971d6d249325af32151539adb58e504d31ab9a947c64ecc4db9d` |
| `tests/control/test_remote_host_phases.py` | `0644` | 32343 | `70d77c157bb84d773d63e4922ce37d36ebc4b34ea89bc1f15134d7d3ed520cfd` |
| `tests/test_t09_early_cleanup_state.py` | `0644` | 17751 | `23c4fb613396c213670bf26ea9abd05ffa7817500cd3600dd16a3ed32978c3c2` |
| `tests/test_t09_v14_cleanup_lifecycle.py` | `0644` | 40243 | `80480c6b2129bda95eac27c60f3ba7b791fe82c7aa56e22038775b4d50dd9411` |
| `control/incidents/INC-T09-RETAINED-REMOTE-TRANSACTION-REVIEW.json` | `0644` | 5553 | `777fb4c1d234e540424ee9afb94993d535d284b3ed05d9d0353e159aaa02d39f` |
| `src/giclab/harness/t09_candidate_inputs.py` | `0644` | 33407 | `ade76e3e203e7b18b6b954d97660eaaad767aa46c50a2acef7ae8cadbbcc3edc` |
| `src/giclab/harness/t09_qualification_fixture.py` | `0644` | 10709 | `ba4d8e8361cbec8d0e3b8055f8a4f9175ae42fc49cef737be401a560fd6f27dd` |
| `tests/control/candidate_bootstrap.py` | `0644` | 23799 | `a42edfc49e7a5fed3a05302261dd5b3f6bee0b80c273c14fce5c0c5511154888` |
| `tests/control/retained_candidate_effects.py` | `0644` | 28408 | `15200d3dc92189f22d592151d7b2302a7c579fb9b5eda2241fe860e8243288cb` |
| `tests/control/test_candidate_inputs.py` | `0644` | 17544 | `19a419b517567064171b095cc604f6979dd86a2feda2cda1a52871a7a92f10ca` |
| `tests/control/test_qualification_fixture.py` | `0644` | 9186 | `ba6a5451144ae486cbc661f2d827aa3f6e7cf27bd5a904be756d1c318d87e81d` |
| `tests/control/test_remote_terminal_review.py` | `0644` | 7676 | `c39ac43043e2588fa2b26a3e9fa0d62586296e10a71b4cc117c7ab7603c7ffd1` |
| `tests/control/test_remote_transaction_review.py` | `0644` | 11652 | `b050579bf3083a411ad29096ff30d504801be50497ef2a1c3680d717f11aa2ee` |
| `tests/fixtures/t09/offline-candidate-closure.json` | `0644` | 38636 | `13cb26b5d8fb3692da33780db7e0e10945d697a20c1f381d5b2fb1d58b605e97` |
| `tests/fixtures/t09/offline-candidate-historical-build-inputs.json` | `0644` | 16218 | `0d0a67325597aabfceb6b519cb4c0d64e9280a6be184876bef0488f665264909` |

Terminal disposition: `t09_remote_execution_bridge_review_repair_blocked`.
No implementation ancestor, commits, push, PR-body/review publication, new conformance
or viability receipts, or final full local gate cycle exists. Hosted CI for repaired
source is not run by owner instruction; the push hold remains in force because no
verified workflow-pause completion has been received. The index is empty and the
43 task-owned changes remain deliberately uncommitted. Latest read-only GitHub/Git
checks still show the exact starting local/remote/PR head and base, open draft PR,
unmerged state and disabled auto-merge. Frozen experiments/manifests have no diff.
Operator-attested GPT 6 Astra/high; runtime metadata not introspected; no delegation.
This is a direct incomplete worker assessment, not independent approval, merge
permission, scientific interpretation or live authority.


### Explicit offline image/environment addendum — resumed locally

Status: in-progress, all R1–R6 closure claims still partial. The owner expressly
resolved the earlier image-input scope boundary: use a separate small archive
fixture and deterministic environmental command channel through retained archive
load and qualification. No historical archive, SiRA tree, UV wheel, dependency
installation, real image build/load or external acquisition is authorized.
Hosted CI remains not run by owner instruction. Push and remote publication remain
held; no workflow-pause completion has been received here.

Read-only Git/PR verification again matched head
`a98b4b875ab4d101709d62bc7222b5c90681a893`, tree
`b75ce4579c934440c7679cbf289b3294d01d6caf`, and base
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`; PR 15 remains open/draft/unmerged,
auto-merge disabled. The empty index and 43 changed paths match the last preserved
inventory. Only the subsequently recorded ledger/incident checkpoint bytes differ
from that snapshot; every other source/test byte matches. A fresh private snapshot
retains all 43 files (3,381,894 source bytes), status and staged/unstaged patches.
Inventory SHA-256: `3d256c319baf732621ed180db5669501a8f0ade547d3f36f3bff0556f4e5015f`.
The original seven- and seventeen-file inventories remain unchanged at
`6a3597adedbfec4eb0ba138ccb354077683b0b7177141f4697ea6c9cb038c1c7` and
`40934a7ee935ea0de7b27366e54626b6835d0553b1c44eb9ca317940e0a6864b`.
The dirty snapshot is not the committed/reviewed head. Frozen experiments/manifests
have no diff. Operator-attested Astra/high, metadata not introspected, no delegation.

The new source path `src/giclab/harness/t09_environment_fixture.py` is narrowly
mapped to the explicit environmental input contract. Its candidate closure entry
uses the existing candidate-binding-input role. The deterministic image channel
is added to the existing `tests/control/retained_candidate_effects.py`; boundary
tests extend `tests/control/test_candidate_inputs.py`. No general framework or
alternate controller/cleanup path is introduced.

Definition of done for this continuation: exact deterministic fixture/input binding
and negative tests; stateful allowlisted environmental operations; retained
qualification and full downstream transaction causality; all R1–R6 behavioral
matrices; final local gates and immutable source/receipt binding. None of these is
closed by the map below. The archive input uses an actual deterministic USTAR
parser fixture, capped at 1 MiB (tighter than the authorized 16 MiB environmental
input ceiling). Actual archive bytes/SHA and simulated config/image identity are
separate fields. Historical constants remain the no-binding defaults. Offline
failure cannot enter the build/download fallback.

#### Remaining joined dependency/seam map

Every row names the retained caller/validator under test, not a replacement
receipt producer. Source paths are in `t09_remote_runner.py` unless stated.
Input/source/member identities are bound by the one candidate/environment manifest;
unknown command shapes are denied. Rows marked pending are planned evidence,
not execution proof. All rows leave actual deployment/kernel/credential/model
availability unproven.

| Phase / retained consumer | Input or environmental operation | Bound prerequisite / leaf channel | Independent assertion / current coverage |
| --- | --- | --- | --- |
| `ProductionCategory3World`, shared controller; local assembly | Full source package and held transaction identity | Exact candidate source closure, actual tar/rehash; provider responses only fake | G1 assembly before entry; one controller and accountant; prior prefix evidence only |
| `host_transfer_verify`, `_live_host_transfer_verify` | Post-entry archive transfer, ownership and full source validation | Local carrier copy of exact source archive; real verifier/journal | Wrong bytes/host/predecessor fail; transfer receipt causal parent; existing prefixes |
| `host_preflight`, `_live_host_preflight` | Provider receipt, host/core/OS/container inventory | Bound command observations and actual durable lifecycle | Unrelated host/phase/ownership rejected; preflight failure cleanup prefixes pass |
| `host_qualify`, `_live_host_qualification` | Complete phase request and predecessor | Same candidate/environment; `deterministic_fixture=False` | Must invoke every retained substep below and derive own phase receipt; pending |
| `materialize_retained_or_build_image` | Image archive, held descriptor, load/inspect/tag/remove | Explicit USTAR bytes/member manifest; stateful image command channel | Exact bytes accepted; drift before effects; incorrect inspect/failure rejected; tests in progress |
| `secret_channel_preflight` | Read-only local canary mount, uid/file observations | Test-created canary; execute retained canary script with OS observations bound | No value/hash retained, zero secret bytes read, exact cleanup; pending |
| `evaluator_overlay`, `_evaluator_package_records`, `validate_evaluator_overlay_binding` | Locked package metadata and overlay files | Deterministically serialized test dist-info/files; simulated installation command only | Real inventory/hash/package equality; mutation rejected; pending joined coverage |
| `final_image_file_hashes` | Source/interpreter/package file hashes | Actual candidate or separately declared fixture members; leaf hash command | No historical digest assigned to different bytes; real comparison rejects mutation; pending |
| `final_image_runtime_preflight` | Runtime and command rendering observations | Actual candidate preflight/writer/budget code in local subprocess; OS/upstream import observations bound | Repaired code executes, no canned runtime conformance receipt; pending |
| `provider_accounting_container_preflight` | Accounting regression command | Execute real candidate regression locally, fake model responses only | Exact terminal counts and bounded lifecycle from actual accounting; pending |
| `offline_runtime_preflight` | Runtime/finalizer/evaluator fixture inputs | Actual preflight code plus existing qualification fixture and candidate package | Command equality, fixture score 0.0 and no task effects from real consumers; pending |
| `stage_qualification_archive`, `qualified_real_evidence_regression` | Regression archive and evaluator inputs | Existing 2,034-byte/15-member fixture; real staging and regression program | Exact archive/member validation and independent fixture assertions; components passed, joined pending |
| `core_suppression_preflight` | Core-limit/OS observations and containment probe | Bound core/OS observations; never execute a real destructive core probe | Contradictory core report rejected; no claim of kernel containment; pending |
| `browser_lifecycle_preflight` | Named container lifecycle and browser observations | Stateful create/inspect/start/wait/remove, deterministic upstream browser effect | Real retained ownership/lifecycle validation and bounded removal; pending |
| `sealing_primitives_preflight` | Candidate commands, evidence files, clocks | Actual sealing/file validators and deterministic local clocks/files | Mutating seal/source/argv fails; no supplied success receipt; pending |
| `image_equivalence_adjudication` | Image config and functional input relationships | Explicit synthetic config/source expectations, historical template separate | Actual comparison derives synthetic-only adjudication; wrong config fails; pending |
| `gpu_snapshot` | GPU command observation | Explicit unavailable/no-use response | No GPU effect/acceleration claim; existing preflight leaf observation |
| `host_freeze`, `_live_host_freeze` | Qualification context, metadata observations, full dynamic manifest | Same candidate/environment, fake upstream metadata response; actual full schema/argv generation | No reduced manifest; candidate switch/source/policy mutation fails; pending |
| `condition_session`, runtime `run`, retained LLM factory and duplex peers | Four condition inputs, model/browser effects, output writers | Four fresh real local runtime processes, private IPC, deterministic upstream inputs | Noncolliding exact IDs/prior history, actual answers, pre-growth denial and bounded transport; pending joined proof |
| export, retained finalizer/evaluator entrypoints | Actual sealed raw/essential evidence and fixture evaluator | Actual export/validation/finalizer/evaluator fixture consumers | Answer/None/error/score 0.0 agreement and source mutation rejection; pending |
| `first_pair_checkpoint` | Task A finalized evidence | Actual retained checkpoint decision on same transaction files | B cannot start before true retained decision; pending |
| `host_cleanup`, `_live_host_cleanup`, `EarlyCleanupJournal`, retained provider closeout | Latest lifecycle/ownership and observed exact resources | Same stateful environment, fake provider absence responses, actual retained cleanup | Full pre/post-freeze/resume/timeout matrix and exact-owned idempotence; two prefixes passed |
| shared controller terminal release | Cleanup/authority/accounting outcomes | Actual controller, held descriptors and test-only authority | No silent clean/zero after missing evidence, no later condition after failure; pending joined proof |

Orientation `make state-capsule` failed with `prepared shadow did not qualify secret
channel`; it did not produce a successful state capsule. This is retained as an
unresolved gate result, not a new behavioral characterization. `make agent-check`
was started for orientation and its result remains pending at this entry. Final
full-suite/parity/static/privacy/site cycle remains deferred until joined evidence.


### Environmental component results and independent R6 characterization

The initial environmental selection failed 13 nodes before intended assertions
because the immutable historical config template was omitted from the candidate
closure. Adding that unchanged, source-referenced template is authorized input
closure work, not a historical hash override. The next two setup failures detected
bytecode writes from dynamic imports into a sealed source snapshot. The helper now
disables bytecode during those imports; snapshot membership checks stay active.
Neither setup error is R1–R6 behavioral evidence.

The exact deterministic input and retained materializer happy path then passed
2 tests in 11.95 seconds. The full image input/materialization selection passed
**13 tests in 76.94 seconds**, including exact bytes, two fresh input builds,
same-size/one-byte/missing/source/binding drift before commands, historical-entry
rejection, wrong image inspection, load error, partial output, timeout and missing
image. The retained code generates its own load/context/phase evidence and failed
loads cannot select a build fallback. No Docker executable/daemon is called.

Actual retained `t09_secret_preflight.main` runs through the allowlisted command
channel, opens the test canary read-only without reading its value, and writes its
own receipt. The real `secret_channel_preflight` consumer accepts expected uid and
rejects a contradictory uid; exact cidfile registration/absence/cleanup code runs.
The two canary cases passed in 11.41 seconds; the combined environmental selection
passed **15 tests in 91.21 seconds**. These are component tests: their canary fixture
starts with a simulated loaded-image prerequisite, whereas joined state must come
from actual retained materialization. Canary setup initially omitted the pilot
state; it was corrected with actual `initialize_state`, not a fabricated receipt.

`tests/control/test_remote_transaction_review.py::test_r6_runtime_event_writer_cannot_grow_without_shared_output_headroom`
failed at its intended assertion in 0.48 seconds, then again in 0.46 seconds while
preserving its exact event prefix. The shared `ProviderBudgetBoundary` starts with
previously consumed aggregate output equal to its unchanged cap. The actual remote
factory receives the retained `EventWriter` and writes **1,210 unadmitted bytes**
before the shared observer rejects output; expected denied growth is zero bytes.
This is a source-bound component red on the dirty continuation, not a joined result
or a claim that the entire reviewed commit was rerun. The EventWriter AST was
compared with `a98b4b8...` and is identical; the factory carries the existing R1 fix.
Private source/evidence snapshot inventory SHA-256:
`b485828203cee37657f304d9e39c926b34d87c263979ee453b86c8903c2637e7`;
event-prefix SHA-256:
`3472ad61971d0b9af7cf01a0e677083025d1a79e5c18bdcdf23b43c38fd5a0f7`.
The node remains active and red. No skip/xfail or weaker assertion was introduced.

Both orientation `make state-capsule` and `make agent-check` returned failure
`prepared shadow did not qualify secret channel`. The new environment module
passes focused mypy; focused Ruff passes. The host module still has eight
outstanding type diagnostics at the previously observed sites; no baseline parity
or successful full gate is claimed.

During renewed phase wiring, one attempt failed on the missing required `label`
argument to `PhaseFile.read` (51.99 seconds). The next rejected an extra environment
input against the exact transfer input-role set (51.73 seconds). Both failed before
joined behavior and left cleanup unresolved; they are not successful R4/R3 evidence.
The input-role set remains strict. Environment identity is instead being added as
an explicit optional hash in the existing typed remote host binding, permitted only
with candidate source identity and checked against the private loaded context.
The same hash will participate in predecessor equality. This replaces the erroneous
extra-input wiring, not the staging verifier or its required source/member checks.

### Continued environmental and writer repair (dirty source; no closure claim)

The joined attempt subsequently reached retained transfer and preflight, actual
archive materialization and the retained canary. It failed in
`evaluator_overlay` at an unmodeled low-level container command (67.92 seconds).
Cleanup also failed its exact image comparison: it still selected historical
image/archive identities although qualification had explicitly selected the
synthetic environment. This is an observed, directly related cleanup defect;
no freeze or condition occurred and cleanup was not reported successful.
The privacy scan itself retained an empty violations list. The controller's
unresolved cleanup disposition must not be relabelled as a successful transaction.

The retained materializer now uses actual `stage_verified_archive` to publish an
exact-owned image copy under the transaction. Cleanup selects the same validated
candidate/environment image ID, staged archive path and archive SHA, through the
private context; historical defaults remain unchanged. Original fixture inputs
remain outside cleanup ownership. The existing 15 environmental component nodes
passed again in **97.58 seconds** after that change. Full-controller cleanup after
this change remains unverified.

Environment fixture revision 2 adds explicitly serialized dist-info METADATA
inputs derived from the frozen evaluator dependency inventory. Its image archive
bytes remain unchanged from revision 1; the environment binding and input inventory
are distinct revision-2 identities. This is metadata input generation and a modeled
command copy, not dependency installation. The exact allowlisted `uv sync` command
copies those bound inputs; modeled `uv pip freeze` reads actual copied metadata via
`importlib.metadata`. Retained overlay inventory/hash/package validators and
cleanup journal execute. The active node
`tests/control/test_candidate_inputs.py::test_retained_overlay_derives_inventory_and_rejects_metadata_drift`
passed **1 test in 44.76 seconds**, including real revalidation and rejection after
metadata mutation without changing expected hashes. It is component evidence,
not historical package installation or joined qualification success.

The R6 red above is now followed by a narrow source repair. Existing
`ProviderBudgetBoundary.reserve_output_bytes` reserves cumulative condition output
capacity under its own lock and existing caps, separately from observed bytes.
Provider reservation projection retains this output reservation; observed bytes
consume it and an interrupted writer leaves an upper bound. The shared observer,
existing duplex protocol and runtime port convey that allocation. The retained
`EventWriter` asks for admission before opening/writing its event, uses partial
unbuffered writes, and reports actual file growth. The actual LLM factory binds
that writer to its admission port. Newly edited `sira_gate_a.py` and
`t09_sira_pilot.py` are in-scope R6 source already present in the candidate closure;
they are explained additions to the dirty-file inventory, not unrelated work.

The same R6 node passed **1 test in 0.49 seconds** with zero denied event bytes.
Two active protocol/writer nodes passed **2 tests in 0.16 seconds**:

- `tests/control/test_remote_bridge.py::test_output_allowance_is_shared_and_distinct_from_observed_usage`
- `tests/control/test_remote_bridge.py::test_actual_event_writer_reconciles_exact_bytes_after_shared_grant`

They prove separate lower/upper output accounting, preservation across a model
reservation release, rejection beyond the cap despite a forged local mirror, and
exact written event-byte reconciliation. Earlier bridge/terminal/review component
selection passed **56 tests in 3.85 seconds**. Broader focused selection (bridge,
review, terminal, Gate A and pilot tests) produced **158 passed, 1 failed in 12.10
seconds**. The failure is
`tests/test_t09_sira_pilot.py::test_t09_provider_is_a_narrow_adapter_over_the_retained_t07_pragmatic_path`,
which could not open the historical T07 launch-request artifact. This is an
unavailable historical test prerequisite; it is not an R6 behavioral failure or a
raw-green/parity claim. Exact-base parity has not yet run.

R6 remains partial: runtime logs, bridge journals, other evidence writers,
cleanup reserve and full transaction final reconciliation still need containment
and integration. The event-writer pass does not close that requirement. All six
findings and readiness remain unresolved pending their full matrices and one
causal retained transaction. No final source ancestor, receipts, commit or
publication is established. Hosted CI remains not run by owner instruction;
push/publication remain held pending verified workflow-pause completion.

### Retained qualification prefix advanced; environment revision 3

Environment revision 3 adds eight exact image-file observations and an inert
command-rendering file for the `/usr/bin/timeout` filesystem identity. Five image
files are copied from the candidate's actual source; upstream import and package/
interpreter observations are explicitly synthetic. The upstream import fixture
raises if any condition entrypoint is invoked. The timeout metadata file is never
executed. No historical digest is assigned to these bytes. The actual retained
file-hash consumer selects the complete bound test map only through the explicit
candidate/environment context. Its historical default map remains unchanged.
The unchanged bounded `model_preflight.py` source was added to the existing
candidate closure, now 328 members. The image archive remains 10,240 bytes with
SHA-256 `b6ffdb92fac18ccd915d068245e2e6ef7d374292b527bc4d730767bc2c7b117c`.
Its config member is 619 bytes, SHA-256
`b9e10f884d3f2b24008bef830b0a518c3c3516b7ad4e9243cf122e76178aba99`;
manifest.json is 111 bytes, SHA-256
`ee4ac19305c50c16f46bce60a493467fe07be23e639ba96ee071f7dbba5d6c98`.
The simulated daemon image ID is derived from the config bytes, not the archive
SHA. Overlay metadata has 51 members. All environmental inputs stay below the
1 MiB fixture cap; files are now sealed read-only (the inert command file has
owner execute metadata for the retained renderer, without being dispatched).

The retained runtime preflight now accepts the same explicit input context. It
executes its actual import, artifact writer, budget, command-rendering and owned
cleanup checks. The logical `/usr/bin/timeout` path is mechanically mapped only
for this non-executing filesystem/rendering probe; all other command arguments
remain equal. The local Python interpreter is observed separately from simulated
image interpreter identity. Normal historical constants and CLI selection remain
unchanged. `runtime_preflight.py` and `t09_preflight.py` are additional explained
in-scope edits to existing candidate closure members, for this permitted input
propagation; they are not frozen scientific document edits.

The retained accounting preflight's real implementation also runs locally,
including its fake response/error, concurrent reservation and bounded shutdown
regressions. Its receipt is generated by that code. No ready-made accounting,
qualification or phase-success receipt is supplied. The next retained offline
preflight is being wired to the existing archive/dataset/evaluator fixture with
explicit input binding and the original logical command paths. Its fixed semantic
fixture assertions are preserved; it has not yet passed in the joined transaction.

Observed incremental outcomes, all using the active `[transaction]` node:

- 82.04 seconds: legitimate descriptor-relative staging write was rejected by the
  test audit guard, which lacked `dir_fd` context. Retained cleanup and terminal
  provider verification passed. This was harness setup, not an R1–R6 red.
- The guard now tracks exact held directory descriptors/inodes and checks the
  resolved transaction path for `openat`; it does not allow arbitrary relative
  writes. Directory closure removes the tracked descriptor identity.
- 78.56 seconds: actual image load, canary and overlay completed; the file-hash
  fake omitted the retained command's required `--log-driver none` tokens and
  rejected the command. Cleanup and terminal provider verification passed.
- `test_retained_image_file_hashes_are_bound_actual_bytes` first failed at that
  command-shape mismatch in 6.66 seconds, then passed in **7.41 seconds**, including
  mutation rejection before another command. This is a component input/consumer
  test, not a historical image qualification.
- 78.49 seconds: actual runtime preflight reached command rendering and correctly
  rejected the initial incorrect assumption that argv[0] was Python. The retained
  command actually starts with `/usr/bin/timeout`; its Python path is argv[4].
- 76.19 seconds: corrected runtime preflight passed, followed by rejection of the
  not-yet-modeled provider accounting command. Retained cleanup passed.
- 73.82 seconds: real provider accounting preflight passed, then the unmapped
  offline-preflight command was rejected. Retained cleanup passed.
- 74.05 seconds: offline-preflight exact command comparison rejected an incorrect
  overlay mapping in the new channel. The mapping has been corrected from the
  retained caller's actual `qualification-inputs/evaluator-overlay` argument.
  Cleanup remained successful; no freeze or condition entry occurred.

The 73.82-second prefix and its exact candidate source/inputs are preserved in a
private task snapshot: 652 files, 30,589,401 bytes, inventory SHA-256
`8f794c9e047e84a40508c1f5446740b3930a865adac40ecfdf13239439cfdb40`.
This includes both bounded generated local source archives; it is not an increase
to the separate environmental-input cap. Source binding for that observed prefix:
`f900acd29a6524e8c24f23ded176f36b3f97471e19849890900d44fb56320f61`;
source-member manifest:
`783b00e272f0441669a57822a1079bf48999f6387a048072bf5d0b8523725b02`;
environment binding:
`807157a3035bd6f46f376fb87368eecbc4ca4063dc9256366d70fa6a5a78b6ee`;
environment generator source:
`6a07bedd0c623291eab38cba10bfd5c3a76a53e9ee20a2d328ba0a2e40d42be7`;
channel implementation source:
`175b5cb6c037feca9f1ed56f7c994d2c20b6ccb0caa2f15750979e761392e895`.
These bind that earlier dirty snapshot, not subsequent edits or a final ancestor.

Targeted Ruff passes. Mypy now passes the environment module and retained host
runner after correcting the existing variable shadowing, result annotation and
untyped keyword-expansion sites; these are type-surface fixes with unchanged
arguments and behavior. Mypy also passes the candidate-enabled offline preflight
and the four selected accounting/bridge/writer modules. This is not the final
repository gate cycle. The call-trace wiring now records actual retained function
entries and source hashes on both failed and successful phase exits; it is labeled
an execution trace, never a success receipt. Joined qualification and all-condition
completion remain unproven. Hosted CI and publication remain held as already stated.

### Continued retained environment wiring — partial, no repair closure

The worker remains operator-attested Astra/high, with runtime metadata not inspected
and no delegation. Hosted CI remains **not run by owner instruction**. No verified
workflow-pause completion has arrived; push and remote publication remain held.
The committed source remains `a98b4b875ab4d101709d62bc7222b5c90681a893`;
all work below is an additional dirty source/test delta, not evidence for that commit.

The incident regression index briefly contained three newly appended string entries
instead of `{kind, reference}` objects. `make incident-check` and the joined test
rejected that schema error; neither run is a behavioral characterization or a passed
gate. The entries now use the existing schema, and direct
`validate_incident_document` returns no errors. Immutable incident facts are unchanged.
The expensive incident regression command was not rerun during integration wiring.

The bridge/review/terminal selection passed **58 tests in 3.86 seconds**. An
environment selection produced 16 passes and one setup rejection because the source
snapshot changed while copying; the rejected `environment_drift...[missing]` node
passed alone in 6.09 seconds after the source stabilized. This is 16 passes plus one
rerun, not one all-green combined run. A joined watchdog expired after 90 seconds
(94.71 seconds overall); retained cleanup subsequently existed and inspection found
no matching remaining worker. This is not full-controller R5 timeout acceptance.
The parent joined-test watchdog is now 180 seconds for the transaction case only;
retained phase and transport deadlines remain unchanged. A separate trace-path
setup bug used a method as a path; it was corrected to the actual transaction root.

Environment fixture `T09-OFFLINE-IMAGE-ENVIRONMENT-FIXTURE-1` now has revision 4.
Revision 3 and its preserved evidence remain historical test-input provenance.
The archive remains 10,240 bytes with SHA-256
`b6ffdb92fac18ccd915d068245e2e6ef7d374292b527bc4d730767bc2c7b117c`;
its simulated config/image identity remains separate. Revision 4 adds the tracked
static HTML input and a small explicitly nonexecutable simulated Chromium identity,
plus declared resource/signal/browser observations. The source closure now contains
329 members, including unchanged `containers/sira-smoke/fixtures/static.html`.
The qualification archive fixture remains the same 15-member, 2,034-byte input.
No source, wheel, image, or other dependency was acquired or installed.

The stateful command channel now covers exact core/browser create, inspect, start,
wait, stop, and remove operations. It invokes the actual retained core suite,
inheritance routines and scanner, and the actual retained browser probe. Only the
resource/signal observations, private filesystem mount mappings, and stateful
Playwright leaf are modeled. Real browser, signal abort, kernel containment, image
boot and daemon import are not tested. The ordinary host expectations stay historical;
explicit candidate/environment parameters bind the offline file hashes and scan roots.
Image comparison evidence now explicitly leaves real runtime equivalence unknown.

New active node
`tests/control/test_candidate_inputs.py::test_retained_process_qualification_uses_bound_observations`
passed all four cases `[core-None]`, `[core-core-limit]`, `[browser-None]`, and
`[browser-browser-version]` in 24.91 seconds, including exact container cleanup.
The first attempt had two passes and two unknown-fault setup errors; those errors
were not negative behavioral evidence. The real image-file hash node and deterministic
input node passed together (2 tests, 11.97 seconds). The new
`test_offline_freeze_inputs_reject_missing_or_mixed_selection` passed (1 test,
6.47 seconds): an incomplete or mixed candidate/environment/archive selection is
rejected, including no explicit binding on a candidate package.
Targeted Ruff passed and mypy reported no errors for the environment and host modules.
These are focused checks, not the final full validation cycle.

The joined test remains failing during wiring. Its successive retained paths reached:

- Actual offline preflight, then regression scratch allocation rejected outside the
  private root (94.70 seconds overall). The scratch directory is now explicitly bound.
- The added browser-file inputs exposed an incomplete explicit role set in the retained
  file-hash input selector (79.75 seconds overall); the exact offline role set now
  includes both additional bound files and its real hash regression passes.
- Actual staged regression and its real semantic consumer, then scratch deletion
  rejected because plain read-only directory descriptors were not recorded by the
  test guard (95.29 seconds overall). Cleanup remained unresolved and detected a
  test credential/privacy condition; this was not reported as zero activity/clean.
- After descriptor tracking used actual `fstat` directory type, regression completed
  and the next unbound core command was denied before external process execution
  (100.03 seconds overall). Retained cleanup and terminal provider verification passed.
  Core command routing now reaches the same stateful leaf tested above; retry pending.

The unresolved cleanup prefix and its exact 329-member source were privately
preserved as 471 regular files, 10,527,052 bytes. The inventory SHA-256 is
`d5978e0d052d6bc53a17a38f91903dd6e215e4e5f5dbc9e5e015d63697d09133`;
candidate binding SHA-256
`a3fd98a0852571e4d24c013990eb0e994c1178cce1f2d8bec42966d32d820fea`;
source-member manifest SHA-256
`270794e3ef8ebca236e9e05df73d947186eaf2c47bd9e3f6e9e46eb0261a3ae6`.
The snapshot retains source, binding and transaction JSON evidence, not credential
files or a purported successful receipt. An initial snapshot attempt rejected an
atime-sensitive metadata comparison and is not counted as a valid preservation;
the successful copy verified stable inode/mode/size/mtime, no-follow reads and rehashes.

Qualification receipt projection and full candidate freeze input propagation are
implemented but not yet established by a passing joined phase. The same retained
writer/loader still enforces full manifests and source relationships; candidate
archive expectations are separate from historical regression expectations. The
shared runtime, downstream finalization/evaluation, checkpoint, complete R3/R5
failure matrices, and all-role R6 before-growth containment remain unfinished.
All six readiness findings remain unresolved; no success receipts, implementation
ancestor, commits, push, hosted CI, scientific result or live authority were created.

### Stopped handoff — unguarded environmental probe, repair still incomplete

A newly added standalone test initially lacked the joined bootstrap's process guard.
`test_retained_sealing_probe_does_not_publish_container_mutation_authority` called
the actual `docker_prefix`, which attempted `docker info` and
`sudo -n docker info` through `subprocess.run`. Both returned nonzero and the test
stopped with `Docker is unavailable` (7.65 seconds). Their output was directed to
DEVNULL. No image build/load or condition launch was requested by these commands,
but the calls crossed the authorized offline boundary. Their actual daemon contact
cannot be established from discarded output, and no further Docker query was made.
**Zero real Docker invocations cannot be claimed for this worker run.** No model,
provider, browser, benchmark, image build/load, or scientific execution was enabled.
The owner must disposition this boundary breach before the task can claim its
zero-real-effects acceptance requirement; this is not a request for live authority.

The test now has an explicit `subprocess.run` channel admitting only the exact
30-second Docker-info observation as synthetic input and a `Popen` guard denying
all process creation during the probe. The guarded rerun failed at the intended
behavioral assertion (5.60 seconds): the retained sealing producer leaves synthetic
`container-command.json` files inside the real mutation-intent search root, and
`owned_container_intents` rejects those fixture files as malformed. The producer's
AST was identical to reviewed head before this characterization (SHA-256
`cd1cbb1f4b27eb245d646a06005a33d8ad419ebbc382f6bafc91d4d33f3689d4`).
The intent loader already had a mechanical type-variable rename; its source delta
must not be described as byte-identical to reviewed head. This new R3/R4 failing
regression remains active and **unfixed**. No folder exclusion or weakened ownership
check was introduced to hide it.

The latest joined retry preceding this stop reached actual core/browser qualification,
sealing primitives and evaluator-overlay revalidation, then rejected missing
Architecture/Os fields in the simulated inspect observation (121.76 seconds overall).
The channel now derives those fields from the bound archive config, but that correction
has not been verified by a subsequent joined run. Its failed cleanup remained unresolved:
synthetic sealing command records polluted the intent ledger, and the harness placed
its fake model-canary file inside the globally scanned artifact root. The harness now
maps that test credential to an exact transaction-owned sibling credential directory;
this mapping change also remains unverified by the joined path. Neither failure was
converted into clean zero. A full retained freeze adapter and candidate archive/image
binding propagation have been added but remain untested end to end.

Terminal status: `t09_remote_execution_bridge_review_repair_blocked`.
Remaining work: resolve the test-boundary disposition; repair and test sealing-probe
ownership isolation; finish candidate freeze and four-session shared-controller wiring;
complete actual-answer/finalizer/evaluator/checkpoint agreement; complete all R3/R5
failure/cleanup matrices and R6 output roles/allowance reconciliation; finish coupling
and rejection matrices; then run final local gates and freeze/rebind source evidence.
No finding is closed. No final conformance/viability/source/aggregate receipts were
generated, no implementation ancestor was committed, and no PR update or push occurred.
The clean final worktree requirement is not met: the preserved continuation has 48
explained dirty paths and an empty index. Full-suite/parity/site gates were not run
for this dirty candidate. Hosted CI is not run by owner instruction; publication
remains held with no workflow-pause confirmation received.

Read-only Git/GitHub verification at this handoff still reports feature/local/PR head
`a98b4b875ab4d101709d62bc7222b5c90681a893`, tree
`b75ce4579c934440c7679cbf289b3294d01d6caf`, destination/base
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`. PR15 is open, draft, unmerged,
auto-merge disabled. `git diff --check` passed and experiment/manifest diff remains
empty. Historical CI is not evidence for the dirty source. Independent exact-head
review and Joseph's separate merge authorization remain required; neither is supplied.

Preservation closeout: the 48-file dirty continuation, exact staged/unstaged diffs,
status, unguarded test's complete sealed source, guarded regression test delta,
and late joined failure evidence were copied privately and rehashed. The snapshot
contains 646 records / 15,534,787 bytes; inventory SHA-256
`ca6d6aba4cf5065056b0d2bc39a4d5f58edb1f3cc98001b51001e32cf48a37a8`.
The index was empty. This paragraph is an additive ledger descendant of that snapshot,
not part of the snapshot's own source identity. Final focused Ruff passed, mypy passed
for the two environment/host modules, and `git diff --check` passed. No final full-suite,
parity, site, hosted CI, source freeze, receipt rebind or publication is claimed.

### Owner incident disposition and bounded local CI continuation

The owner acknowledged the two historical `docker info` / `sudo -n docker info`
attempts and authorized forward remediation. Both failed; original output remains
unavailable and daemon contact remains unknown. This is not retroactive approval
or a zero-effects record. Do not reenact the old probe. Newly authorized outer CI
operations are separate from prohibited experimental effects and intercepted tests.

Read-only verification: local/remote/PR head remains a98b4b875ab4d101709d62bc7222b5c90681a893,
HEAD tree b75ce4579c934440c7679cbf289b3294d01d6caf, base
f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2. PR open/draft/unmerged, auto-merge disabled;
original checkout clean, index empty, frozen experiment/manifests unchanged. All 48
paths reconcile exactly to the previous snapshot except its documented additive
ledger closeout. All 646 previous inventory records and the original seven/seventeen
source snapshots were rehashed successfully. A new private 48-file snapshot records
3,825,070 source bytes, modes/types, patch and committed parent identities; inventory
SHA-256 1559ab631436a36c9a78abaf54b0150b0b031f77ed7ce543a75887f39895af89.
No actual successor package or current live authority was found.

DoD mapping and order: shared pre-import/collection/child guard (R3/R4, in progress);
bounded pinned CI launcher/runner (not started); probe namespace and negative authority
regressions (R3/R4, not started); remaining joined/runtime/output matrices (R1-R6,
partial); immutable ancestor/receipt descendants/final container parity (not started).
The single joined transaction remains the acceptance test; component tests close no
finding. Operator-attested Astra/high; metadata not introspected, no delegation.
Hosted CI is not run by owner instruction. Push/publication remains held pending
verified workflow pause. No remote mutation is performed by this continuation.

### Guard and probe namespace results; container prerequisite remains blocked

The shared explicit CI bootstrap now installs an audit guard before pytest import,
collection and fixtures; ordinary test invocation installs the same policy in
`tests/conftest.py`. Child Python environments retain it. Concrete test-owned
temporary allocations scope named Unix IPC; socketpair and real Python pipes run.
Docker/sudo/unknown processes and external connections are denied before dispatch.
A named negative test expects one exact denial without erasing records. A separate
caught-denial probe exited 90 despite catching the rejection; its sticky journal
was preserved. This is Python-interface enforcement, not a complete native sandbox.
The existing retained child guards remain additional layers; their complete joined
interaction has not yet been demonstrated inside a container.

Active guard/launcher/component selection: **71 passed**, no skip/xfail, 3.60 seconds,
JUnit retained. This includes the existing R1/R2/R5/R6 component nodes and new
`tests/control/test_offline_effect_guard.py` / `test_local_container_ci.py` nodes.
Earlier selection was 64 passed (4.86 seconds); it is component evidence only.
The shared guard's already-imported pytest plugin produces a rewrite warning; it
does not skip execution. A setup attempt without `PYTHONPATH=src` failed import;
a subsequent source snapshot caught a concurrent source edit and refused copying.
Neither setup failure is counted as behavioral evidence. Source was held stable
for the later passing candidate tests.

R3/R4 producer repair: `allocate_sealing_probe_root` allocates fresh qualification
evidence outside pilot/per-attempt cleanup-intent discovery. All retained callers
pass the explicit root into `sealing_primitives_preflight`; receipts label the role
and deny mutation authority. The actual intent consumer has no new exclusion or
weakened rejection. The original node
`tests/control/test_candidate_inputs.py::test_retained_sealing_probe_does_not_publish_container_mutation_authority`
now passes its original assertion, plus repeated invocation/evidence retention and
probe-copy forgery rejection.
`test_sealing_probe_failure_preserves_separate_evidence[RuntimeError]` and
`[KeyboardInterrupt]` pass with preserved partial probe state and untouched unrelated
evidence. All three passed in 17.75 seconds. A prior run passed the behavioral
assertions but failed an incorrectly assumed synthetic-info observation count; the
assertion now enforces exact allowed command shape and a finite 16-call ceiling.
No successful cleanup or freeze receipt was substituted. Full-controller cleanup
after separated sealing and the remaining R3 matrix are still unproven.

Outer CI, separate from experimental effects: dry plan reviewed before one bounded
`version --format` call to the explicit local Unix endpoint, with fresh empty client
configuration, no sudo or inherited Docker overrides, 15-second/64-KiB limits. The
call returned 1 in 0.166 seconds with 120 bytes: connection to the configured daemon
failed. The exact output is preserved; daemon absence is not inferred. No image
pull/build, container creation, resource removal, or runtime reconfiguration occurred.
The probe did not record wall-clock start/end timestamps, only elapsed time; do not
backfill them. The old Docker-info attempts and discarded output remain unchanged.

Dry plan observed 11,930,488,832 free bytes; preparation requires 8,589,934,592 retained
bytes plus a 4,294,967,296-byte budget (12,884,901,888 total). Preparation was not
admitted. No disk cleanup or budget enlargement was attempted. The owner must make
the already configured runtime accessible and provide sufficient existing-storage
headroom before required container validation can run. Safe code work remains
authorized; historical incident disposition is no longer a permission blocker.

CI files are a partial, unqualified implementation: pinned recipe/lock/backend inputs,
preflight and argument builder, exact-ID lifecycle with fake failure/cleanup tests,
and initial gate runner. The latter invokes existing `make ci-check`, never format.
Sanitized context/history export, complete result collection, actual permissions and
limits, per-revision environments/JUnit persistence through the retained comparator,
and real containment smoke remain unfinished. No CI image ID or Linux result exists.
Python 3.11.14 and uv 0.11.7 arm64 digests were read from official public registries;
Quarto 1.9.38 SHA/size were read from its official release API. Only public CI metadata
was acquired, not an image/tool archive or historical experimental artifact. The
current and exact base dependency lock both hash to
bec09cf0d326c56af9f717782eef9160579e7720dff701083570df9aa712b34b.
See `docs/harness/T09_LOCAL_CONTAINER_CI.md` for explicit proof limits.

Guarded state-capsule failed: `happy path stopped: host qualification failed:
downstream Git blob violates its role-specific size contract`. This is not passed
or excused by parity; no size/hash check was weakened. The full gate cycle, exact-base
parity, site/privacy completion, source ancestor and receipt rebind remain not run.
Focused Ruff and retained-host mypy passed. No skip/xfail/exclusion changes were made.

Publication-spending evidence: read-only API reports CI workflow 328946384 and
Publish notebook workflow 328946385 both disabled_manually. Repository run queries
for in_progress, queued, waiting, requested and pending each returned zero. This
satisfies the owner's workflow-pause evidence condition at this observation; recheck
before any eventual push. No administration or remote write occurred. Hosted CI
remains not run by owner instruction. Repair evidence is incomplete, so no commit,
push or PR update is made. All six findings remain unresolved; no V17, scientific
change, live authority, model/provider/browser effect or merge occurred.

Final focused rerun after guard/format changes: 71 component/guard/launcher nodes
passed in 3.60 seconds; all three sealing namespace nodes passed in 20.26 seconds.
Both JUnit files are retained. No active skip/xfail was added. Experimental dispatch
count in these guarded runs is zero; expected negative denials are preserved. The
standalone sticky-denial check intentionally produced an unexpected-violation record
and exit 90; that intercepted operation was not an external action. Newly authorized
outer CI metadata remains one separate failed call.

Guarded `make agent-check` completed with a failing target-selection result:
`selected-runtime target differs from goal/package state`. It did not pass. An
attempt to interrupt the already completed process found it absent and sent no
signal. No final exact-source gate is implied by these dirty-development orientation
checks. The final source remains dirty/unfrozen, and no receipt/document descendant
commit exists. The last sealing test's immutable private candidate binding is
729f353a5676aa759161d5385c50dc952e0ea6ec048b4b8768f2dde5e5c57599
with 334 explicitly inventoried members. Later ledger/launcher edits are not covered
by that candidate test binding. Its source is preserved separately at closeout.

Retained focused evidence: component/guard JUnit SHA-256
04c1ed9336bb232feac8c2fee5f3d2d7e21d213224bf312e8a4f4493b4c78c34;
sealing JUnit SHA-256
5f01381427129519a732cfecdd931b027fbafd3671c0c6ef5f3c565f629481ec;
new outer metadata result SHA-256
327b13c300483b514bc9b7923a67ec5ba0cd93103c52da4bba48822d2a279dca.
No experimental image action, provider/model request, browser launch, scientific
execution, V17 persistence, or merge occurred in this continuation. There was one
authorized outer metadata operation and public CI dependency-metadata research;
there is no global zero-effects claim.

Terminal state remains `t09_remote_execution_bridge_review_repair_blocked`: required
local runtime/preparation capacity unavailable; CI implementation/qualification,
joined transaction and all original acceptance matrices remain incomplete. The
acknowledged historical incident is not a renewed permission request. Independent
review and Joseph's separate merge authorization remain pending.

Preservation closeout: 62 explained dirty paths (the 48-path baseline plus the
CI/guard files, concise runbook, and existing sealing test caller update), empty
index. A fresh private no-follow snapshot contains 416 records / 14,646,120 bytes,
including the complete 334-member tested candidate source, current patch/source,
JUnit, denial journals, and outer preflight/control-gate failures. Inventory SHA-256
2906a716670184144eabaa9b01c78923164d46f8dc70dd2530108121a3c74bec.
This paragraph is an additive ledger descendant of that snapshot, not part of its
own source identity. Earlier snapshots were preserved. Final read-only local/remote/PR
head and base remain the original exact identities; PR remains open/draft/unmerged
with auto-merge disabled. Experiment/manifests and workflow-file diffs remain empty.
`git diff --check` passes. No final source/test ancestor, tested Linux head, or receipt
rebind exists. All background test/control subprocesses invoked here have completed.

### Source-gate diagnosis continuation: blockers are separate

Start verified: exact base/head/tree, branch and PR state unchanged; 62-path index
empty, scientific/manifests/workflow diffs empty. Reused and verified all 416 prior
snapshot records. Only the documented additive ledger closeout differed; a small
delta/patch inventory was preserved (SHA-256
649ca422f7b26b4ae8323a43905374e209a822ab6e2b9d25339b8aa590accc37).
No archive or old snapshot was duplicated. Operator-attested Astra/high, no metadata
introspection or delegation. The accepted incident disposition and verified workflow
pause remain in force. No daemon probe was repeated.

| Blocker | Observed status | Next permitted work |
|---|---|---|
| Configured daemon accessibility | Prior connection failure remains unresolved; Docker Desktop 4.87.0 installed, narrow settings read denied by OS; external runtime destination prepared | Owner performs supported disk-location change after checking current source/workloads; verify external backing and endpoint afterwards |
| Correctly measured storage | External APFS/Thunderbolt nonsecret bulk placement verified; startup now above 8 GiB headroom; active VM placement, guest capacity and build peak remain unqualified | Preserve separate filesystem budgets; no image/build/run admission yet |
| Downstream source gate | Explicit candidate propagation repaired and consumer regression passes; ordinary dirty-HEAD invocation still fails exact Git binding | Freeze actual implementation ancestor and perform authorized non-circular current-proof rebind after joined evidence |
| Selected target | Preserved before/after goal contexts reproduce a goal_record_sha256 mismatch; actual capsule consumer rejects stale selection and diagnostic names the field | Keep selected inputs stable during gates; historical receipts retain their own bound context; final agent-check pending |
| R1-R6 acceptance | Component evidence only; no complete joined transaction | Guarded bounded component work; joined run waits for container |
| Final validation | Pinned container/full/exact-base/static/privacy/site cycle not run | No host-native substitute or success receipts |


#### Source-gate repair and host-prerequisite diagnosis (2026-09-06)

The retained state-capsule command failed with ShadowValidationError at deterministic
host qualification. `DeterministicLowLevelEffects.qualify_host` selected current Git
HEAD and did not propagate its constructor's explicit candidate input to
`validate_git_bound_downstream_source`. In the ordinary dirty invocation, the latter
correctly rejected unequal Git/local sizes but conflated that comparison with the
finite cap in its error. The selected role is selector, repository path
`containers/sira-smoke/pragmatic/t09_remote_runner.py`, cap 4,194,304 bytes. This is
not an oversized source, missing object, scientific policy issue, or reason to raise
any limit.

| Source context | Bytes | Git blob / SHA-256 |
|---|---:|---|
| Exact base | 1,093,805 | blob baf94c442f96bd74d87f22150e69c9890c5a224a; SHA 6096c2c88ef80c07beeca577933a718f2c5e950bcb706be6becdf4983f7393cd |
| Reviewed HEAD | 1,163,386 | blob 30c4b70e7cf8c0685878e76f4318e2c3b3c0da60; SHA 39a6216acb02ebc86e1e1a07c4db5d4cb2562ba8bcda9acb29787f1941b7d6ef |
| Preserved dirty start | 1,209,036 | SHA 92f2b2a97a91a96d9a6f8a8bfb00ac6d89ae5e7d4eaebd44c2f9c183450f43e0 |
| This diagnostic repair | 1,209,254 | SHA 12119e388e95dc0c5592cbdb2d8e97f2c6b4018cb71e1b9539e984011fdc1437 |

The active node `tests/control/test_candidate_inputs.py::test_deterministic_qualification_propagates_explicit_candidate_source`
first failed at the intended behavioral assertion after real candidate generation
and package construction: the caller attempted Git inspection in a projected package
instead of carrying the explicit binding. Original red JUnit SHA
 dbeb3b8ddfda6446e3710c88a759499677d6dede297aa5fc0d6a4d2643595ccc
(1 failure, 84.989 seconds) is preserved. Qualification now retains the constructor's
source input, checks transfer identity, verifies the package before module loading,
and passes that same input to the existing downstream verifier. Default historical
selection has no fallback. The same node passes and rejects switched binding and
same-size altered source. This is deterministic qualification component evidence,
not a retained live qualification or joined transaction.

`test_downstream_correct_role_cap_still_rejects_before_git` (all four roles),
`test_downstream_wrong_role_remains_rejected`, and
`test_downstream_historical_size_mismatch_reports_source_drift` use the actual
consumer and preserve finite caps, role checks, and historical rejection. An interim
12-node run had an ImportError in a newly added negative-test assertion after the
positive consumer passed; that test import was corrected. It is preserved as a test
error, not additional behavioral characterization. The ordinary state-capsule gate
is NOT now claimed green: dirty bytes cannot bind to committed HEAD, and current
control receipts await the authorized ancestor/descendant process.

The agent-check target error is separate. Reconstructing selection from the preserved
pre-command goal and current goal yields the same V16 / PLAN-EXP0001-PILOT-V16 /
command package 377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b,
no explicit override, and only `goal_record_sha256` differs. Goal hashes are
827a82bb28f5b8d3c1c2cfe9770ec7a78e5731a98f578f47190c35009d031de9
and 1850a38370424e03054bb9963b8616f6209f7ae94d07fd5739fe1b433f1805b2.
The prior command overlapped a recorded goal edit; its retained error lacks a stack
or captured target object, so this is source-grounded reconstruction of the failure
mechanism, not a fabricated original execution trace. The diagnostic now lists
mismatched typed fields. `tests/control/test_state_capsule.py::test_state_capsule_rejects_goal_changed_since_target_selection`
proves rejection at the actual capsule consumer even for a semantically neutral goal
edit. Existing exact V16 and incompatible-selector tests pass. No resolver/default
or compatibility rule changed; no successor was created.

Historical root `control/receipts/packages/v16` remains bound to ancestor
 aeff713e46a75d513dd9ccbcb53586e3151fdfd6 / tree
 a6a650de2c7d2611bb042789e8a359293f5ccd83, its goal hash
3d0f48adc39e8d553f173f96d4585dbf53f31ea05617b328ae275f33ff6e3ea4,
and target semantic d5e0993a483fee7fe889c3dc293a753eb3cb84529851e6ce6e6f5db550807783.
The existing bound-target validator already uses that historical context. Those
receipts were not rewritten or labelled current. Final agent-check remains pending;
no failure is labelled inherited without exact-base evidence.

Runtime diagnosis used filesystem metadata and the already retained one outer
version result, without another daemon probe. The installed client resolves to the
existing Docker Desktop application. DOCKER_HOST/DOCKER_CONTEXT are absent. The
explicit approved Unix endpoint equals the endpoint in the recorded command; its
socket exists and is readable/writable at the filesystem permission layer. The
retained exit-1 result says it cannot connect. Stopped daemon, inaccessible listener,
and another internal runtime fault cannot be distinguished from this evidence.
The operator must inspect/restore accessibility of that already configured runtime;
no alternate endpoint, start/restart, privilege, installation or configuration change
was attempted. The new fake preflight test verifies exact --host propagation, fresh
empty client configuration and separation of usable metadata from unqualified storage.

Storage observation: 2026-09-06T15:10:48.407074Z; source and host scratch share one
filesystem. Available bytes were 6,328,016,896 (6.328016896 decimal GB; about 5.893 GiB).
The retained preflight plan previously recorded 11,923,800,064 bytes; the ledger's
11,930,488,832 is another observation, not the same exact measurement. The old record
has elapsed duration but no exact wall observation timestamp. Do not backfill one.
The visible default Docker sparse backing file is on the same host filesystem:
logical 245,106,737,152 bytes, allocated 5,698,007,040 bytes. Its active use and Linux
internal available bytes remain unverified; logical capacity is not available space.

| Working-peak item | Exact known bytes / disposition | Filesystem and concurrency |
|---|---|---|
| Public pinned Python/uv compressed layers | 369,183,029 + 23,707,331 | Prospective daemon backing; metadata only, layers not downloaded |
| Pinned Quarto archive | 133,976,767 | Prospective preparation filesystem; extraction peak unknown |
| Total initial compressed inputs | 526,867,127; plus image config metadata 7,694 | Not an unpacked-image/build requirement |
| Unpacked layers, dependency downloads/cache, build transients | Unknown; no reuse credit established | Actual daemon backing and Linux free space unverified |
| Source/history export | Required incremental pack/input size not yet measured | Host input then isolated Linux workspace; existing repo/snapshots already allocated, no duplicate snapshot cost |
| Concurrent run workspace | 4,294,967,296 maximum tmpfs, plus 67,108,864 /tmp | RAM; no extra swap; not double-counted as host disk |
| Exported results and captured console | 1,073,741,824 + 268,435,456 maxima | Separate host outputs under current partial runner; not silently omitted |
| Retained host headroom | 8,589,934,592 | Same host filesystem; unchanged |
| Existing preparation budget | 4,294,967,296 | Declared ceiling, not measured unpacked peak |

Preparation and test workspace execution are sequential; retained dependency layers
persist across them. A valid same-filesystem peak must include the greater of the
preparation transient peak and retained-image + source-input + run-output peak,
plus the unchanged headroom. Unknown terms prevent admission. The prior formula
`free >= 8,589,934,592 + 4,294,967,296` now reports only budget headroom, never
qualified preparation. Three integer-boundary tests prove even ample host space
cannot certify unmeasured backing/image requirements. The observed deficit to the
floor alone is 2,261,917,696 bytes; to the declared 12,884,901,888-byte threshold it
is 6,556,884,992 bytes. Neither is a sufficient cleanup prescription. Operator action
requires sufficient host AND verified backing-filesystem capacity after the remaining
peak is measured; no file/cache/evidence/runtime deletion or relocation was performed.

No new daemon operation, image preparation, container launch, joined run or full gate
occurred. Public registry manifest metadata inspection is distinct from experimental
operations (zero in these guarded tests), and the old two Docker attempts retain
unknown daemon contact. Workflow IDs 328946384 / 328946385 remain covered by the
retained verified pause; final publication must recheck drift. Hosted CI not run by
owner instruction. All R1-R6 remain open; fixture, terminal, transport and writer
components are not a campaign proof. Local CI implementation and final Linux gate,
source ancestor/rebind, publication and independent review remain pending.


Final guarded source-gate/component selection: 49 passed, 0 failed/errors/skips in
10.473 seconds, JUnit SHA-256
dd9bb22f2d3a26278118d63545355567353ea8fbc5e381d25453f7537a246c36.
The tested 334-member dirty candidate binding is
bd360b8f19b2a39015ce21afe29637a6a34ca271e328b6fbea936a27d7ca6871.
Its qualification fixture remains 2,034 bytes / 15 members / SHA
284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb.
No joined/environment qualification was run. Candidate inputs and tested source were
held stable throughout this run; subsequent ledger/incident evidence additions are
identified as additive descendants, not part of that candidate binding. Focused
Ruff/format checks and three-source mypy pass. Incident schema/consistency validation
passes with regressions explicitly not executed by that validator. Its `complete`
field means document validity, not finding closure; this incident remains open.
Guard journals for the new passing selections contain no unexpected violations.
The final full/static/privacy/site/exact-base container cycle remains NOT RUN.

The original red JUnit and implementation baseline are retained. Pytest's temporary
red candidate directory is no longer available after its ordinary retention cleanup;
its original failure trace is not replaced with passing evidence or represented as
an intact raw directory. The latest tested candidate is preserved incrementally
against the earlier retained candidate so it does not depend on pytest retention.
Earlier seven-/seventeen-/48-/62-path preservation snapshots were not moved or
replaced. Two newly dirty paths in this continuation are the narrowly changed target
diagnostic and its existing state-capsule test file; total is now 64 explained paths.
No staged files, checkpoint commit, source ancestor, receipt rebind, push or PR update.

Final read-only verification: local/remote/PR head remains a98b4b8... and its original
tree; the PR destination is phase-1/sira-pilot-autonomous-r2, confirmed at f56dfc2...
with the original base tree. Original checkout remains clean. PR remains open, draft,
unmerged, auto-merge disabled. Both expensive workflows still report disabled_manually;
the earlier verified zero nonterminal run counts remain historical pause evidence,
not a hosted test result. No hosted dispatch or remote mutation occurred. Frozen
experiment/manifests/workflow diffs remain empty. No V17/live/scientific authority,
experimental effect, paid provider/model spend, or merge was added. One prior outer
metadata failure remains the only authorized daemon call in this repair history;
this source-gate continuation added zero daemon/image/container calls. Independent
review and explicit owner merge authorization remain required.


### External nonsecret bulk placement — 2026-09-06 owner continuation

Operator-attested Astra/high; no metadata introspection, model switch or delegation.
The exact 64-path dirty start matched the prior inventory byte-for-byte. Verified
all 416 records in the earlier preservation snapshot and all 28 incremental records;
original 49-test JUnit hash still matches. Seven-/seventeen-/48-/62-path predecessors
and the latest incremental snapshot remain present, with no symlink replacement.
The missing original ephemeral red pytest directory remains missing; its retained
red JUnit is not described as an intact raw directory. Git local/remote/PR head and
base remain the supplied exact identities; PR open/draft/unmerged, auto-merge off,
index empty. Frozen experiment/manifests and historical archive pins are unchanged.

The worker is the Mac mini, Apple M4. The owner's named mount is a real external
APFS volume, observed over Thunderbolt, distinct from the startup APFS container.
UUID/container/device/root identities and topology are retained in ignored local
control records; no display-name lookup, suffixed-path guess, or directory created
on the startup filesystem stands in for a mount. The established project root had
only historical t07/t09 children before this continuation; neither was changed.
The volume is writable and unlocked with ownership disabled. Encryption does not
make apparent modes/owner IDs on this mount proof of exclusive confidentiality.
Only nonsecret source/test data and appropriate evidence are placed there.

New compatible role directories were created after mount verification. A fresh
source-preservation child contains exactly the 64 dirty source/test/document files
plus staged/unstaged patch (4,749,027 bytes). Every destination was reread and
SHA-verified; inventory SHA
3181415d6811fbf2358f68e58ea062afbab4c84d879abb05872952c313724b70.
This reconstructs the dirty source from its named committed parent without copying
historical archives or raw private authority, credentials, runtime ownership dumps,
or earlier snapshot trees. Originals were retained. Raw prior JUnit/topology logs
remain at their existing locations; passing report projections omit host identity.

`ProjectStorage` in the existing outer launcher reuses the retained no-follow path
primitive and external retention formula; it does not execute an old T07 plan.
The ignored `.tools/local-ci-storage.json` pins the observed destination. Missing
configuration, absent volume, changed device/root/volume/container identity, wrong
filesystem/lock/ownership state, symlinks and out-of-root paths fail closed.
New directory creation uses checked parent descriptors. The guarded host entrypoint
selects fresh external scratch and results before exec. Its children inherit exact
temporary/cache paths even with replaced environments. The existing audit guard now
rejects Python writes outside the bound bulk root; mount loss cannot trigger internal
fallback or be caught and reported as a successful child. This remains a Python
interface guard, not a native-code sandbox or a replacement for Linux ownership.

| Actual writer/role | Placement and observation | Remaining proof boundary |
|---|---|---|
| Dirty editing checkout/common Git store | Retained internally, allocated 291,753,984 / 5,709,824 bytes at measurement | Deliberate owner exception; no Git-aware cutover attempted |
| New preservation/patches | Verified external `evidence/pr15/` children | No secret or private authority migration; prior evidence retained internally |
| Source/history exports, disposable checkouts/build contexts | External `ci/inputs/` and `workspaces/` roles selected | Full source/history export/build wiring still unqualified |
| Candidate/extraction/Python/pytest scratch | Fresh external `tmp/p15-*`, explicit pytest base temp/cache | Ownership-sensitive candidate/transaction tests wait for Linux; hardcoded internal host writes are denied |
| uv/Python/pip/XDG/Deno/Ruff/mypy caches | Explicit external `cache/` children; future venv under fresh run root | uv 0.11.7 `cache dir` / `python dir` and Python 3.11.14 `tempfile.gettempdir` observed exact destinations; no download/install |
| Logs/JUnit/coverage/failure guard evidence | Fresh external `ci/results/`; source evidence under `evidence/pr15/` | No public private topology; bounded outputs remain required |
| Quarto/site/build environment | Explicit Linux `/work` caches/scratch/disposable checkout, `/results` log/export | Quarto absent from inspected host PATH/project tool paths; rendering not executed or certified |
| Runtime image layers/build cache/container writable storage | Fresh external runtime-data destination prepared; not active | OS denied settings-store read; guest space/active backing unknown; owner supported relocation required |

The candidate source closure explicitly adds `scripts/ci/local_container.py` as the
new import dependency of its already listed guarded launcher. The retained storage
module was already present. This changes the allowed closure from 334 to 335 members;
no historical expected source/archive hash or scientific policy is rewritten. No new
candidate success receipt was generated from this untested closure. The earlier
334-member candidate result remains bound to its own exact historical dirty source.

Storage observations at 17:02:16.701318Z:

| Filesystem | Available bytes | Retained headroom | New allocation / uncertainty |
|---|---:|---:|---|
| Startup Data | 20,201,062,400 | 8,589,934,592 | No new project bulk budget charged here; small ignored local control records only, bounded below 1 MiB; deficit 0 |
| External shared APFS container | 734,155,038,720 | 200,048,192,717 | 534,106,846,003 bytes above floor; measured preservation already allocated; CI preparation still has its 4,294,967,296-byte ceiling |
| Linux guest/runtime backing | Unknown | Must independently satisfy existing limits | No runtime/guest measurement, image migration or image preparation here |

The external headroom is the existing max(150 GiB, ceil(20% capacity)) policy using
observed capacity 1,000,240,963,584 bytes. Available space uses the lesser of APFS
container free and filesystem allocatable bytes, never misleading per-volume zero
FreeSpace, summed sibling-volume capacity, or free space from the startup disk.
The old internal 12,884,901,888-byte preparation threshold is not charged after
external placement. The startup headroom policy itself is unchanged.

Public compressed dependency inputs remain the previously observed 526,867,127
bytes plus config metadata; unpacked/build peak is still unqualified. Run exports
retain 1,073,741,824-byte results and 268,435,456-byte console ceilings. Linux scratch
retains the 4 GiB plus 64 MiB tmpfs limits within the existing 8 GiB RAM/no-additional-
swap boundary. Preparation and tests are sequential; reusable layers persist.
Existing source, snapshots and caches are not charged again as new copies. Neither
external surplus nor hypothetical sparse-file savings establishes build admission.
The observed default internal Docker.raw remains logical 245,106,737,152 / allocated
5,698,007,040 bytes, not verified as the active disk. The actual migration source,
transient peak and guest capacity remain unknown until supported runtime inspection.

Docker Desktop 4.87.0 / build 236836 is established from installed application
metadata, not inferred from the socket. The narrow settings-store read failed with
OS PermissionError; no privilege workaround or complete settings dump was used.
Owner action: in that product's Settings → Resources → Advanced → Disk image
location, inspect the current source and other workloads, Browse to the fresh
project runtime-data destination, and Apply through the supported mechanism.
Do not drag/symlink Docker.raw or replace an old image. The worker did not start,
restart, migrate or reconfigure the runtime. No new daemon probe was warranted
before placement can be verified; the prior connection error remains unresolved.
[Docker's supported relocation](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/macfaqs/)
requires this product operation; the source setting could not be verified here.

Focused external run: 34 passed, zero failures/errors/skips, 0.195 seconds of pytest
execution (mount checks occur in the launcher before pytest). Raw JUnit SHA
528fd12be63db0f6249c5e6b67075edde3ac0b2b9cfc913158a8ae5ba8a60b87.
Active nodes are in `tests/control/test_local_container_ci.py` and
`tests/control/test_offline_effect_guard.py`, including absent/plain mount,
changed volume/root, path spaces, wrong/symlink destination, independent filesystem
budget, child environment inheritance, pre-creation internal temp denial and sticky
mount-loss exit. Diskutil/filesystem observations for fake-volume nodes are explicit
leaf inputs, with no real daemon/process success stubs. One named isolated negative
child deliberately catches simulated mount loss and exits 90; that is expected
denial evidence, not a real unmount or environmental escape. No new skips, xfails,
exclusions or weakened production ownership checks. Focused Ruff/format checks pass.

| Storage acceptance item | Status |
|---|---|
| Current volume/mount identity and noowners classification | met for nonsecret placement |
| Incremental source preservation and retained originals | met |
| Default host bulk paths, child propagation and fail-closed tests | met at tested Python/launcher seams; native tool/OS containment not claimed |
| Runtime external backing, guest capacity and complete build peak | blocked on supported owner action and subsequent observation |
| R1-R6 joined transaction/final local-container gate | incomplete; not run in this continuation |

No R1-R6 finding is closed by storage tests. Earlier 49-component evidence is retained,
not rerun or relabelled as coverage of the changed storage guard. Ownership-sensitive
host tests and the joined/full suite were not run on the noowners bind mount.
Historical archive/image replay remains not run; working qualification fixture
identity is unchanged. Hosted CI remains not run by owner instruction; verified
workflow pause remains the spending posture, and publication still awaits complete
implementation/local evidence. No implementation ancestor, receipt rebind, commit,
push, PR update, scientific authority, V17, model/provider/browser/experimental Docker
action or merge was added. Historical Docker attempts and unknown daemon contact
remain explicit; this continuation made zero new Docker daemon calls, pulls/builds
or container launches. Read-only OS/volume/tool observations and nonsecret file copies
are separate real local operations. Independent exact-head review remains pending.


### Owner-authorized Docker UI relocation attempt — 2026-09-06

Operator-attested Astra/high; no delegation or model metadata inspection. After
explicit owner confirmation permitting interruption of the observed unrelated
PostgreSQL workload, Computer Use invoked Docker Desktop 4.87.0 Settings →
Resources → Advanced → Browse → Apply & restart → Yes, move it exactly once.
The existing external volume identity was reverified, the prepared destination
was empty, and the product selected its own DockerDesktop child.

The backend logged a cross-drive copy start at 18:27:19 UTC and failure at
18:32:19 UTC: the copy process exited with signal 9 / WaitStatus 9, and
"New setting not applied". The approximately five-minute duration does not prove
the killer or a timeout cause. The external partial disk disappeared; the original
disk remained. The UI reported "Failed to apply settings". After clearing only the
unapplied form change, the original internal disk location and disabled Apply
button were observed. The engine and the same preexisting PostgreSQL container
were running again; application/data-level health was not exercised. No blind
retry, manual disk copy/deletion, software update, privilege change or CI build
was performed. The failed operation is authorized outer local infrastructure
activity, not a zero-Docker-effects claim or experimental execution. The earlier
Docker incident and its unknown daemon-contact fact remain unchanged.

Sanitized observation retained under the existing external evidence/pr15 role,
`docker-relocation-20260906/observation.json`, SHA-256
`eed4093a35f907276526a39b7e30af552749be18298c497ec605ae672488b387`. All 64 prior source files matched the retained storage-placement
inventory before this additive ledger edit; previous snapshots remain intact.
Local HEAD/tree and PR head/base/draft/open/unmerged/no-auto-merge identities were
reverified unchanged. No source repair test was rerun for this UI operation.
External runtime backing remains blocked by the observed product relocation
failure. R1-R6, joined evidence and final local-container validation remain
incomplete; no receipt ancestor, commit, push, hosted CI, scientific authority,
V17 or merge was created.


### Bounded read-only relocation diagnosis — 2026-09-06

Disposition: signal sender/cause not recoverable from the retained evidence examined.
The fixed 18:25:00–18:36:30 UTC window preserves Docker backend launch of cp PID
99400 and signal-9 failure after exactly 300.141328 seconds. Idle reduction just
before failure is correlation, not proof of sender or deadline. The separate
macOS cp disk-write report belongs to PID 98835 before this attempt and records
no action. The refined nonprivileged unified-log query returned no copy-specific
attribution; coverage, initial output-selection/display truncations, unrelated
records and metadata-command limitation are documented explicitly. No raw logs or
live VM content were copied, and no daemon/container query was needed.

Current metadata: Docker 4.87.0 (236836), macOS 26.5.1 (25F80), arm64. Source
245,106,737,152 logical / 5,697,826,816 allocated bytes remains internal APFS;
external APFS target is empty. Observed at 19:23:21 UTC: external available
710,983,970,816 bytes, internal 47,945,019,392 bytes. These are current metadata,
not failure-time capacity or copy-throughput evidence. Mount identity reverified.

Issue docker/desktop-feedback#484 remains open with one non-maintainer follow-up
and similar 4.79.0/4.85.0 reports. No explicit matching fix found in current
release notes; unrelated Resource Saver fixes are not promoted into a remedy.
Backup status unverified; retained PostgreSQL running state does not prove
integrity or recoverability. Next proposed action is review/submission of the
sanitized Docker support draft, requiring explicit transmission permission; no
submission or remedy executed. Any later recovery needs database-safe backup/
health verification and separately approved maintenance, storage and rollback.

Evidence: existing external incident root, `diagnosis-20260906/inventory.json`,
SHA-256 `9f4666fbe55e095ca466675454b3b589ff60f9b5cdfa7cb22e9e4a83b021a7b7`; payload 14637 bytes, below 16 MiB.
All 64 existing dirty paths reconciled, index empty, original observation hash
unchanged. Only this additive ledger entry changes tracked content. Local/remote/
PR head and tree unchanged; PR open/draft/unmerged with auto-merge disabled.
No source repair, tests, CI, commit/push, runtime mutation, experimental effects,
V17 or merge. Hosted CI remains not run; R1-R6 and required local-container gate
remain incomplete. Earlier Docker incident uncertainty is preserved.


### Isolated GIC Colima continuation — 2026-09-06

Operator-attested Astra/high; no delegation or model metadata introspection. The
owner now permits exactly the GIC profile `gic-pr15-ci`, independently of shared
Desktop maintenance. No shared Desktop, PostgreSQL, or Biblos access is permitted.
64 dirty paths and empty index reconciled: 63 source paths match the preserved
storage-placement inventory; the ledger contains the explained additive diagnosis.
A reconstructable external increment retains the ledger and both diffs (1,042,416
bytes), inventory SHA-256 `7a6a739ed28fc2739312ce3da733b5da4dac8ef666315e1a39d5e1afe2a5b678`.
Prior preservation copies are retained. Committed HEAD/tree and PR remain unchanged.

| Historical T07 restriction | Applicability to this owner-authorized CI lane |
| --- | --- |
| VM private-key confidentiality and ownership | Still required. One AES-256 encrypted, ownership-enabled APFS sparsebundle; unlock material only in protected internal control storage. No plaintext VM keys on the outer noowners volume. |
| Complete vendor-attested preboot executable manifest | Historical rejection unchanged. This lane permits checksum-bound upstream bootstrap plus measured post-start runtime identities; this is limited assurance, not T07 qualification. |
| Exposure, provenance, resources and concrete security notices | Still required: no host mounts/personal keys/remote API/default-profile fallback; bounded native VZ runtime and immutable CI image. Lima GHSA-2j9v-p4xj-cjw2 affects QEMU through 2.1.2, is fixed in 2.1.3 and does not affect VZ; selected candidate Lima 2.2.0 remains subject to actual binary and startup verification. |

A private pre-allocation plan binds the verified external volume and budgets a
64 GiB sparse maximum, with 20 GiB root and 32 GiB data disks contained within it,
2 GiB bootstrap/tool cache, 1 GiB source inputs, 1 GiB exported results and 8 GiB
remaining protected capacity. Guest image/build/workspace costs are subdivisions
of the 32 GiB data disk, not additional outer allocations. External retained
headroom remains 200,048,192,717 bytes; internal OS headroom remains 8 GiB.
The control-file exception is bounded to 64 KiB; no new internal bulk cache.
Observed memory-pressure availability was 55%; initial VM remains 2 CPU/6 GiB.
Profile creation, measured isolation, joined transaction and final gate remain
pending. This entry grants no finding closure, historical replay, scientific
authority, hosted CI, publication or merge.


#### GIC runtime preparation and first contained candidate attempts

The protected, ownership-enabled AES-256 APFS image was created under the verified
external project root; its logical ceiling is 64 GiB. Unlock material remains only
in a fresh protected internal control directory. VM keys and runtime homes are
inside that encrypted filesystem. Neither the outer noowners mount nor a plain
unencrypted image is asserted to protect credentials. No shared Desktop, Lab
PostgreSQL, old disk image, or Biblos runtime was contacted or modified.

Verified public inputs: Colima 0.10.3 binary SHA-256
`980ad8bf61a4ca370243f4cb41401a61276dcd2c2502bee7b9b86f9250169f34`;
Lima 2.2.0 archive `bbdef91774885a0d05f7b048c4eb89ae2bcf3a0c252ae7ca7934e63df76d93c3`;
Colima's embedded-pinned ARM64 Docker bootstrap
`1fc0354f4f99734ce3886628cc7af8b0437c1a1d391b126bd09cba0df35ee53f`.
Published checksums were verified before use. The Lima documentation-only symlink
was excluded from extraction after an initial strict-file rejection; executable
bytes were not rewritten. Docker CLI 29.7.2 and Buildx 0.36.1-desktop.1 were copied
read-only from the installed application, without contacting its daemon.

The GIC VM is native ARM64/VZ, 2 CPUs, 6 GiB configured RAM, 20 GiB root and
32 GiB data disk. Measured Engine 29.5.2, containerd 2.2.4, runc 1.3.5,
BuildKit 0.30.0, Ubuntu 24.04.4/kernel 6.8.0-117. Guest image/container storage is
on the encrypted externally backed data disk; no host filesystem mounts exist.
Personal public-key import and agent forwarding are disabled. Measured identities
are post-start observations, not the rejected historical T07 preboot attestation.

Two startup policy gaps were retained and remediated, without erasing their
observations. First, standard bootstrap apt timers were enabled. The GIC profile
was stopped and its supported provisioning hook now masks both timers and services.
Service execution was not observed. A subsequent timer timestamp differed from the
initial blank observation; this is not evidence that no timer ever triggered.
Second, Colima's `portForwarder: none` rule omitted Lima 2.2's explicit wildcard
boolean. After restart, two host DNS forwarding attempts failed with address-in-use
errors. No successful listener was observed; zero forwarding attempts cannot be
claimed. The GIC VM was stopped again. A documented GIC-only Lima override now
prepends the explicit wildcard deny rule (`guestIPMustBeZero: false`); actual
merged configuration was validated before the third start. Its startup log contains
no TCP forwarding attempt. Private evidence preserves all three start logs and
the two stopped-state records. This is separate from the earlier Desktop Docker/
sudo incident, whose daemon-contact uncertainty remains unresolved.

Official security notices were checked against observed versions and configuration.
Lima's QEMU issue does not affect the selected VZ backend; Docker's cited copy
issues are fixed before Engine 29.5.2. The cited runc advisory expressly excludes
Docker exploitability. containerd 2.2.4 retains the malicious-image DoS exposure;
this exclusive lane uses only pinned trusted CI images and disallows untrusted
imports, following the advisory's stated workaround. CRI is observed disabled.
This is a scoped applicability assessment, not a vulnerability-free claim.

The sanitized ten-file CI context (437,484 bytes) built successfully in 66 seconds.
Measured guest data growth was 3,610,009,600 bytes, below the declared 4 GiB
preparation increment. The resulting Linux arm64 image is
`sha256:2c9c64bb3571a036c743f50c7a6f3cf2edfcd7ab46ba2d843a1321d4982653be`.
Python 3.11.14, uv 0.11.7 and Quarto 1.9.38 checks passed during preparation.
Public dependency acquisition/build and GIC VM management are authorized real
infrastructure effects; experimental provider/model/browser/container effects
remain forbidden. No global all-effects-zero claim applies.

Containment transaction `gic-pr15-ci-3b7be950183e3bdd` passed the actual non-root,
read-only-input/root, no-engine/credential, dropped-capability/no-new-privileges,
network-none inspection and safe negative checks. Three named guard denials were
expected; unexpected denials were zero. Real local Python child and Unix IPC ran.
Both owned containers and all three guest volumes were removed with exact ownership
verification. Earlier smoke setup failures (CLI absence-text parsing and observed
`CAP_CHOWN` spelling) remain preserved; the originally unresolved removal was later
proved absent and its exact volumes removed. No experimental success was fabricated.
51 focused launcher tests passed before the later development-runner changes;
those tests do not validate the subsequently changed runner.

The exact 435-commit history bundle eventually exported and verified (5,077,995
bytes; SHA-256 `ede3a8ca7257e8081efb4124dadeb4f935448ba3634aa221133b1751e6e5f522`).
An earlier 60-second export timeout and an incomplete object-copy metadata check
remain preserved. A fresh read of the implicated loose object verified its actual
Git object identity; the earlier physical metadata change's cause is unknown.
No shallow archive, missing-object fabrication, or original Git-store mutation was
used. The successful export took 352.915 seconds.

The first two contained candidate attempts reached the retained regression consumer
and failed its deterministic semantic equality assertion. They are not completed
joined transactions. Exact active node:
`tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[transaction]`.
Input manifests `48b00c129c158084fa460a5542c633814a1e4d13313759152c80e9fdd5af7e2d`
and `a82b571f86fcdd2b17fa107dc8bd7283d0354d43ad6d7e953f61d72e394791ef`
bind 65 dirty paths separately from the unchanged committed HEAD. Bounded diagnostic
tracing in the second attempt showed NLTK's missing writable download directory,
followed by its partially initialized import; the two exception types caused the
semantic-hash difference. The test child now declares its own HOME/NLTK cache under
the bound fixture root, while all download/effect guards remain active. No production
evaluator identity, scientific scoring, or equality assertion was relaxed. These
failures are environment characterization, not R1–R6 closure.


#### Contained continuation: qualification, sealing selection, and archive continuity

All results below are guarded Linux arm64 dirty-candidate evidence, not evidence
for the unchanged committed HEAD and not historical V16 qualification. The same
pinned dependency image and exact history bundle above were used. Each attempt
materialized its own sealed dirty source input in private Linux volumes. No
host-native joined/full-suite substitute was run.

| Input revision | Observed stopping point | Narrow source repair / evidence disposition |
| --- | --- | --- |
| 4 | Local launcher resolved through a uv symlink to a root-owned interpreter | Inner runner creates the invoking user's copied stdlib venv before frozen offline sync; real ownership checks remain active. |
| 5 | Candidate capsule omitted incident-referenced active tests | Explicit candidate closure adds 17 existing validation inputs; scientific/policy projection is unchanged. |
| 6 | Preflight found a rebound temporary credential target | Carrier reads the exact durable cleanup journal target, verifies kind/ownership hash/path, and does not rewrite that record. |
| 7 | Qualification evaluator child lacked declared writable HOME/cache | Every isolated phase child now has its own bound fixture HOME/NLTK/TMP paths. No download or evaluator-success substitution. |
| 8 | Qualification validator omitted consumed inputs; cleanup reapplied historical scan roots | Bind/recheck local finalizer qualification and offline regression inputs; propagate the candidate environment's exact core-scan roots into cleanup. Fake canary is outside artifact evidence, at the durable recorded target. Wrong-root and changed-byte rejection remain active. |
| 9 | Freeze lacked the explicit qualification archive dependency | Propagate that typed dependency to freeze/condition entry. Selection: 61 passed, 2 failed; one failure was a rejection-test regex disagreement, not an accepted mutation. |
| 10 | Freeze's stable sealing-result reference was absent after probe namespace separation | Publish only the actual validated qualification receipt at its existing selected-result location; synthetic commands/raw trees stay in the dedicated probe namespace. Selection: 62 passed, 1 failed. |
| 11 | Freeze selected a different phase's archive location; partial freeze cleanup remained unresolved | Selection: 63 passed, 1 failed. Original sealing namespace regression passes; cleanup did not manufacture missing freeze evidence or claim clean. |

The receipt selector is `publish_sealing_probe_selection` in the retained runner.
It verifies the actual probe root, source receipt equality, qualification role and
absence of mutation authority before exclusive publication of the selected result.
`test_retained_sealing_probe_does_not_publish_container_mutation_authority` remains
active, including repeat invocation and forged mutation-record rejection. It is
component evidence, not full R3 closure.

Revision 12 changes archive continuity: qualification creates one transaction-owned
fixture; later phases reopen that same source through
`load_deterministic_qualification_archive`. Expected bytes/members still derive
from the tracked generator. Missing, mutated or symlinked source is rejected rather
than regenerated. The archive remains 2,034 bytes / 15 members / SHA-256
`284c3c37b9be5c9cead25499252c8aeec908157da6a99d1d79cc312b83d20acb`.
The generator source identity changes explicitly; archive identity does not.
Its new negative node is
`tests/control/test_qualification_fixture.py::test_later_phase_reopens_exact_archive_without_rebuilding`.
Revision 12 source inventory digest:
`28958d9c29881dbd43d0223f5c2a44142a95e4133bb28eb430a1739cce57be4a`.
Its result remains pending in this entry; subsequent evidence is appended below.

The GIC-only outer metadata command initially placed the profile name after `ssh`;
Colima rejected selection without executing the requested guest command. Exact
checks found no default-profile state created. The corrected global
`--profile gic-pr15-ci` selection returned the intended guest storage observation.
`colima_argv` now enforces that ordering for start/stop/status/ssh, with four active
regressions. This was an outer selection failure, not proof of daemon unavailability.
A subsequent host Python invocation failed at import (`yaml` unavailable) before
any daemon call; the existing project interpreter then ran the launcher. Neither
setup error is a behavioral regression or an experimental effect.

R1/R2/R5 retain their earlier component progress. R3/R4 remain partial across the
retained qualification/freezing/cleanup chain. R6 writer-role coverage is incomplete.
The adapter's runtime, finalizer, evaluator and failure-export operations still
raise explicit unimplemented errors; no successful output was fabricated for them.
No four-condition campaign, final gate, immutable implementation ancestor, receipt
rebind, commit, push, independent review, or repair-complete claim exists.


#### Latest contained result and exact remaining work

Input revision 12: **67 passed, 1 failed, 0 skipped** in 84.328 seconds.
Archive continuity and all four reopen negatives passed; freeze's materialization
loader still demanded the historical method label for the explicitly bound offline
image. The loader now selects the matching method only after validating the typed
offline environment; the normal historical label/hash checks are unchanged.

Input revision 13 (`1a2dbeacac66e0c9d853f5ebcb6f4adcb3a95eeb8bdbee00df394375fb2c90ce`):
**67 passed, 1 failed, 0 skipped** in 86.710 seconds. Comparing every expected
projection field with the actual retained manifest found exactly one disagreement:
`runtime_contract_sha256`. The shared controller used provider-profile digest
`80962bb30ed6aa879e4c1e8c7d7e25a119375c28e0897cd02e3ff1c0aa15b41a`;
the candidate runtime-identity file was
`6cfac368ed1c0f6fa944aa735572d7e98e3ce25f8fe2b15bac6fc945b2b3e3ae`.
Production now uses the retained `contract_paths(...)["runtime"]` resolver and
rehashes that exact input. Full projection equality remains active. The cleanup
manifest loader now receives the same explicit source/archive/environment inputs;
ordinary invocation still rejects candidate input.

Input revision 14 (`521e9e9bcb8529058ed776dac028b620f024afbc3f3bf0084313b5a68130c04c`):
**71 passed, 1 failed, 0 skipped** in 92.690 seconds. Full freeze validation passed,
then the fixture clock lacked the retained handoff sleep. Actual retained cleanup
and terminal provider verification passed despite the phase failure. The fixture
now models one bounded host-freeze wait (at most 120 seconds), records it in the
causal phase trace and advances the controller's existing environmental clock.
No task execution or provider retry was introduced.

Latest input revision 15:
`bd81ef63d32c4c749529af0e0d6c5178b6963ee64a0ad2228f68cc925eb939e7`.
Transaction **`gic-pr15-ci-bd1dceb266802576`**: **129 passed, 1 failed,
0 errors, 0 skipped** in **97.363 seconds**. This includes the active R1/R2/R5
component modules, the R6 event-writer/allowance regressions, bridge tests, launcher
checks, archive reopen negatives and original sealing namespace node. It is not a
full suite or parity result. The sole failing node remains
`tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[transaction]`.

Its actual causal prefix is controller local assembly and transfer verification,
retained host preflight, retained qualification (archive materialization, canary,
runtime/dependency/core/browser/sealing/evaluator fixture consumers), retained full
freeze validation/publication, one shared condition reservation/entry, and retained
cleanup plus terminal provider verification. `host-freeze` returned zero. The
condition operation in `RetainedCandidateEffects.execute_condition` still raises;
its failure-preservation/export operations are also unimplemented. The observed
stop is **condition-execution: consumed condition failure could not be sealed and
exported**. No real runtime client ran in this joined transaction, no genuine
answer reached its finalizer/evaluator, and no Task A checkpoint ran. The full
four-condition campaign, all required failure matrices, R6 writer roles, R4
conformance/viability receipts, final source ancestor and complete local gate remain
unfinished. No further fixture-input permission is implied to be needed merely
because these in-scope implementations remain unfinished.

The inner runner now emits an explicitly failed gate receipt and verifies source
integrity after a failing test command. Four active
`test_inner_gate_checks_source_and_retains_failed_outcome` cases exercise real
local subprocess success/failure with and without changed source. The latest
contained gate records exit 1 and `source_unchanged: true`; both failures and source
mutation remain failures. This does not qualify the final runner/image or prove
all final export/setup/interruption cases.

Failure preservation reached a 128 MiB per-archive cap while copying repeated
source trees from passing component fixtures. The capped archive (134,217,615
stored bytes) remains retained and explicitly incomplete. No cap was enlarged.
Complete failed-node workspaces and guard journals were subsequently exported as
separate bounded archives (about 44 MiB each), with complete JUnit for all nodes;
passing fixture workspaces are reproducible from the sealed input inventory.
Every implicated exact-owned container and volume was then verified absent.
This outer cleanup does not relabel any earlier unresolved tested cleanup as clean.
The latest shared guard journal contains zero unexpected denial records.

Targeted Ruff for the touched launcher/runner/retained-source/test modules and
`git diff --check` passed. No full type/static/privacy/site cycle, raw full suite,
exact-base parity, native-only rerun, final container gate, success receipt rebind,
implementation commit, push, or independent approval is claimed. The active source
remains an explained 65-path dirty delta with an empty index. Frozen experiment and
manifest paths have no Git diff; no actual successor execution package or live
campaign was created. Historical replay and real experimental image qualification
remain not run.

Read-only GitHub verification on 2026-09-07 confirms unchanged local/PR head and
base, PR open/draft/unmerged with auto-merge null. CI workflow 328946384 and Publish
notebook workflow 328946385 remain `disabled_manually`. Hosted CI is not run by
owner instruction; publication has not occurred and remains gated on completed
repair/local evidence. The sanitized development evidence index is retained with
SHA-256 `addf79f97b037712a9f942bb5c65bedd4905f938f74e02c40467352ff57e5b02`;
raw logs, JUnit, source snapshots and failure archives remain in the protected
runtime evidence store. Historical Docker/sudo uncertainty, GIC startup timer and
failed forwarding observations remain recorded separately; no shared runtime was
contacted by this continuation. The worker setting remains operator-attested
Astra/high, metadata not introspected, and no agent delegation occurred.


GIC-only closeout verified on 2026-09-07: all labelled task containers and guest
volumes are absent; `gic-pr15-ci` is stopped, verified through its exact Lima
instance. Three starts and three stops occurred in this continuation. Reusable
image/disks/cache, protected VM identity and the protected internal image-only
unlock material remain retained. Final available bytes: startup 49,060,233,216;
outer external filesystem 679,172,120,576; protected image 53,505,130,496;
guest data filesystem 28,288,835,584 of 33,633,878,016 total (3,610,386,432 used).
These are separate filesystems/capacity observations, not additive free space.
Existing reserves and resource ceilings were not enlarged. No other runtime or
workload was stopped. The protected image may be detached only after this owned
closeout; its separate external detach record will identify the observed result.

The nonsecret incremental preservation destination is the established external
project evidence root's `pr15/colima-local-validation-20260907` child. Its inventory
binds this ledger and the final explained source delta, with the prior
`colima-resume-20260906` inventory as the reconstruction base. Only changed payloads
are copied; original snapshots, red JUnit and failure evidence remain retained.
The inventory hash is recorded outside these source bytes to avoid self-reference.
Final status is `t09_remote_execution_bridge_review_repair_blocked`: retained
condition/runtime/failure-export wiring and the remaining R1–R6 evidence are
unfinished. Infrastructure readiness and passing components do not close findings.


### 2026-09-07 condition-session continuation (development, in progress)

The starting 65-path delta and 352-member tested candidate were independently
rehashed against the prior inventory. Committed/local/remote/PR head and exact
base remain unchanged; index empty. The prior 129-pass/one-failure run remains
component/development evidence, not validation of the committed head.

The recorded encrypted GIC runtime/image were reused. Prestart validation found
a launcher source error: Colima 0.10.3 `mounts: null` means no mounts; an empty
list selects the home default. The actual profile correctly retained null. The
validator now requires explicit null and rejects missing/empty-list selection.
Sixteen selected guarded cases passed. Effective Lima isolation and daemon/image
identity passed on resume; four update units remain masked. A fresh isolated
containment smoke passed with three expected denials, zero unexpected denials,
and verified exact-owned temporary-resource removal. No shared runtime was used.

The adapter now invokes retained condition-session orchestration with the actual
campaign observer and a separate invocation input, preserving duplex stdin/stdout.
Candidate source/environment/archive selection reaches the actual condition
verifiers. The first new joined attempt reached `execute_condition` and failed
at `PrivateConditionListener.create`: AF_UNIX path too long. Its complete failed
node, JUnit, carrier diagnostic and source input were preserved; exact-owned
containers/volumes were removed. This is additional source-grounded development
failure evidence, not R1–R6 closure. The repair uses a held Linux directory-fd
address for the same owned socket location; short-path behavior is retained.

A single new source fixture, `tests/fixtures/t09/offline-condition-runner.py`, is
explicitly added to the candidate closure. It supplies an upstream test agent
and browser surface to the actual retained runtime wrapper/locked LLM factory.
It creates session JSON from returned fake effects; it supplies no qualified
phase, completion, export, score or cleanup receipt. Qualification fixture 1
bytes and historical archive/scientific pins remain unchanged. The new file
explains the 66th dirty path. Runtime execution/export/finalization, full R1–R6
matrices and final container/parity gates remain incomplete. No success receipt,
implementation ancestor, commit, push or hosted run is claimed.

The next retained runtime attempts preserved two additional test-carrier defects:
shared guard tracking required a registered transaction temporary root, and the
Linux held-fd socket alias required resolved-path containment at the leaf guard.
Both denials occurred before forbidden dispatch; they are not environmental
behavioral characterization or real effects. A later child reached the actual
container entrypoint and `sira_gate_a_runtime.run`, which rejected a stale test
wall clock. The test channel now passes one wall/monotonic origin to host and
child and carries measured condition duration into the campaign clock. The
retained future-origin and lifecycle-chronology validators are unchanged.

Transaction `gic-pr15-ci-e80608b9868f1c11` then recorded two calls from the actual
retained locked LLM factory and one fixture browser action through the shared
observer. Both calls reconciled; their session-derived IDs are retained exactly
in shared frames, runtime events and the nonauthoritative mirror. The returned
fixture action was `send_msg_to_user('No relevant answer.')`. This proves only a
first-condition prefix, not two/four conditions or final scientific acceptance.
The concrete R6 gap is now observed inside this path: admitted event output was
2,051 bytes; end-of-runtime reconciliation reported 50,899 bytes and received
`output-bytes-rejected` / `ProviderBudgetExceeded`. No after-the-write allowance
was added to hide this failure. Comprehensive writer-role admission remains open.

That run also exposed the admission socket surviving into strict raw inventory.
The retained bridge now quiesces the runtime channel before raw sealing, removes
its private endpoint/locator, and retains the relay's shared carrier for later
host terminal frames. A missing client is cancelled with a finite wait; absence
of detachment remains infrastructure-invalid, not a fabricated terminal receipt.
Active nodes:
`tests/control/test_remote_bridge.py::test_retained_bridge_releases_endpoint_before_raw_seal`
and
`tests/control/test_remote_bridge.py::test_retained_bridge_missing_runtime_cancels_before_raw_inventory`.
Both passed in guarded native macOS components and in the isolated Linux container.
Earlier new-test setup mistakes (missing supervisor directory and an already-used
component handshake) remain preserved as setup failures, not behavioral red evidence.
The original joined unsafe-socket failure is the source-grounded characterization.

Transaction `gic-pr15-ci-a8861a2a18bf86f1` ran these two passing socket components
and the still-failing joined node (2 passed / 1 failed, no skip/xfail). Its bound
input manifest is `ebeef0767b56e6b623a0d59137c3e7f6622434407493917453e052d42ca5dc77`;
this identifies dirty development inputs, not the committed HEAD. Retained
`condition_session` and `retained_condition_completion` completed against actual
sealed raw evidence. The controller still lacked the off-host export; retained
cleanup correctly rejected the missing verifier acknowledgement. Cleanup for
that tested transaction remains unresolved even though its outer test container
and exact-owned guest volumes were subsequently removed. No cleanup requirement
was weakened. Export/restore/acknowledgement consumers are the next implementation
seam; shared normalization, finalizer/evaluator agreement and R6 are still open.

New failed-node preservation uses a complete file inventory plus incremental
payload archives referencing an independently rehashed prior retained archive.
Original failures and snapshots remain retained. Only newly created redundant
preservation intermediates are removed after payload reread/hash verification;
no original source/evidence or shared resource is removed. Each run retains full
JUnit, gate/source-integrity result, bounded carrier logs, and actual outer
container/volume cleanup evidence. These runs do not constitute full-suite,
parity, static/privacy/site or final exact-commit validation. No R finding is
closed and no receipt rebind, checkpoint commit, push or hosted CI has occurred.

A targeted host mypy check passed for `remote_bridge.py`, but its invocation
omitted the required external cache override. The existing internal mypy cache
contained 25,870,560 bytes afterward (one recently modified 25,870,336-byte
cache database); prior allocated bytes were not recorded, so incremental growth
is unknown. Earlier targeted Ruff calls also used the existing local default
cache. This is a storage-placement error, not compliant external placement.
The bounded private cache inventory is retained; existing caches were not deleted
or moved. Subsequent host static commands require explicit protected external
cache destinations and disabled local bytecode generation. This does not alter
any container/source gate result, waive the storage policy, or revise the earlier
Docker incident. No experimental/environmental dispatch is inferred from a static
cache write.

### Retained export and shared failure projection continuation (2026-09-07)

The actual retained attempt export now executes `export_attempt`,
`verify_attempt_export`, `restore_verified_attempt_export`, and
`acknowledge_attempt_export` on the same candidate transaction. The local carrier
copies the generated archive bytes; the retained consumer rechecks the full frozen
receipt closure and publishes the acknowledgement. The normal historical entry
still rejects the candidate selection. The earlier source-bound failures remain
preserved; none is relabelled as a successful historical replay.

| Development transaction | Selected container result | Observed stopping dependency |
| --- | --- | --- |
| `gic-pr15-ci-3d04e28e61e4dcb9` | 2 passed, 1 failed | Export bootstrap invocation was rejected by the child guard before export dispatch. |
| `gic-pr15-ci-b39a48534a436308` | 2 passed, 1 failed | Candidate restoration selected the historical current-commit Git lookup. |
| `gic-pr15-ci-c968468404220aba` | 6 passed, 1 failed | Restoration did not create the private aggregate-state parent; an exported archive had an overly broad creation mode. |
| `gic-pr15-ci-8c2e7fb433ca4841` | 10 passed, 2 failed | Newly enforced destination validation exposed nonprivate intermediate directories in both joined and retained export component paths. |
| `gic-pr15-ci-64e03efa5e5aa192` | 12 passed, 1 failed | The export producer omitted receipts required by full frozen validation after restoration. |
| `gic-pr15-ci-a4d108803f71b4fe` | 13 passed, 2 failed | The expanded producer closure had not yet reached the strict export consumer allowlist. |
| `gic-pr15-ci-766e4837ba631394` | 14 passed, 1 failed | Real export, restore, acknowledgement, cleanup and terminal verification passed; shared failed-condition projection remained unwired. |
| `gic-pr15-ci-bc695e3c199ffaf4` | 20 passed, 1 failed | Six real failure-envelope copy/mutation cases passed; joined shared preservation remained unresolved. |

These are separate selected runs, with zero skips, not summed component evidence
or a completed campaign. Each retained record binds its own sealed dirty-source
input, JUnit, source-integrity check and exact outer cleanup. Source 29 input
manifest: `4b9435ce01ad4a70e60b2f65e58f9e8b27f64e4219e8e445969bc4af7083e117`.
Source 31 input manifest:
`a447120d87362c9cd80d52dbbf45e600f667b1c05aa9df8611dbef30d5b1d3fa`.
Both describe 66 dirty paths above the original committed head; they are not
validation of `a98b4b875ab4d101709d62bc7222b5c90681a893`. Development source 30
was preserved but not executed. Complete failed-node inventories reference verified
prior payloads plus new deltas; original archives remain retained. Exact-owned
outer containers and three guest volumes for each completed failed run were
removed only after evidence copy/hash verification.

Source repairs retain existing consumers and role checks: source-aware package
verification no longer mixes the candidate with the historical current-commit
lookup; restoration creates private parents using no-follow directory operations;
atomic state replacement rejects unsafe/replaced destinations; archives start
with private modes; export includes an explicit fixed map of the frozen receipts
and the candidate regression-input record. The consumer verifies the same map
and full frozen identities. The original retained export test remains active.
Raw and essential terminal readers now derive the actual process exit, completion,
answer and error from their sealed session evidence; source bytes are not rewritten.

Active added coverage includes `test_restored_state_rejects_unsafe_destination`,
`test_restored_state_uses_private_atomic_destination`,
`test_restoration_creates_private_intermediate_directories`,
`test_retained_essential_terminal_uses_sealed_process_and_session`, and
`test_retained_failure_export_copies_bound_bytes` in
`tests/control/test_remote_terminal_review.py`. The last node checks real copied
bytes, same-size source and payload mutations, wrong size, unexpected members,
symlinks, idempotent verification and corrupted destination rejection. It tests
copy/verification, not a scientific qualification. The existing
`tests/test_t09_sira_pilot.py::test_raw_attempt_streams_before_cutoff_without_aggregate_stage`
continues to exercise its retained export/restore component contract.

The shared failure projection is still development work. An explicit
`RetainedConditionSource` binds the original raw/essential seal, independently
written terminal normalization and actual export acknowledgement. Its source
reader is shared by the retained producer and the production consumer. A separate
`derived-condition/essential-failure` envelope preserves shared accounting and
copies actual bridge prefixes. Closure claims must be derived from the original
host/runtime cleanup evidence. The new copy consumer writes and rehashes a real
separate destination before acknowledgement; no successful receipt is supplied by
a fixture. Failed preservation is not retried under a different classification.
Source-bound negative and joined coverage remains incomplete.

R1/R2/R3/R4/R5 remain partial; the joined transaction has only one runtime process
and no successful shared finalizer/evaluator/checkpoint chain. R6 still has an
actual behavioral rejection: event writers admitted 2,051 bytes while the runtime
observed 50,899 bytes in the earlier bound run. No retrospective allowance was
added. All writer roles, denial-before-growth, reconciliation and full-controller
failure matrices remain required. Conformance/readiness stays blocked.

A direct host-only mypy invocation initially selected ambient installed modules
and reported 24 errors; this is invalid source-selection evidence, not inherited
failure or a gate pass. Repeating the focused check with explicit `MYPYPATH=src`
for the retained runner, effects and production modules passed. Ruff and mypy used
protected external cache paths. Full local-container parity/static/privacy/site,
source ancestor freeze, receipt rebind and publication have not run. Hosted CI
remains not run by owner instruction. No new experimental effects, scientific
result, V17, merge authority or independent approval is implied.

The next joined source selection exposed two more exact dependencies. Source 32
(transaction `gic-pr15-ci-619a30e6dd8b90cc`, 20 passed / 1 failed) rejected the
restored acknowledgement against the unbound real clock. Its recorded verifier
epoch was 1,800,001,152.8297992, while a later real-clock observation was
1,788,790,095.0679018. The retained export consumers now accept an explicit
observation-clock dependency propagated from the same controller clock; default
historical/live callers retain real wall time and unchanged future/chronology
checks. Source 33 (`gic-pr15-ci-be68716f6735fa5b`, 21 passed / 1 failed) passed the
clock regression but rejected the output-allowance events at exact schema validation.

A guarded read-only bridge-consumer diagnosis from the preserved source-33
transcripts reproduced that schema rejection. It did not execute a controller,
condition, model or browser and is not a host-native joined substitute. Inventory
identity: `796aa1d3b1622bb57d2c73f4baa0820fd5ff355d2407cbc5c917d42b7d541e10`.
The first diagnostic process lacked its required guard journal directory and exited
before execution; the corrected invocation retained the actual rejection. After
the source repair the same preserved bridge bytes validate; the old diagnostic's
red-only assertion therefore fails, rather than constituting a new joined pass.

The 67th explained dirty path is
`schemas/t09-condition-duplex-frame.schema.json`, already a member of the explicit
candidate source closure. It now names the three exact allowance protocol events
implemented by the prior R6 component change. The transcript-order validator
separates accepted capacity from a terminal denial, validates the exact reply and
reason, rejects subsequent runtime activity after denial, and requires a nonzero
host process exit for that path. The supervisor also rejects further effect or
growth requests once it has denied output. This repairs a shared schema/consumer
incompatibility; it does not close pre-growth writer coverage or R6. Original
joined node identity and its complete-campaign expectation remain unchanged.


The shared failure path subsequently executed successfully in source 34
(`gic-pr15-ci-0fdebbdba6369713`, 24 passed / 1 failed / 0 skipped). The unchanged
four-condition joined node still failed at its intended complete-campaign assertion:
the actual first runtime process exited nonzero because R6 remained unresolved.
Shared failure sealing/export, retained cleanup and terminal verification passed;
no failure-preservation exception was substituted for that result.

A separate active node,
`tests/control/test_candidate_inputs.py::test_candidate_actual_package_verifier_in_isolated_source_process[condition-failure-export]`,
now injects an explicit upstream failure after the fixture-driven partial session
write. Source 35 (`gic-pr15-ci-b36c7fff5edd4511`, 24 passed / 1 failed) omitted
local qualification preparation for this new mode and failed before condition
entry; that is a bootstrap prerequisite error, not R2 behavioral characterization.
Source 36 corrects this propagation. Its source/history input manifest SHA-256 is
`4416440f7025e33f394083f4c465efbf72fe36a9dd8a3781e13b6a276da5eba7`;
its complete 353-member candidate binding is
`6d5fba0529c1e8c698852e562e4980dc271be50aae74b96c6691d9b4de44e8e8`.
The selection describes 67 dirty paths above the original committed head.

Source 36 transaction `gic-pr15-ci-e3c731ff9974698d` ran 29 selected container
nodes: 29 passed, zero failed/skipped, 129.200 seconds. The failed-condition prefix
retained answer `No relevant answer.`, actual process exit 1, two exact scoped
call/logical IDs, and no score. Source completion identity:
`11afe86e00cd52b67be0e1fc63cfa30f1b8fbfe359a14464ab4cb1e7f002a686`;
actual shared export receipt:
`6b56a37ebae73b22a285e065649fb3958921d3faa29648937550f6502ba29ede`.
Its original raw/export/acknowledgement, derived failure, accounting, controller
trace, JUnit and source verification are preserved in a reconstructable private
inventory plus a 29,369,856-byte delta/guard archive set. All three exact-owned
guest volumes were removed after verification; the test/preparation/collector
containers are absent. This is a successful intentional failure-prefix test,
not the original four-condition campaign and not R1–R6 closure.

The selected run also passed four active late-activity rejection cases in
`test_output_denial_blocks_later_activity_before_shared_reservation`: model,
browser, new allowance and observed-output requests cannot continue after output
denial. A subsequent guarded native bridge-component module run exposed an older
component test that tried to continue positive reconciliation after such a denial.
Its original red JUnit is preserved. The existing node now tests positive
reconciliation before denial and forged-mirror rejection in a separate session;
no assertion about capacity or observed bytes was dropped. The separate active
late-activity tests retain terminal-denial coverage. This test-contract correction
is not a writer-boundary repair or a new joined result.


Two additional source-grounded component defects were characterized without a
host-native joined run. In
`tests/control/test_remote_transaction_review.py::test_r6_campaign_checkpoint_retains_unconsumed_output_allowance`,
the actual production `_record_boundary_state` consumer dropped an admitted
80-byte upper bound to 0 or 20 observed bytes. The new three-case characterization
had two intended assertion failures and one pass. It now imports the accountant's
existing validated upper/lower projections separately; the next condition cannot
admit more than the remaining aggregate bound. All three cases pass. Unused
capacity is not released merely by observing less output; no release policy or
scientific cap was introduced. This is a history-consumer component, not two
executed retained conditions or R6 closure.

`tests/control/test_remote_bridge.py::test_private_listener_failed_creation_preserves_replacement_evidence`
reproduced three intended assertion failures (socket, manifest and parent
replacement) and one safe rollback pass. Setup failure had an unconditional
unlink loop while normal close already checked exact ownership. Both now use
one exact root/member validation-and-removal helper. Failed publication closes
its listener, checks the whole created member set before deleting anything,
and preserves replacement or unowned evidence. Setup completion also validates
the identities captured at creation. The four setup cases and three existing
normal-close replacement cases pass. Original red JUnit and exact component
source bytes are retained privately alongside source-36 evidence; no failed
historical run was reconstructed. These are R3/R5 components, not the full
controller cleanup/interruption matrix.

The remaining R6 writer map is explicit: runtime JSON and usage ledgers
(`sira_gate_a_runtime._write_json_evidence`, `_write_usage_ledger`), initial
assignment/runtime-environment writes, upstream session/logger writers, the
client's `_persist_journal`, relay journal/terminal evidence, retained attach
stdout/stderr (`run_attached_with_caps`), shared bridge journals, and raw/derived
failure/export evidence. EventWriter alone is admitted. Retained attach streams
currently write directly to files with per-file containment plus later census;
this does not establish shared admission before growth. Runtime journal updates
also accompany admission frames, so treating each of those writes as another
round trip would introduce recursive bookkeeping. A bounded shared allocation
must cover these real writers and preserve exact observed-versus-admitted totals;
no retrospective reservation or reduced output assertion has been added.


Final focused comparison for this continuation uses sealed development source 37,
input manifest `8ab0e70516abc5ad79e07ab7f71192b40c7d469754035209ca7fbe91540efaf3`.
Transaction `gic-pr15-ci-3a09d7a9171ab362` passed all 67 selected nodes, zero
failures/skips, in 132.831 seconds. It includes the intentional failed-condition
prefix, the complete bridge component module, the three reservation-history cases
and retained export/restoration components. JUnit SHA-256:
`a70b263c22c3d4c6d20d904e65748c00b80a5bb5c5b7fa171d1b8e986fec075b`.
The prefix candidate binding is
`43563245bd2693129fbee8e2e11c4c854b39a540c18cec622a212ed21d820124`.
Its source completion and real export receipt are respectively
`a3df5bb2c77e3e87565d254936ab4945eb83046d1c767259ab1bf99c9681a0b6` and
`4a2f9f99dcb1b48ee9ac083bff47e70e45c379c195e3f352fe55dddf20e8cd60`.

The unchanged original `[transaction]` node was separately rerun on exactly that
same source input as `gic-pr15-ci-c2087d281dfb262d`: one failure, no skips,
125.506 seconds. It still stops at first condition execution, with actual shared
output admission 2,051 bytes and observed request 50,900 bytes. The supervisor
rejects growth with `ProviderBudgetExceeded`; the process exits nonzero. Retained
condition terminal processing, attempt export/verification/restoration/ack,
shared essential-failure sealing/export, cleanup and terminal security verification
all pass. The original four-condition success assertion remains red. This is an
implementation/evidence blocker, not a missing runtime, permission, archive or
source-verification prerequisite. No source or test was weakened to bypass it.

Both runs report source unchanged during execution. Each complete selected-node
workspace is retained by verified prior-payload references and a new bounded delta;
all exact-owned temporary containers and volumes are absent. Only the GIC VM was
stopped, with stopped state verified. Reusable image/disks/cache/unlock material and
original source/evidence snapshots remain retained. Shared runtimes were not
contacted. Protected-image detachment and final preservation inventory are recorded
in the task-owned `condition-runtime-repair-20260907` handoff evidence, alongside
sanitized per-node results and actual trace projections. Those projections label
the intentional failure-prefix success separately from the original failed
four-condition test; the latter's captured assertion contains its terminal
transition suffix, not an invented complete controller receipt.

The final focused Ruff check, Ruff formatting check, two-module mypy check with
explicit candidate imports, and `git diff --check` passed. Full raw suite, exact-base
parity, full static/privacy/site gates, final immutable implementation ancestor,
current receipt regeneration, commits, push, and independent review remain not run.
No R finding is closed. All runtime/log/journal/failure writer roles still require
pre-growth enforcement and exact reconciliation; happy raw normalization and
retained finalizer/evaluator/checkpoint wiring, four shared runtime processes, and
the remaining cleanup/timeout/mutation matrices remain required. Current code/test
bytes match tested source 37; this additive ledger handoff is a later documentation
delta. Local/remote/PR head remains the original reviewed head, index empty, with
67 explained dirty paths. Hosted CI remains not run by owner instruction. There is
no new experimental/provider/model activity, V17, scientific result, merge grant
or independent approval. Historical Docker-contact uncertainty is unchanged.

### R6 census attribution and initial-event repair — 2026-09-07

Category 1 continuation; operator-attested Astra/high, no model/effort introspection
or agent delegation. The current 67 paths, types, modes, sizes and SHA-256 values
matched preservation inventory
`fdf40a1acc0e3c089a7591bb84d439d6e399a5f735fd302c8e252976369f0120`
exactly before edits; index empty. Fresh Git/GitHub checks confirmed the original
reviewed local/remote/PR head and required base, open draft/unmerged PR and disabled
auto-merge. Original preservation payloads and source-37 inputs remain unchanged.
No experiment, manifest or workflow source was changed. This entry is later than
the source snapshots described below.

The R6 counters have incompatible coverage. `_install_locked_llm_factory` binds
admission to appended EventWriter bytes; `ResourceGuard._tree_bytes` counts the
entire attempt raw directory, including host records created before that factory,
runtime/session JSON, the private listener binding and the client journal. The
initial assignment event was written before binding and omitted another 256 bytes.
The original source-37 remote journal's exact first 36 frames reconstruct to
33,876 bytes. Original sealed events total 2,307 bytes, of which only 2,051 were
admitted. The final original raw directory is 99,558 bytes, not the earlier 50,900:
post-census teardown adds/replaces files and removes the private listener binding.
Consequently its final inventory alone does not supply an observed per-file census
at the earlier instant. The missing transient binding is not reconstructed as
original evidence. No cumulative grants were added together.

A bounded test-side profile now observes returns from the actual candidate
`ResourceGuard.snapshot`, recording at most 128 observations/4,096 members each.
It does not replace the census, allocate output or change its result. The trace
is written outside the attempt directory by the existing test trace producer.
Source 38 (`3ca4f0e535a4cfc32f589ca5cbafddbaa2c3591aca4c92ba7fc21f8210720ac1`)
transaction `gic-pr15-ci-3e7951cf4c173cfc` reproduced the positive test failure.
Its actual census was 50,897 bytes, exactly equal to the observed member sum:
33,876 journal; 2,307 events; 3,533 runtime/session JSON; 11,181 host entry/release,
command, ownership, timing, overlay and private listener-binding bytes. Variable
record encodings make this a new observation, not a replacement for original
50,900-byte evidence. The guard still rejected the whole-directory observation.

That diagnostic's first implementation incorrectly placed its post-transaction
controller-result file in the sealed candidate source directory. This happened
only after the measured transaction returned; it did not alter executed source
members, but it violates the post-test exact member-set requirement and is not a
passing candidate-integrity result. The original failed workspace is retained.
The producer now writes the complete actual controller result to the separate
transaction output root before asserting success, and validates the candidate
source both in the transaction's finally path and after result publication.
The original positive assertion is unchanged. No evidence was deleted to repair
that diagnostic mistake. The profile is now restricted to the exact sealed
candidate source filename rather than accepting an ambient suffix match.

The first concrete writer repair makes EventWriter's required admission explicit.
A duplex runtime constructs it with `require_output_admission=True`; an unbound
writer rejects before opening the event file or advancing its sequence. The real
runtime publishes assignment only after its retained factory has bound admission.
Historical in-process assignment ordering remains unchanged. The actual shared
observer and real duplex writer regression exercise bound writes and exact event
byte reconciliation. This repairs the initial-event omission, not all R6 writers.

| Evidence | Actual outcome and source |
| --- | --- |
| `test_r6_initial_runtime_event_requires_bound_admission` red | Source 39 `55367c9dd4ff0a60073930aca9e4fde2565efdf05c945c1612f11662f7c0af33`; run `gic-pr15-ci-470a6cde58e035db`: 1 failed, 1 passed, no skips. Failure is DID NOT RAISE after the real writer accepted an unadmitted first event, not import/setup failure. |
| Initial writer component green | Source 40 `b37e7ce3d369a33e2099cb3a33a6d3a7f9a38515df0a5a58451dac4f4bbcaf9c`; run `gic-pr15-ci-bb00071dd79dc9c3`: 3 passed, no skips. The initial bound-write case here used the in-process budget port; its later version invokes the actual shared observer. |
| Both original joined parameters plus three components | Source 41 `f2ea5ad8c986cf7408fb5366111fe482b694d5dd580ff95e76f11c24ace9143e`; run `gic-pr15-ci-b2d23d264792f90f`: 4 passed, 1 failed, no skips; 235.059 seconds; pytest exit 1. `[condition-failure-export]` passes and `[transaction]` remains red. Candidate member verification executes on both outcomes. |
| Later scoped component source | Source 42 `8bdbf9d74954bf2d09efd8f4841dd4238b4dfd99ef13b47aafffcdab470f5c97` includes the actual shared observer assertion and stricter candidate-profile source selection. Its separate container results are retained with the incremental handoff. |

Source 41's actual runtime now grants/observes 256, 430, 1,053, 1,674, 1,955 and
2,307 cumulative event bytes. Its subsequent 54,280-byte census is rejected with
ProviderBudgetExceeded. Extra protocol frames enlarge the journal; the larger
observation is not a changed policy budget. Both controller results, raw/completion,
export/acknowledgement and terminal evidence are retained. The failed positive
transaction still stops at first condition execution. The intentional partial
answer/nonzero-exit path remains unscored, with actual retained failure export,
cleanup and terminal verification. Wrapper success is not workload success.

All-writer pre-growth enforcement remains **partial**: the remote journal, runtime
JSON/session/log streams, pre-runtime host control writers, later relay/shared
journals and derived failure/export writers still need one shared allocation and
bounded nonauthoritative consumption covering their actual scopes. In particular,
a runtime-only grant cannot establish admission for host writes made earlier.
Neither an increased allowance nor retrospective admission was added. The required
host/runtime/failure allocation and consumption integration is still implementation
work under the existing authority, not a request for new permission. R6 is not
closed, and the successful four-condition finalizer/evaluator/checkpoint chain and
remaining R1–R6 negative/coupling matrices remain unfinished. No completeness,
viability or conformance receipt was regenerated.

The same GIC encrypted volume/profile and immutable CI image were reused. Fresh
containment smoke `gic-pr15-ci-e3d451baf2c68b96` passed. The prestart script's
`systemctl is-enabled` diagnostic returned four masked values followed by Colima's
nonzero-status wrapper text; its strict whole-output assertion failed. The recorded
`systemctl show --property=LoadState --value` readiness check independently verified
all four masks. No updater was enabled, runtime reconfigured, dependency downloaded
or image rebuilt. Shared runtimes were untouched. Per-run exact-owned collection
and cleanup are recorded before GIC-only shutdown. Historical Docker/sudo daemon
contact remains unknown; authorized new outer CI operations are separate.

Focused Ruff/formatting, two production-module mypy and diff checks passed. No final
raw full suite, exact-base parity, full static/privacy/site gate, implementation
ancestor, receipt descendants, commit, push or independent approval exists.
Hosted CI remains not run by owner instruction. Current-control source rebind
and all final gates remain pending. Exact incremental source and sanitized review
artifacts accompany the R6 continuation record; the original snapshots remain.


### Accepted private access; atomic writer boundary preparation — 2026-09-07

The independent partial review of evidence commit
`b517fdda1affb60c2e435483c04a4a78f6bedcab` accepted the entry point and inspected
source/evidence representations. Its implementation disposition remains CHANGES
REQUIRED — NOT APPROVED; no R1–R6 finding is closed. Reviewer access acceptance
is not an exhaustive payload rehash, a runtime attestation or new execution authority.
The existing owner-authorized Category 1 continuation remains the work scope.
Operator-attested Astra/high; no model/effort introspection or agent delegation.

Read-only intake again found local/remote/PR head
`a98b4b875ab4d101709d62bc7222b5c90681a893`, tree
`b75ce4579c934440c7679cbf289b3294d01d6caf`, required base
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`, and an open/draft/unmerged PR with
auto-merge disabled. All 67 starting dirty paths, modes and bytes matched inventory
`85d04e2097d53516add44fc8087fd2acfef2a54eb37ecdb8b59d3f9061448b8c`.
The index was empty. Existing snapshots were reused, not recopied or replaced.
The new incremental intake is externally retained under the task-owned
`r6-atomic-publication-20260907` evidence child. Frozen experiment, manifest and
workflow source remains unchanged.

The next preparation exposes admission at both actual atomic publication helpers:
`_write_json_evidence` and `_write_usage_ledger` now share `_publish_json_evidence`.
An explicitly required but absent callback rejects before creating directories or
files. A supplied callback receives the complete encoded temporary-file size before
creation. The old destination must coexist with that entire temporary file until
replacement; subtracting the destination size would understate the peak. The helper
cannot allocate policy allowance itself, release it after a failed publication, or
report temporary bytes as a guessed whole-scope observed total. Exclusive temporary
creation preserves a preexisting/interrupted record instead of truncating it. Write
or fsync failure retains the created prefix and existing destination.

This is an **unvalidated writer-boundary preparation**, not a connected remote
output allocator. Current runtime callers have not yet supplied the callback or
required-admission flag. Their unadmitted JSON/ledger behavior is consequently still
open, as are pre-runtime host writes, runtime session/log writes, relay/client/shared
journals, failure/export writes and the final observed-total reconciliation. No
budget increase, late census grant, observation substitution or reduced evidence
scope was introduced. The new callback must be supplied from the same preapproved
scope allocation as those writers; per-write recursive protocol reservations are
not a solution for admission journals. The initial EventWriter repair and both
original joined test parameters are unchanged.

| Current requirement | Status and evidence |
| --- | --- |
| Atomic JSON/ledger pre-growth call surface and failure preservation | partial: source prepared; 10 active parameter cases added, not executed |
| Actual shared-accountant denial at the writer; full temporary allocation before replacement | test assertions prepared against `_AccountingObserver`; not executed |
| Missing admission, existing destination, retained temporary and outstanding reservation on interruption | test assertions prepared; not executed |
| One pre-host shared allocation and all writer-role consumption/reconciliation | partial from prior work; still not integrated |
| Successful four-condition retained transaction and remaining R1–R6 matrices | blocked for execution; still incomplete |
| Final source/test ancestor, non-circular receipt descendants and exact-container gates | not started; no new product commit |

The new nodes are `test_r6_atomic_runtime_record_requires_admission_before_creation`,
`test_r6_atomic_runtime_record_shared_denial_preserves_files`,
`test_r6_atomic_runtime_record_reserves_full_temporary_before_replace`, and
`test_r6_atomic_runtime_record_failure_retains_prefix_and_reservation`, in the
existing `tests/control/test_remote_transaction_review.py`. JSON and usage-ledger
roles are both parameterized; denial also covers an absent versus existing record.
These new API cases are not represented as historical red characterizations.
The source39 original red evidence remains unchanged and separately identified.

Focused Ruff formatting/check, one production-module mypy and `git diff --check`
passed on the new source. No implementation test, contained smoke, joined run,
full-suite/parity/native-only/privacy/site or final control gate was run in this
continuation. No source41/source42 result is assigned to these changed bytes.

Runtime execution has a precise unresolved prerequisite: the accessible protection
record identifies the retained GIC image and confirms an internal protected unlock
control file, but does not give that file's location or a configuration record that
resolves it. The location has been requested from the owner; its value must not be
provided. No new key/image/profile was created, no credential search performed,
and no image/daemon/VM was mounted, contacted or started. Only the recorded outer
APFS mount was checked: same volume identity, writable/noowners classification;
654,708,371,456 available bytes at intake. Startup availability was 45,572,231,168
bytes, above the retained 8 GiB floor. These observations do not establish protected
image or guest readiness. Existing GIC stop/detach evidence remains historical,
not a new observation of an active runtime. Shared runtimes were untouched.

Direct source self-review notes the remaining integration boundary explicitly:
preparing this callback cannot make the positive transaction pass, and observed
scope occupancy must not be confused with temporary allocation or cumulative
rewrite traffic. The production runtime must remain blocked from a completeness
claim until the actual connected boundary and all required tests execute. Hosted
CI stays not run by owner instruction; no V17, scientific result, provider/model
cost, product push/PR mutation, merge or independent approval is created.

### Recovered-locator resume; runtime writer admission and conserved census — 2026-09-07

Operator-attested GPT 6 Astra/high; no model/effort introspection or delegation.
The owner-delivered resume instruction supersedes the preceding missing-locator
blocker. The recovered nonsecret pointer was revalidated, and the existing GIC
image unlocked through its protected descriptor channel. No unlock value or
fingerprint was recorded. The existing encrypted external image, GIC-only profile,
configuration, masked update timers, forwarding restrictions and immutable ARM64
CI image were reverified; no replacement runtime/image/key or dependency download
was created. Shared Desktop/Lab/Biblos runtimes were untouched. The historical
Docker/sudo incident remains acknowledged with unknown daemon contact.

Intake again verified local/remote/PR head `a98b4b875ab4d101709d62bc7222b5c90681a893`,
head tree `b75ce4579c934440c7679cbf289b3294d01d6caf`, required base
`f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2`, and base tree
`e3cf777632400ec18736a34b6abec53d6d67de55`. PR15 remains open/draft/unmerged,
auto-merge disabled. All 67 explained dirty paths initially matched preservation
inventory `f3c8e5bb9b1e6c4aca9ea7cfb37fb0f2c82f79840b55eb3f0224d4a4c5fa2bc5`;
originals were retained. Index remains empty; no product commit or push. Frozen
experiment/manifests and workflow files are unchanged. The latest incremental
preservation and private review handoff use the existing external evidence child
`r6-resume-after-locator-20260907`. Dirty overlays, complete joined candidate
closures, and per-run identities are distinct objects, not the committed HEAD.

Actual changes and scope:

- Runtime atomic JSON/usage-ledger callbacks are connected to shared admission for
  the complete temporary size before mutation. Denial/interruption keeps original
  files, created prefixes and reservations. These previously untested cases ran.
- The duplex client reserves its initial journal capacity before its first journal
  write, carries bounded bootstrap frames in memory until admission, and consumes
  its mirror before publication. Additional journal capacity is granted by the
  shared observer before exchanges that cannot safely perform nested allocation.
  The actual private-client entry enables this path. Legacy direct component ports
  retain their original default. No global policy allowance is locally created.
- Terminal JSON has a bounded, shared-admitted 64-KiB pool before work begins;
  source session/logger writes have a 4-MiB pool. These are allocations from the
  unchanged existing budget, not increases to that budget. Python session/log
  opens now consume before creation/truncation/write, resolve UTF-8 locale
  explicitly, reject links/nonregular replacements and do not expose raw FDs.
  A caught logger admission denial remains sticky and invalidates completion;
  subsequent writes cannot clear it. This guard is not an arbitrary native-code
  sandbox and does not cover host attach streams or host/shared journals.
- Output observations carry unconsumed terminal/source/journal capacity separately.
  The shared observer and transcript validator reject occupancy that would consume
  those outstanding allocations. No late grant, substituted observation, omitted
  journal or cleared campaign history was used.
- Shared outcome-validation failures retain the effect-returned original source
  and bridge references for the existing held-first failure validator. This fixes
  the later failure-export loss of those references; validation still grants no
  authority merely because a reference was supplied.

Distinct observed container runs (no cross-run sum is a suite result):

| Source / run | Actual selected result |
| --- | --- |
| source43 / `gic-pr15-ci-7be154319079e743` | 32 component passes, including the prior 10 untested atomic cases |
| source44 / `gic-pr15-ci-678605b472e5a721` | 81 component passes |
| source44 / `gic-pr15-ci-0fb7b19a79ca67df` | 4 passed / 1 failed; positive transaction failed, intentional failure passed; this predates strict unused-capacity conservation and is not all-writer R6 proof |
| source46 / `gic-pr15-ci-6e25cb6f35598e3e` | 84 component passes |
| source47 / `gic-pr15-ci-e5dea01c05eaab05` | 87 component passes |
| source48 / `gic-pr15-ci-54585b8abf2fee9a` | 88 passed / 1 failed; positive transaction correctly infrastructure-invalid after census rejection; essential export/cleanup preserved |
| source51 / `gic-pr15-ci-4107540deb1dc23c` | 91 passed / 2 failed; Path.open locale encoding was rejected before the intended allowance assertion; preserved as a compatibility failure, not fabricated review-head red evidence |
| source52 / `gic-pr15-ci-b0923987a4df5628` | 97 component passes after locale/path corrections |
| source52 / `gic-pr15-ci-d95be682eec2f2e6` | positive transaction failed; intentional failure/export passed |
| source53 / `gic-pr15-ci-dc8c6a044f21c73d` | 98 component passes including caught logger denial |
| source55 / `gic-pr15-ci-1df0968836058d93` | 99 passed / 1 failed: 98 components plus intentional failure/export pass; original positive transaction fails; zero skips/errors; pytest exit 1; source unchanged |

Source55 input-manifest SHA-256 is
`ceac5c7cbb472c5239ec942679a2bd4c5c6c9647e8dd26a20f5ae19ac4d55451`.
This later additive ledger entry is not part of that tested snapshot. Intermediate
source45/49/50/54 snapshots were not executed and are not assigned test results.
All active original positive and intentional-failure assertions remain unchanged.
Focused Ruff check/format, six production-module mypy and diff checks pass; full
raw-suite/parity/control/privacy/site/native-only gates were not run.

The source55 bounded diagnostic calls the real ResourceGuard census unchanged,
then records a second bounded member inventory. Its last member sum was stable:
68,390 observed bytes = 57,205 runtime-produced bytes + 11,185 host-produced bytes.
The last grant was 19,006,889; retained unconsumed capacity was 18,949,684. Thus
`grant - retained = 57,205` and `observed + retained - grant = 11,185` exactly.
The missing host bytes are readiness/release markers and supervisor admission,
command, identity, timing, evaluator-binding and start/release records. The session
file's 265 bytes are now admitted. This does not prove pre-growth admission from a
scan: the actual writer tests and wiring establish only the covered runtime roles.
The host's writers still need admission before producing their own files. Later
host cleanup/seal/export and relay/shared journals remain in the required scope,
although they are later than this runtime census. No budget increase is indicated.

The positive path's workload exit is 1, answer is `No relevant answer.`, and score
is absent. Its host condition-session wrapper exit 0 means orchestration completed,
not workload success. The controller preserves infrastructure-invalid/unscored
classification, original raw source, bridge evidence, essential failure, export and
acknowledgement, then performs retained cleanup and terminal verification without
a later condition. Earlier source44's missing shared completion files remain a
separate downstream wiring gap; source48/52/55 stop earlier at the correctly
rejected census. A four-condition success, finalizer/evaluator and first-pair
checkpoint have not been demonstrated.

| Finding | Current component / joined evidence | Remaining requirement |
| --- | --- | --- |
| R1 | Actual retained factory and scoped IDs in the first runtime; prior component evidence preserved | four fresh clients with carried campaign history and full replay/evidence matrix |
| R2 | Actual answer/nonzero workload and retained failure export preserved | successful/None/zero-score agreement through shared completion/finalizer/evaluator and mutations |
| R3 | Retained qualification/freeze and failure cleanup/terminal path executes | all pre-freeze prefixes, corruption/replacement/idempotence and interrupted cleanup matrix |
| R4 | One controller drives retained transfer/preflight/qualification/freeze/first runtime/export/failure cleanup | successful joined four-condition chain and required coupling tests; no completeness claim |
| R5 | Existing partial I/O/deadline component cases pass in guarded Linux container | full-controller timeout/disconnect, descendant/FD cleanup matrix |
| R6 | Runtime event/JSON/session/logger/private-client journal denial and conservation components pass; host deficit attributed exactly | pre-host and all remaining writer-role admission, exact final reconciliation, full-controller denial matrix |

The required next source seam is host output admission before readiness/control
publication, followed by attach/host/shared journals and bounded failure/export
writers. It must preserve shared allocation authority and a coherent cross-peer
counting scope. Granting the already-written 11,185 bytes now would be an invalid
repair. Shared success normalization must be a separate source-bound derived
artifact; it cannot invent missing files inside sealed raw evidence. Retained
finalizer/evaluator/checkpoint adapters remain unfinished. These are authorized
implementation tasks, not a request for a new owner waiver.

Existing GIC-only containment smoke passed before tests. Exact-owned test and
preservation containers/volumes were removed after bounded evidence export; VM
stop and final image-detach observations are retained with the private closeout.
The image/disks/cache/unlock material and all original source/evidence remain.
Authorized outer GIC operations are distinct from fake experiment events and the
historical uncertain incident. No real experimental/provider/model activity, new
provider cost, V17, authority grant, science change, merge or independent approval.
Hosted CI remains not run by owner instruction. No immutable implementation
ancestor/current receipt descendants or final tested product commit exists.


### Host/control continuation — development, September 7, 2026

Operator-attested Astra/high; no metadata introspection or delegation. Starting
67-path inventory matched its retained predecessor exactly; index empty and local,
remote and PR head remained a98b4b875ab4d101709d62bc7222b5c90681a893.
The GIC-only protected runtime and immutable CI image were reused after current
protection/identity checks; containment smoke passed. No shared runtime was contacted.

The host bootstrap now requests shared output capacity before the binding/release/
control publishers grow files, and hands original frames into the same runtime chain.
Host and runtime do not mint separate authority. Atomic partial prefixes remain
retained, and rejection is sticky. Source56 exposed a prefix direction-label defect
and two invalid zero-cap test setups; both are retained as development failures.
Source57 corrected them: 109 passed/1 failed/0 skipped. The actual first workload
exited zero with its real fixture answer, but shared control projection was missing.
Source58 added separately derived raw-bound control documents: 109 passed/1 failed;
its archive omitted these documents. Source59 puts the exact five projection members
through actual retained archive verification/restoration/acknowledgement: 134 passed,
1 failed, 0 skipped. Condition execution and raw export now pass in its positive
transaction gic-pr15-ci-628bce190ec7f5bf; finalization remained unwired and its failure
path lacked retained source references. The intentional condition-failure-export
parameter passes separately. No successful four-condition campaign is claimed.

The additional changed path containers/sira-smoke/pragmatic/t09_evaluate_attempt.py
belongs to the approved candidate/finalizer input closure. Development now propagates
the existing explicit source/archive/environment binding to the retained finalizer,
with default historical rejection unchanged. The real retained finalizer and evaluator
are being wired next; these edits and new projection mutation tests are not yet run.
The whole-transaction test watchdog increases to 900 seconds for the added retained
finalizer/four-client path, within the existing container wall ceiling; scientific
condition/campaign deadlines, retries, policy caps and parity exclusions are unchanged.

Remaining R6 coverage includes nonempty attach streams, shared/relay journal failure
capacity, export/finalizer writers and final reconciliation. R1–R6 remain partial;
no final ancestor/receipt rebind, full/parity/privacy/site gate, product commit/push,
V17, scientific result or independent approval. Hosted CI is not run by owner instruction.


### Host/control downstream continuation — source60 through source68 development

The original source55 failure and every later failed positive transaction remain
preserved. No component count is added to another run or treated as a campaign pass.
The positive [transaction] and intentional [condition-failure-export] parameters
remain separate, active assertions. Source60: 149 passed/1 failed; source61:
1 passed/1 failed; source62 and source63: each 3 passed/1 failed; source64 through
source66: each 7 passed/1 failed; source67: 7 passed/2 failed. None skipped.
Source68 is sealed and running; it includes the unproven lifecycle normalization.
All are dirty-source evidence under unchanged committed a98b4b8, not tests of
that committed source. Exact input manifests, complete candidate closures, JUnit,
phase traces and reconstructable guest-tree deltas are retained privately.

The retained finalizer now executes. Its successive original failures identified:
source60's unsupported child-invocation filename; source61/62's stale condition
clock reused for a later export acknowledgement; source63's evaluator-file order
mismatch; source64's guarded rejection of an isolated Python metadata child;
source65's actual versus explicitly synthetic metadata-directory mismatch;
source66's three historical image hashes still selected by the evidence schema;
and source67's misuse of the canonical-binding decoder on a pretty-printed source
schema. The latter is a development regression, not a historical behavior finding.
The repaired paths retain exact acknowledgement clocks, one fixture-owned ordered
evaluator manifest, guarded execution of fixed metadata probes against the already
bound synthetic dist-info files, and complete explicit candidate/environment/archive
selection for the finalizer and independent finalized-output selector. Only three
image-file schema constants are projected in memory; all other schema constraints
and historical schema bytes remain unchanged. Ordinary selection still rejects
candidate input without its complete explicit contract.

The runtime's actual remote-mirror lifecycle differs from historical schema 0.2.0.
Source68 adds a separately derived, nonauthoritative lifecycle projection from the
sealed original journal and mirror, using the same frame/order/binding validator
as complete bridge validation. It checks scoped monotonic IDs, replies, terminal
status and exact mirror agreement. The original lifecycle/raw files are unchanged;
invalid or unresolved evidence remains infrastructure-invalid. Its real-runtime
and mutation test has not yet returned at this ledger entry. No finalizer/evaluator
or first-pair success is claimed before actual consumer evidence.

Source64 adds three passing actual relay-publication regressions: valid, denied,
and interrupted writes. Full encoded bytes consume shared-prefunded capacity before
creation; partial temporary bytes remain retained rather than being deleted/retried.
Source66 also prefunds the bounded terminal transcript/receipt before the final
acknowledgement closes admission. Shared unused capacity remains reserved, never
reported as observed usage. Existing finite frame/transcript/policy caps are retained.
Actual attach-stream admission, shared/export/finalizer writer coverage and final
whole-scope byte reconciliation remain incomplete. No R1–R6 finding is closed.

The source64 incremental preservation records 68 paths, 14 new payloads and
2,706,199 payload bytes; inventory SHA-256
095a898dff2b125cdb0407cbb961b4580e40c94b6be09d9a86b2f04d7b78b670.
It references the intact prior snapshot and keeps all originals. Later source67/68
changes require their own incremental preservation. No product commit/staging/push,
final implementation ancestor, receipt descendants, full/parity/privacy/site gate,
V17, science change, live activity or independent approval has occurred. Hosted CI
remains not run by owner instruction. Authorized GIC-only outer CI operations and
intercepted guard denials remain distinct from fake environmental events and the
historical Docker/sudo incident with unknown daemon contact.


### Continued retained checkpoint and attach-writer repair (September 8 UTC)

Source69 (`a6d32f923a2fecd61cbbe22f76bae08ffa309229cff940d57040333afc8fbb85` input/history manifest), transaction `gic-pr15-ci-75a1557f64f2ab53`, recorded 10 passed / 1 failed / zero skipped. Both Task A conditions executed, exported, finalized, and evaluated through the retained implementations. The actual shared first-pair decision admitted Task B. Its retained state had not received that decision, so Task B rejected entry; its nonexistent attempt root then made export fail. Cleanup/terminal verification succeeded. This is a failed positive transaction, not four-condition proof.

The new active `[transaction-no-answer]` parameter preserves two separate runs. Source71 (`7b0eb86e2b9f854ddc1498643bbf97063d29c707d19fe7743df166d2bba5a8cc`), transaction `gic-pr15-ci-8bc52c4b9c4c957e`, failed because production equated normal process exit with task completion. Source72 (`a1f8552382c6af076ed7344f2176f1fb3376ef5028effa8611306597d2bf9d53`), transaction `gic-pr15-ci-218bb2a033046eac`, removed that conflation: both actual no-answer conditions reached retained finalization/evaluation, scored 0.0 under unchanged policy, and the actual first-pair decision stopped Task B. Its new outer parameter assertion still incorrectly expected complete-four-condition state; that test wiring was corrected subsequently. Both invocations remain failed pytest runs. The original positive `[transaction]` and nonzero `[condition-failure-export]` assertions remain distinct and active. Source70 was frozen but not run; an unexecuted test access was corrected before source71.

Source73 (`e6ec67437cf53c5a7640e6146e8ddc4f262e85d4e58184a830b90a8803b308c3`), transaction `gic-pr15-ci-199c8b3d2bc10373`, failed its one positive node at the actual new checkpoint receiver. The full source-bound shared decision arrived, but its first-pair origin was 1800001133.0 versus the sealed host origin 1800001132.625. Production had initialized its state at receipt return, discarding the 0.375-second transport/return interval. The correction derives shared wall/monotonic origins from the sealed manifest and revalidates that identity during provider-cost observation. It does not alter clocks in prior evidence, policy durations, or the host's frozen document. A regression checks the exact fractional origin and rejects byte/interval drift.

The checkpoint transport uses immutable bytes in the existing condition request and an exact phase-file hash. The retained receiver validates candidate/frozen/plan/source identity, actual Task A selections, raw/semantic hashes, and existing export acknowledgements, then calls the existing record_first_pair_checkpoint on its state replica. It does not create another decision owner. Publication reserves exact encoded decision/state temporary bytes through the shared bridge first. Replay/conflict and full coupling coverage are still pending. Source74 was frozen but not run; an import-order issue and a new test's exception type were corrected before source75. Source75 (`72be0e7c648e8836a2df8297ff97f05df99aa94edc1256bf2444ed3c5e021049`) is running the positive, no-answer, and clock tests; no outcome is claimed here.

Subsequent untested R6 work connects actual attach stdout/stderr to a shared-funded bounded 4-MiB combined allocation, requested before files/process creation. A nonblocking pipe reader consumes that allocation before unbuffered file writes, retains admitted prefixes, and signals infrastructure stop on denial/interruption. The existing 512-MiB per-stream/attempt caps are unchanged; the allocation is not permission to exceed them or extend itself. The new tests cover both real local stream descriptors, shared consumption/observation, and rejection before process/file creation. These edits are not in source75 and have not yet been run. Shared journals, later output-role reconciliation, failure-before-runtime export, all R1–R6 matrices, and full final gates remain incomplete.

Source69 preservation inventory `d1a046afb18ad30794468451c741290da0ae9fb1d887c3696748b09e6b6e2cff` retained 68 safe source payloads (4,610,155 bytes). An octal-string versus integer mode comparison caused redundant copies: the separately retained correction identifies the actual eight changed paths. Originals and prior archives were retained; no credential or historical archive was copied. Future incremental comparisons normalize mode values. Source/testing evidence remains dirty development over a98b4b8, not a committed repaired ancestor. Hosted CI remains not run by owner instruction; no product commit/push or readiness change has occurred.

### Observed joined completion and attach-writer coverage (September 8 UTC)

Source75 (dirty input manifest `72be0e7c648e8836a2df8297ff97f05df99aa94edc1256bf2444ed3c5e021049`) ran transaction `gic-pr15-ci-144914b8c4babdf8`: 3 passed, 0 failed, 0 skipped in 524.046 seconds. The original positive transaction executed all four retained conditions, finalizers, evaluator fixture consumers, actual continuing first-pair checkpoint, cleanup and terminal verification. The separate no-answer transaction executed two normal exit-zero/incomplete/None conditions, valid zero scores, and the unchanged first-pair stopping policy. The clock regression verified the sealed fractional origin; neither outcome changes scientific eligibility.

Source76 attach components recorded 2 passed / 4 failed: the four failures were erroneous test assertions equating observed output with reserved upper capacity. Their actual valid-write/denied-byte assertions passed. Source77 corrects those counter assertions and records six passing components, separately from integration. Source77 input manifest `16505dbc2652ea303de187b39b8bb367377c455970d6e8494501bf9a8082b580`, transaction `gic-pr15-ci-aa472db567fa23df`, records 3 passed / 0 failed / 0 skipped in 652.862 seconds: `[transaction]`, `[transaction-no-answer]`, and `[condition-failure-export]`. The positive node additionally verifies four distinct actual runtime processes, candidate runtime-source identity, exact prior call/logical-ID history, eight distinct calls, actual distinct fixture answers, retained evaluator score 0.0, and the actual continuing checkpoint. Intentional workload exit 1 remains infrastructure-invalid/unscored despite the passing wrapper. Complete node workspaces and guard journal were retained as 102,401,536 incremental bytes with verified prior references; all three exact-owned guest volumes are absent. This is dirty-source offline proof, not validation of committed a98b4b8 or independent finding closure.

Source78 input manifest `a52fb9d7513c760815be30c4bde17bc70e2bae3684c8a126f21ef4ddc3eb9c46`, component transaction `gic-pr15-ci-ea1a4e0761a124ab`, records 2 passed / 0 failed / 0 skipped in 0.785 seconds for `test_r6_attach_partial_write_and_interruption_preserve_prefix_and_reap[False/True]`. Actual stream writes retain a 128-byte partial prefix on write failure, and interrupted release reaps the actual child/capture worker. A distinct full-controller attach-output-denial characterization is running; its result is not yet asserted.

R1–R6 remain open pending their complete negative/coupling/cleanup matrices and complete writer-role reconciliation, particularly shared/control journals, later essential/export and finalizer outputs. No final source/test ancestor, receipt rebind, full-suite/parity/static/privacy/site cycle, native-only final gate, product commit/push, or hosted CI was performed. Hosted CI remains not run by owner instruction. Real experimental effects remain zero; authorized isolated outer CI activity and historical incident uncertainty remain separate.


### Attach-output denial, essential export, and shared carrier admission

Source78's full-controller denial preserved the four-MiB attach prefix but exposed
missing interrupted bridge/source propagation in shared essential preservation.
Sources79–81 preserve the successive failures: exact container-kill observation
was incompletely routed; cleanup attempted admission through a failed relay future;
and the actual essential-seal consumer queried Docker identity through an ambient
boundary. The latter dispatch was intercepted before process creation. The guard
journal's own write was initially denied by the narrower bootstrap write guard;
its exact existing per-process journal is now permitted, so intercepted failures
are not masked. No experimental Docker invocation was performed by those denials.

Host failure/cleanup publication now consumes a finite shared grant obtained before
runtime handoff. Three actual interrupted duplex prefixes remain distinct from full
terminal evidence; no detachment or acknowledgement is fabricated. Their validators
check schema, source/session, exact canonical prefix/IDs and authoritative calls.
The retained essential source role keeps nonzero exit infrastructure-invalid and
requires independently validated cleanup/security facts. Missing runtime cleanup
stays a named failure rather than a synthesized success.

Source82 explicitly binds the exact image-info leaf query to the same deterministic
environment channel. Environmental fixture revision 5 adds that command shape;
the 15-member/2,034-byte qualification archive remains unchanged. Source83 completes
the already-modeled exact-owned kill dispatch. Actual exit -9, closed runtime
resources and removal/absence are retained. Source84 fixes essential versus raw
seal role selection, then reaches shared sealing/export and cleanup but rejects
original retained mount-path fields in final privacy scanning. Source85's attempted
role distinction incorrectly skipped secret-shaped structural checks; its new
active regression caught that error (3 passed/1 failed). Source86 preserves secret
and network checks for both roles, exempts only original retained absolute mount
fields, and independently applies public-envelope checks even when a descriptor
has both roles. Raw bytes remain untouched.

Source86 full-controller `[transaction-attach-output-denial]` passes separately
from the earlier successful/no-answer/intentional-failure campaigns. Its actual
attach denial, exit -9, bounded retained and shared essential sealing/export,
privacy, cleanup and terminal verification all run. Complete original guest-tree
members and guard records are retained with verified incremental references;
its exact three owned volumes are absent. This is failure-path acceptance, not a
successful scientific workload and not R6 closure.

Source87 introduces a disjoint controller-output reservation in the existing shared
observer: remote allowance updates cannot spend shared-carrier capacity. The
actual carrier's bounded transcript, terminal receipt and nonempty diagnostics
consume grants before writes; partial writes preserve their admitted occupancy.
Controller observations reconcile separately after validating terminal protocol
evidence, whose accounting snapshot precedes its own receipt publication. Unused
capacity remains reserved through campaign carryover. The whole guarded review
regression module passes (73/0/0); the four joined parameters are running and not
yet certified for source87. Three-module mypy and targeted Ruff pass. Additional
export/finalizer writer roles and complete post-host byte reconciliation remain
unimplemented; no full R6 or other review-finding closure is declared.

Exact distinct focused results below are dirty-source evidence over unchanged
committed a98b4b8, not that commit's test results. Counts are passed/failed/skipped,
never combined across invocations.

| Source | Transaction | P/F/S | Input/history manifest SHA-256 |
|---|---|---|---|
| 78 | `gic-pr15-ci-272254a91651ec53` | 0/1/0 | `a52fb9d7513c760815be30c4bde17bc70e2bae3684c8a126f21ef4ddc3eb9c46` |
| 78 | `gic-pr15-ci-ea1a4e0761a124ab` | 2/0/0 | `a52fb9d7513c760815be30c4bde17bc70e2bae3684c8a126f21ef4ddc3eb9c46` |
| 79 | `gic-pr15-ci-3035c4f9e4a10187` | 0/1/0 | `0316b30e94dc30f02d7e924b50deb84a141c5b594ae54a4ca3af066bdae0bcab` |
| 80 | `gic-pr15-ci-0e03322cdbe6cab6` | 2/0/0 | `f2c359e8a65d8de3ce473c31548325bb6ef5eb79c5e3bd10376a2bd1257a5285` |
| 80 | `gic-pr15-ci-79abe946188509b3` | 0/1/0 | `f2c359e8a65d8de3ce473c31548325bb6ef5eb79c5e3bd10376a2bd1257a5285` |
| 81 | `gic-pr15-ci-16557c133b9ceac8` | 3/0/0 | `d88dc5a96e187d8d41c6814b2cccf205de55e1b5c14ec9c2b01f064f2024d283` |
| 81 | `gic-pr15-ci-eec4805ad268012c` | 0/1/0 | `d88dc5a96e187d8d41c6814b2cccf205de55e1b5c14ec9c2b01f064f2024d283` |
| 82 | `gic-pr15-ci-5a8ff48660b51b7b` | 0/1/0 | `e09b310b550fa839f9bf7d7f8a7d424e4d560e8d80b5043b4924bd8bb8b98be9` |
| 83 | `gic-pr15-ci-e4fb18ce1267d6fc` | 0/1/0 | `ff51ae77260bc63e7009cef9826b77a622cc63993aa9f0f6fb34e16eba63815e` |
| 84 | `gic-pr15-ci-1fb093b260cc414f` | 0/1/0 | `3b2b4de09ac45ea16dc892bbce83f6655fd48be613061f58e10f8fdf02074a50` |
| 85 | `gic-pr15-ci-c2547f93f8902ff1` | 3/1/0 | `000cacfe248b2c63911d4146186ce03b50768228a93acdce829f4318e6a70d87` |
| 86 | `gic-pr15-ci-8db2088d3d2fa84b` | 1/0/0 | `7f2d7cf55fcdd40a744899f39229957dd6b8149663555cd31d1dc34e45846769` |
| 86 | `gic-pr15-ci-f777f595a8569c2e` | 4/0/0 | `7f2d7cf55fcdd40a744899f39229957dd6b8149663555cd31d1dc34e45846769` |
| 87 | `gic-pr15-ci-4182d9cb2f48c84a` | 73/0/0 | `508b3d415dd36dc5024c249779711172848458406cc1854a1f7e03dc194cb4ba` |

Latest pre-source87 external incremental inventory was
`5d6fb5a4549f567ac026884827e9080b3b4fe52838812f771420304a894476e6`:
68 paths, 11 new payloads, 2,636,085 bytes, with original/prior references retained.
Later source and this additive ledger require a new preservation inventory.
R1–R6 remaining negative/coupling/full-cleanup matrices, final immutable source/test
ancestor, noncircular receipt descendants, full exact-base/parity/static/privacy/site
and native-only gates remain incomplete. No product commit/staging/push, V17,
science change, readiness/merge/auto-merge, or independent approval occurred.
Hosted CI remains not run by owner instruction. Authorized GIC-only outer runtime
operations remain distinct from fake experiment effects and the acknowledged
historical Docker/sudo incident with unknown daemon contact.


### Source87–96 downstream admission continuation (development, 2026-09-08 UTC)
Source87's four distinct joined parameters completed: successful four-condition
campaign, normal no-answer first-pair stop, intentional failed-condition export,
and attach-output denial, each through retained orchestration (4/0/0). Source89
hardened immutable carrier role caps. Source90 added actual finalizer, selection,
restoration-copy and mutable-state writer callbacks. Its positive, no-answer and
intentional workload-failure paths passed, but attach denial failed because a
failed workload with published real terminal receipts was incorrectly routed to
the interrupted-prefix validator. The strict prefix rejection is retained.
Selection now requires all complete-bridge members when any terminal publication
exists; absent/corrupt terminal evidence cannot silently downgrade to a prefix.
The actual full validator still establishes acceptance, and the workload remains
infrastructure-invalid/unscored.

Source91 pre-funded the bounded shared essential envelope plus its carrier copy
before condition entry. Actual immutable failure publishers consume that allowance
before writing, preserve partial output and never regrant on retry. The four new
publisher tests initially used the generic duplex fixture's 100-MiB cap and failed
at admission before reaching their writer assertion; these are fixture-setup
failures, not behavioral red writer proof. Source92 uses the retained 512-MiB
attempt cap explicitly and adds a separate insufficient-policy rejection test.
No production budget or historical expected identity changed.

Static reservation arithmetic identified that allocating the entire finalizer
maximum alongside all still-owned pools would exceed the unchanged condition cap.
The explicit offline finalizer uses 4-MiB host and 4-MiB derived suballocations,
with actual writers enforcing exhaustion; the retained 64-MiB envelope and
128-MiB derived role ceilings remain unchanged. Source93 was not executed because
an import-placement lint error was corrected in source94. Source94's four joined
parameters failed before runtime entry: SharedCarrierOutput attempted to replace
a prior 128-MiB controller allocation with its own 65-MiB total. The actual shared
monotonic guard correctly rejected it. Source96 fixes that hidden local/global
counter mismatch by requesting an incremental allocation and reporting incremental
observed writes. A regression begins with pre-existing controller allowance and
usage, then executes the actual carrier publisher.

Source95 added before-write callbacks to the actual bounded archive and control
snapshot/restoration writers, plus the explicit export grant propagated through
retained export/verify/restore/ack orchestration. It was frozen but not executed
before the source94 counter failure required the source96 correction. Export uses
a pre-entry 16-MiB child allocation and 1-MiB carrier-record allocation under the
same accountant, with no automatic enlargement. Actual retained algorithms still
produce and verify the bytes. Final retained occupancy is measured independently
of those pre-write checks. Further full post-host census reconciliation and the
complete R1–R6 negative/coupling/cleanup matrices remain pending; components and
prior joined passes do not close R6.

Exact results below are separate invocations, bound to their dirty input manifests.
No immutable final implementation ancestor, product commit/push, final full-suite/
parity/site gate, hosted CI, scientific run, or independent approval is claimed.

| Source | Transaction | Passed/failed/skipped | Input/history manifest SHA-256 |
|---|---|---|---|
| 87 | `gic-pr15-ci-4182d9cb2f48c84a` | 73/0/0 | `508b3d415dd36dc5024c249779711172848458406cc1854a1f7e03dc194cb4ba` |
| 91 | `gic-pr15-ci-420852155efd1ce2` | 88/4/0 | `3779fdbd4897b34bd6e8f7168758cfcd8c4a2aa00a11bffaf64a45631ee79645` |
| 90 | `gic-pr15-ci-822c63dfa0f32ac2` | 3/1/0 | `06569d1c761dd63c92da8847ee40fed867190912d11da1eb5cba8be480bbf189` |
| 90 | `gic-pr15-ci-84b4b980d876b0e5` | 84/0/0 | `06569d1c761dd63c92da8847ee40fed867190912d11da1eb5cba8be480bbf189` |
| 92 | `gic-pr15-ci-914c14ea73b527a3` | 93/0/0 | `2492e681390509bb18627a0ce311ee998272f247fda46755f4663d77baca673c` |
| 96 | `gic-pr15-ci-a673834a42ecade4` | 97/2/0 | `1a0092874dfbcceb923859840fcaa92c313496a9f3d8e779936e74be4ea2bc47` |
| 87 | `gic-pr15-ci-baefd2751ad17f68` | 4/0/0 | `508b3d415dd36dc5024c249779711172848458406cc1854a1f7e03dc194cb4ba` |
| 89 | `gic-pr15-ci-c2810705edf296d0` | 74/0/0 | `2c95348dff7c8f2576b525b8025b4e6a04bce2d6053d5cbd7c557cccdeba726e` |
| 94 | `gic-pr15-ci-cf0b6ce12eb7d479` | 0/4/0 | `9e0e0ad4464addc4962afb9e86742c7b87367b3d9f6ecb96857041afa954e3f7` |

Source96 tests are still ongoing at this additive entry. All previous originals and exact-owned cleanup records remain retained; current source and this ledger will be independently inventoried. No secret, public scientific manifest, or historical archive identity has been replaced.


### Source97–106 host export and closed-census continuation (development, 2026-09-08 UTC)

Source97 (`c0bfbde039ac979acd834d71e1fcb083654462446da9b6db82778ef1fac9fa58`) produced two separate container results: `gic-pr15-ci-593557c53e993ebc` 99 component passes in 8.361 seconds, and `gic-pr15-ci-b429e2cd1d903eac` all four joined parameters passing in 796.423 seconds. The positive parameter executes all four fresh retained clients, the actual Task A continuation decision and B pair, finalizer/evaluator and terminal cleanup. The other parameters separately retain normal no-answer/score-zero handling, intentional nonzero workload failure export, and attach-output denial. These are not a combined 103-test run or a final committed-source gate. All four original joined trees and guard journal were preserved by an incremental 148,256,256-byte payload with verified prior references; the three exact-owned CI volumes are absent.

Source98 was frozen but not run. Source99 (`89390978270102c4c49c5516fb1910fcb7d89812e274ef23b5bbf62b89e2e013`) additionally distinguishes the immutable runtime protocol accounting snapshot from the actual closed-host attempt census, reconciles only previously granted remote capacity, and hardens control export copies through retained held descriptors. Its 104 component tests passed in 8.501 seconds (`gic-pr15-ci-1772e4f8a0875670`). Its four joined tests failed in 481.211 seconds (`gic-pr15-ci-bc4bf2f6b5ea197b`); source remained unchanged. The first three reached actual condition completion then failed in `_attempt_export_control_sources -> hold_sealed_artifact -> _open_relative_no_symlinks -> descriptor_open`: `offline openat used an unbound directory descriptor`. The newly held source path uses `os.dup(root_fd)`; the offline audit shim did not propagate the already-recorded directory identity to the duplicate. Cleanup correctly refused a missing off-host export acknowledgement. The attach-denial case also lacked a shared sealed failure record. These failures remain original evidence, not expected passes. Its four original trees/guard journal were incrementally retained (132,742,656 bytes), and all three exact-owned CI volumes were removed and absence verified.

Source100–105 are unexecuted intermediate snapshots. Source100's broader changed-Python Ruff check exposed two pre-existing unmarked regex strings in the dirty cleanup regressions; source101 marks them raw without changing assertions. Formatting (53 files), four-module mypy, and diff checks passed; the Ruff failure is retained separately. Source102 narrows only a named archive-failure test window to zero and sends actual encoded chunk counts through the real archive writer; it does not fabricate a successful receipt or enlarge shared capacity. Source103's new counter-diagnostic label had a line-length lint failure, corrected in source104 before any execution. Source105 adds type validation for consumption-only capacity and active malformed/zero-window tests.

Source106 (`33d0ed4dcdddaab5b47dc2b41861fc1b0c4036da76c325fea30320487ff9350a`) repairs only the offline descriptor shim: a real duplicate of an already-tracked exact directory inherits that identity after fstat verification; unknown/replaced directory descriptors fail before duplication. It retains the actual held-file consumer and strict ownership checks. Three active primitive tests exercise real duplication and missing/wrong-inode rejections. The original positive and workload-failure parameters stay active; the new `transaction-export-output-denial` is separate. A joined counter diagnostic preserves actual runtime event totals, closed-host census, disjoint controller observations and grants; it is explicitly not writer-admission proof. Source106 components/joined execution are pending at this entry.

Remaining: full R1–R6 negative/coupling/cleanup matrices, complete output-role reconciliation (including policy scope of control records outside the attempt census), immutable source/test ancestor, non-circular current receipt descendants, final exact-commit container full/parity/static/privacy/site gates and native-only coverage. No finding is closed. Product HEAD remains a98b4b875ab4d101709d62bc7222b5c90681a893; these are dirty snapshots, index empty. No product commit/push, science/manifests change, V17, real experimental effects, hosted CI or shared-runtime operation. Private evidence publication remains separately authorized; it is not product readiness or independent approval.


### Source106–109 closeout and new GIC storage I/O blocker (2026-09-08 UTC)

Source106's completed joined run `gic-pr15-ci-5995b433abd7924a` has four passes and one failure, zero skips, 850.645 seconds, unchanged source. The original positive four-condition, no-answer/checkpoint-stop, nonzero-workload failure/export and attach-denial paths pass, including held-copy export and exact closed-host accounting assertions. The new archive-denial parameter failed before its intended writer: its mode was missing from qualification setup. This is setup failure, not evidence of successful denial. Five original workspaces and the guard journal were incrementally preserved (178,658,816 bytes); their three exact-owned volumes are absent.

Source107 (`8d5f286194e7e93d8574c7866d4505255265120f0f11adcbb740f6b1380cd6e2`) corrected that setup list. Its broader guarded run `gic-pr15-ci-9c7a08250d4623f1` produced 339 passes, five failures, zero skips in 161.005 seconds. Four existing terminal component cases supplied an incomplete request without `inputs`. The archive-denial case still failed before the archive boundary because the runtime's explicit fixture-scenario list lacked `export.output-denial`. Its original runtime stderr and carrier error are retained; zero archive bytes alone did not prove denial. The failed runtime also exposed a separate pre-handoff cancellation failure: essential-copy admission tried to request capacity over the cancelled channel. All original failed workspaces and guard journal were retained (30,918,144 incremental bytes) and the three exact-owned volumes are absent.

Source108 (`4996420f408f74b76fdf9d97df743339ce5929a24721fe58668e1354be50cc1b`) adds the request's empty input map and the explicit export-fault scenario, without changing successful workload effects. `gic-pr15-ci-f1d3ed958faccd98` passed all 344 selected tests, zero failures/skips, 144.227 seconds, unchanged source. The new export-denial parameter now reaches the actual bounded archive writer: a zero consumption window rejects its real encoded chunk, leaves the archive at zero bytes, creates no export acknowledgement, admits no later condition, and leaves cleanup honestly unresolved. It remains distinct from the positive and intentional-workload-failure paths. Original evidence was incrementally retained (31,563,264 bytes); the three volumes are absent.

Source109 (`353db88966b44702de34952c0c40381832879e3463a9ddaa1da58ce9d3e6415b`) addresses the observed cancelled-before-handoff copy path. `_ConditionSessionBridge.admit_path` consumes only its already-granted failure reserve after cancellation instead of retrying an unavailable transport. The existing actual essential-copy regression now covers both pre- and post-handoff cancellation, allowance conservation and denial before destination creation. This change is NOT behaviorally validated by a collected source109 result.

The source109 component invocation `gic-pr15-ci-f1589a0e7e01f3f1` reported container process exit zero, but collection failed with `open .../local-logs/container.log: input/output error`; exact-ID removal then failed with `write /var/lib/containerd/io.containerd.metadata.v1.bolt/meta.db: input/output error`. A bounded recovery inspection found the same owned container in `dead` state with that error; no result-copy attempt followed the failed exited-state admission. No JUnit/gate report was collected, so neither a test count nor pass is claimed. The GIC VM was stopped and its exact Lima state verified `Stopped`. The latest container's removal and three volumes' absence remain UNRESOLVED and their ownership records/disks are retained. No additional container was launched, runtime restarted, storage enlarged/repaired, or shared runtime contacted after this failure.

Host observations at 2026-09-08T04:52:39.404593Z: startup available 41,442,959,360 bytes; verified outer volume 641,551,335,424 bytes; protected image filesystem 47,136,374,784 bytes. These do not establish guest filesystem health/capacity or explain the I/O error. Do not infer disk-full, physical-disk damage, or recovery from these figures. GIC-dependent validation is blocked pending diagnosis of its exact metadata/log storage failure; no automatic repair, replacement image/profile, cap expansion or shared-runtime fallback is authorized.

Source-only progress is preserved. Remaining R6 control-writer coverage outside the attempt census, complete R1–R6 coupling/negative/cleanup matrices, immutable ancestor and non-circular receipts, and final full/parity/static/privacy/site/native gates are still unfinished independently of this new infrastructure blocker. No R finding is closed, product commit/push made, or scientific/authority state changed. Hosted CI remains not run by owner instruction. The next private handoff will distinguish 106/108 observed successes from 107 failures and 109's uncollected result; source109 is not a passing final gate.


### Return to engineering; one fresh isolated CI lane (2026-09-09 UTC)

Owner direction defers optional Source109 recovery. Collection failed; its test and
post-test source-integrity outcomes remain UNKNOWN and are excluded from successful
validation claims. Storage cause and old container/three-volume absence remain
unresolved. The affected original and its verified same-store ciphertext copy remain
retained and unused; no further recovery or old-runtime resume is authorized. Their
exact locators remain in the existing private bootstrap/preservation records. Latest
maintenance stop: private evidence adc89c29d5e4492ae61a5b0321595364c880b0dc,
manifest b5208cddc25c951b0bda386b329556e436b5a5fc46c30f8761f07cbecdd5370a.
Its nonsecret 0644 plan inside a 0700 parent stopped preparation before image access;
it is neither a new disk fault nor proof of credential disclosure. Recovery helpers
remain unqualified and are not included in product source.

Intake local/remote/PR head and tree match a98b4b875ab4d101709d62bc7222b5c90681a893
and b75ce4579c934440c7679cbf289b3294d01d6caf; required base remains
f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2. PR remains draft/open/unmerged,
auto-merge disabled. All 68 dirty paths match source110 preservation inventory
abe6998d6690ffd19061336675e0379669e8e9a3c1d17577da8a42795fe8f581; referenced
payload bytes were verified. The ordinary named-file checkpoint preserves unvalidated
work, not a final implementation ancestor or receipt certification. Source106's four
joined passes plus setup failure, source108's 343 components plus archive-denial pass,
unknown source109 and unexecuted source110 remain separate.

Current work/DoD: preservation/checkpoint in progress; one new gic-pr15-clean-ci lane
and operational storage smoke not started; R6 campaign start/entry/cleanup-control
writer admission and exact reconciliation partial; complete R1–R6 negatives/coupling
matrices partial; immutable ancestor/noncircular receipts/final exact-commit container
and parity/static/privacy/site gates not started. Independent review remains pending.
New lane permission is limited to the owner's declared separate encrypted topology
and finite budget. It is not a cure for the old I/O fault or physical redundancy.
No live/scientific authority, V17, hosted CI, shared runtime, merge or self-approval.


### Fresh lane and pilot/control writer repair checkpoint (2026-09-09 UTC)

The ordinary checkpoint 80a6ed54db31d3346d4c4dff43e8b8353ef64c70 preserves the
previous 68-path repair. A separate fresh encrypted gic-pr15-clean-ci lane passed
operational storage and containment smoke. It uses native ARM64/VZ, 2 CPUs, 6 GiB
VM memory, 20/32 GiB root/data settings and a non-root 2-CPU/4-GiB/512-PID offline
container. Its checksum-bound bootstrap and measured runtime identities are limited
CI assurance, not T07/live qualification, physical redundancy or an old-fault cure.
Old images/keys/recovery tools remain retained and unused; Source109 stays UNKNOWN,
excluded from successful validation claims, with recovery deferred and old resource
absence unresolved. No original/copy integrity sweep or old runtime access occurred.

Production now establishes one retained condition accountant before pilot start and
empirical-entry state writers. Host admission covers declared pilot/journal roots
plus attempt roots. Pilot state and early cleanup journal writers admit before
mutation; denied writes preserve bytes. Unused capacity and bounded failure reserves
carry forward under unchanged policy caps. The shared controller counter records
actual successful write syscall bytes; an independent full-root signed census must
equal written bytes minus the exact retired prior-file bytes of admitted replacements.
The original red joined run ab0002edcf0f2bd0 failed because essential sealing clears
a longer reservation and legitimately shrinks mutable state. Net occupancy is not
a monotonic writer count. The correction neither retrospectively grants capacity
nor clamps/ignores decreases; partial admitted temporaries remain accounted.

Validated essential infrastructure failure now preserves actual exit status, including
zero, without task acceptance or evaluator eligibility. Actual answer/None, source
binding, held failure export and mutation assertions remain active. Attach-output
denial no longer assumes a particular process termination code. Its actual retained
status must agree across the source completion, returned outcome and failure summary.

The explicit CI guard now allows real, tightly scoped scratch-Git fixture creation
and detached switching to full commit identities, with hooks/signing/templates/
protocols/automatic maintenance disabled and Git environment overrides removed.
Foreign/network operations and caught forbidden dispatch still fail. Actual PathLike
arguments are supported. The inner gate console now rejects over-cap growth and
terminates/reaps its owned child on cap/timeout; previous runs lacked this inner-log
pre-growth enforcement although their retained logs stayed below the limit. This is
not arbitrary native-code containment or complete descendant-cleanup proof.

These are separate source-bound development runs, not combined green counts:

| Transaction | Passed | Failed/errors | Skipped | Input manifest SHA-256 |
|---|---:|---:|---:|---|
| `gic-pr15-ci-02f8b7bb6f62f169` | 366 | 0 | 0 | `af2ff8e0c951b6b9f6122cd5d99c37178c81198d2bbe127e8893d6448aff2d16` |
| `gic-pr15-ci-1422d5dbe1b2b5a3` | 448 | 3 | 0 | `0ab2b1bc58cd4e70d7a3eb712cba62e2a87d1de24841a7777e5dd666fa22771b` |
| `gic-pr15-ci-59693514fbcc7d4c` | 271 | 0 | 0 | `e8125d17bc2f39c857f35f6950e30c59b7bd156d1599fde642651e4fe34218b5` |
| `gic-pr15-ci-6f69df84b547f406` | 265 | 1 | 0 | `f9338c6cc7c4430c64c76d7431e1d0ea902119f1a92b6cac8f04a1a5b6798410` |
| `gic-pr15-ci-9e852336031aaf62` | 148 | 1 | 0 | `b23444d3ca1a07b80393779b9228bb973cf43379536869987bb6c332bb41e3b3` |
| `gic-pr15-ci-ab0002edcf0f2bd0` | 366 | 2 | 0 | `42f7e3f0104a6eff3bc21043850173885d367a01b9a81d2da4f374520d177d01` |
| `gic-pr15-ci-aeb66c00c38d3de2` | 362 | 0 | 0 | `360a22e9ab17069312d45a7bee61be1f6d71da5108db7218c5da6b970b7fa334` |
| `gic-pr15-ci-b2cc3f41db2a577b` | 270 | 1 | 0 | `82e0f878f9a70530625894c12adff5e1f8a5b5f75cc34bc13de15e0109f7277a` |
| `gic-pr15-ci-bd3ab8141fc393e4` | 205 | 0 | 0 | `59b677cbc9f6a1ef33ba86549bb76a7fb6eda5f85ff1343be245b6aa663182e8` |
| `gic-pr15-ci-c01e446814a19af8` | 357 | 5 | 0 | `2ff46482114699d8a3980e6e69d82c7275d2f0b77c818242e048ed301482fe41` |

The b2cc3f41db2a577b batch passed all five joined parameters (four-condition
positive; intentional failed-condition export; no-answer/checkpoint stop; attach
output denial; export output denial), but raw pytest remained failed by the scratch
detached-switch denial. Four full closed trees and all five terminal/trace/candidate
summaries were collected; the late additional fifth-tree capture stopped before
Docker dispatch after normal completion. Earlier 1422d5dbe1b2b5a3 retains five full
closed trees at its separate source binding. No missing original is reconstructed.
The final 59693514fbcc7d4c component run passed 271 tests, zero skips, source unchanged,
on image sha256:0928021614063435abaebc9771282edd681aa7dfe1e2960c1a86dda61b174a3a.
The latest five joined passes used image
sha256:159d676bb3d2f85a6167b5a0006137ac70cce5ef6585d13c9b6cc2cd42c96fcb.
They are not exact-head validation of a later checkpoint or the newer image.
Ruff/format/diff checks passed on 16 changed Python files and targeted mypy passed
on three production modules; these are native source-only checks, not native product
validation. Required Python/uv/Quarto and dependency locks remain unchanged.

R1–R6 remain PARTIAL. Concrete next seam: campaign-wide provider-entry/final cleanup
and control-journal publications outside the condition callback; CleanupExecutionRequest
currently carries no writer observer, and retained cleanup_transaction/provider
closeout_campaign need shared admission without another policy owner. Full controller
cleanup-prefix/corruption/idempotence and timeout/disconnect/reaping matrices, plus
causal phase/runtime hook-disable coverage, remain incomplete. The historical T07
launch-request missing in the full pilot module stays explicit; it is not a new
deselection and inherited status has not been established by exact-base parity.

No final implementation ancestor, noncircular V16 receipt descendants, exact-commit
make ci-check, full per-node parity, control/privacy/site or required native-only
product gates are claimed. The exact five existing private deselections are unchanged.
This next ordinary named-file checkpoint preserves engineering work; only its added
ledger text differs from the final focused source snapshot. Product remote/PR remain
a98b4b875ab4d101709d62bc7222b5c90681a893, draft/open/unmerged, auto-merge disabled;
no product push is authorized by these partial results. Private handoff/closeout
records remain outside this source identity. Independent review PENDING;
t09_remote_execution_bridge_review_repair_blocked.


### PR15-R6-CAMPAIGN-ADMISSION-01 checkpoint (2026-09-09 UTC)

This is a partial same-branch engineering increment after checkpoint
8ee06de649d599ffd5ebaac60735fd6909de0551, not a final implementation ancestor.
The shared ProviderBudgetBoundary now admits aggregate-only campaign writers before
provider entry without an empirical run identity or clock. Its existing 64-MiB
essential-cleanup reserve is charged within unchanged aggregate policy before entry;
unused grants and actual observed write bytes carry into all four condition boundaries
and cleanup. This is capacity reservation, not a policy-budget increase or observation.

The campaign_output capability surface contains no policy owner. Production connects
parent provider record/journal/copy and metadata writes plus parent cleanup journal/
receipt writes to that boundary before byte growth. Actual partial write counts survive;
unused grants are retained, expired capabilities and aliases are rejected, and caught
policy denial blocks later condition entry while prefunded cleanup stays available.
Historical unbound callers remain distinct from the active production context.

The retained joined adapter now handles the actual provider-entry/pre-transfer prefix
using durable exact ownership, observed absent planned transfer/credential paths and
retained provider closeout validators. It creates no host phase or freeze receipt.
The terminal closeout consumer supports source-validated idempotent reconciliation
without another provider request. The new joined prefix asserts zero consumed conditions
and then exercises that consumer with redispatch forbidden and unchanged accounting.
This is not the entire interrupted/resumed full-controller cleanup matrix.

Separate source-bound development outcomes (all native linux/arm64 on immutable CI
image sha256:0928021614063435abaebc9771282edd681aa7dfe1e2960c1a86dda61b174a3a):

| Run suffix | Passed | Failed/errors | Skipped | Input manifest SHA-256 |
|---|---:|---:|---:|---|
| 4b057810ac47ab58 | 126 | 26 | 0 | 6ace77f8653c35b4632d5e2254c92dc4e2c956215bec47df931c21af522ce247 |
| d76b6a23f0394a46 | 152 | 0 | 0 | 7e2682f233d99acfd07f4dcd860ea31fb309655377044e7de111f66fff682981 |
| 2703a45113a794ae | 0 | 2 setup errors | 0 | a81e000996bb2be7fc7f68937c9c5c270e9996a926a938556cea41e26302d8a4 |
| 51d538fb4cce3872 | 1 | 1 | 0 | a4a6acb4c36085e41633a219f48cf20134f3e177ebe0173a5f24327f58204e6f |
| 6edb4f1b97228816 | 157 | 0 | 0 | c00cbbaa803c52562d0e64e49a16156c649a93f7a80f80353f57f98ae06cbc25 |
| 3e2ddfa84e07992c | 163 | 0 | 0 | eeebf11442aeb4734acfd46aa751bf7aa4192c2f228c76dea3ef21ece861635e |

The first run exposed new component fixtures lacking explicit launch-capability paths
and an assertion omitting reserved cleanup capacity. The first joined setup lacked the
new module in the explicit candidate closure; it now has 354 members. The 51d5 positive
four-condition transaction passed; its new pre-transfer case reached verified cleanup
but failed a test assertion incorrectly expecting four conditions. Originals remain.
The final 163-test run passed all five original joined parameters plus the new prefix
and 157 components in one batch, pytest exit zero, 1030.192 seconds. Six closed transaction
trees (1450 files, 11822925 bytes) were retained inside the verified 16049664-byte export.
All 894 source members matched the snapshot before this additive ledger entry. This
entry is not an exact-commit CI certificate of its subsequent checkpoint.

Active source assertions: test_r6_campaign_actual_writers_shared_admission_precedes_growth,
test_r6_campaign_partial_writer_keeps_actual_prefix_and_unused_grant,
test_r6_campaign_capacity_conserved_across_four_condition_boundaries_and_cleanup,
test_r6_campaign_denial_is_sticky_but_prefunded_cleanup_survives, and alias/expiry
regressions in tests/control/test_remote_transaction_review.py. The retained candidate
bootstrap requires actual provider-entry and cleanup-journal admission observations.
The pre-transfer trace records 61 parent writes and 50862 observed bytes; cumulative
granted bytes 67137869 include unused cleanup capacity, not additional observed output.

R1–R6 remain PARTIAL. The next seam is explicit campaign output admission across the
retained child-process cleanup/control boundary: CleanupExecutionRequest still has no
such capability and the parent ContextVar does not cross processes. The trace labels
its parent coverage. Full writer census, child admission, required cleanup corruption/
interruption prefixes, controller timeout/disconnect/reaping and exhaustive hook-disable
matrices remain incomplete. No full final gate is spent on this partial increment.
Current V16 receipts, immutable implementation ancestor, exact-base parity and required
full control/static/privacy/site/native-only product gates remain NOT RUN.

Native source-only Ruff/format/diff checks passed on ten changed Python files; mypy
passed six production modules with cache disabled. Initial cache-access diagnostics
are retained as tooling failures, not guest I/O failures. Fresh-lane smoke
782647804ef2f5c6 passed; each finished run exported results before exact-owned cleanup.
The resumed encrypted image used the existing protected descriptor. A redundant
uncredentialed imageinfo query timed out and prompted the owner for a password; the
owner was advised to cancel. Actual image-encrypted mapping checks then verified the
same attachment before profile start. That deviation is retained and the query is
not a future resume method. Closeout and publication records remain external.

The earlier b2cc XML derivative is corrected append-only by sanitizing values before
serialization; all 271 original outcomes (270 pass, one failure) remain identical.
No test rerun or replacement original is claimed. New source deltas were independently
preserved (11 files, 1342104 bytes, inventory SHA-256
687cb1bb09283a986317dc2e2a80a747da3ceb04218053c35b02eb90c31e2d05).
Source106/108 remain separate historical development evidence. Source109 is UNKNOWN,
excluded from successful validation, recovery deferred; Source110 was unvalidated at
its original checkpoint. Old images/keys/recovery tools remain retained and unused.
No new real experimental activity/cost, shared-runtime access, science change, V17,
product push, PR mutation or merge occurred. PR head remains a98b4b8... pending full
completion/publication gates. Independent review PENDING;
t09_remote_execution_bridge_review_repair_blocked.


### PR15-R6-CHILD-CLEANUP-ADMISSION-02 — in progress (2026-09-09 UTC)

Start: ordinary checkpoint 1c78005a52804c675a8fea2e8336a048f0709d6b,
tree 11edd331697cd1c5f003ab5e5bb5aafe19fdfa63; reviewed separately with
CHANGES REQUIRED, all R1–R6 partial. This increment carries explicit campaign
cleanup writer authority through CleanupExecutionRequest and the retained child,
with one authoritative reservation/observation owner, bounded remaining deadline,
pre-growth write admission, conservative failure/disconnect accounting and exact
owned cleanup. It must preserve all six joined cases, add meaningful child-binding
and overlap/replay/partial/deadline negatives, and export relevant parent raw source
records before future ephemeral cleanup. The earlier omitted originals are not
reconstructed. The final full gate/product publication remain deferred.

DoD status: explicit child authority, actual writer connection, conservation/census,
deadline/reaping and joined coupling — in progress; next focused evidence pending.
No new runtime profile, image, key, policy budget or scientific authority is created.

### PR15-R6-CHILD-CLEANUP-ADMISSION-02 — focused checkpoint (2026-09-09 UTC)

The typed CleanupExecutionRequest now carries a single-use campaign cleanup output
capability to the actual retained host-cleanup child. Campaign/source/tree/candidate,
owned output roots, phase/attempt and original cleanup handoff/deadline remain bound.
Two inherited pipes reuse existing bounded bridge I/O; the child consumes the existing
shared controller reserve and cannot create a policy budget or condition identity.
Actual host/pilot/journal/receipt/phase/environment-state writes request finite capacity
before growth. Legacy callbacks select one owner in a bound campaign. Actual partial
write consumption, unreleased grants and independent publication occupancy are distinct.
The transaction metadata census rejects changed files outside admitted paths; it does
not authorize writes retrospectively or treat snapshot occupancy as cumulative writes.

Separate original development runs (native linux/arm64, one pinned clean-lane image):
- 0773149def0fcf31: 10 passed, 14 failed, no skips/errors; exit 1. Missing test import/
  parent directory and caught socketpair dispatch were retained. Inherited pipes fixed
  the actual cleanup transport without loosening the effect guard.
- 83cda34ed96cc0b7: 187 passed, one failed, no skips/errors; exit 1. The new disconnect
  negative expected verified cleanup incorrectly. Only that new assertion was corrected.
- cf4b7297517b0788: 193 passed, four failed, no skips/errors; exit 1. Independent census
  exposed unadmitted host-cleanup-receipt.json and offline-environment-state.json writes.
  Actual write_phase_receipt and ImageCommandChannel.save_state now pre-admit growth;
  the latter persists under the declared retained-phase-traces control-output root.
  The full transaction census remains unchanged in coverage; no budget was increased.
- 17a517aad47638fb: 202 passed, zero failures/errors/skips; pytest exit 0; 1160.846 seconds.
  This is 195 components plus seven separate joined parameters, not a sum of earlier runs.

Final focused input manifest SHA-256:
cc8672a022e69ff1251ce3e591841f07054a7bc06d1e938bf3021f24f3fe3f27.
It binds all 894 tracked source members; candidate closure remains 354 explicit members.
The post-test source check passed. Source/test bytes match the sealed dirty snapshot
rooted at 1c78005; only this additive ledger entry follows it. No exact-final-commit CI
certificate is claimed. Image remains
sha256:0928021614063435abaebc9771282edd681aa7dfe1e2960c1a86dda61b174a3a,
Python 3.11.14 / uv 0.11.7 / Quarto 1.9.38 and unchanged dependency pins.

The positive transaction controller-transaction-gja19n1o executes all four fresh runtime
clients, retained first-pair checkpoint, finalizer/evaluator and verified cleanup. Its
cleanup child recorded 62 protocol events / 20 allowances / 87606 actual written bytes,
with matching independent publication checks and zero uncovered census writes. Child
exit was zero, it was reaped and capture threads stopped. Intentional condition failure,
no-answer, pre-transfer, attach denial and export denial remain separate assertions.
The added cleanup-carrier disconnect consumes only the first condition, preserves
unresolved cleanup, reaps the child and does not fabricate a terminal receipt. The
existing export-denial path preserves three child grants / 29387 observed prefix bytes
with a failed acknowledgement and unresolved cleanup. No grants are refunded by failure.

Relevant actual parent entry/closeout records and full journals were exported before
exact-owned ephemeral cleanup: final batch 457 parent records / 2419875 bytes, including
112 entry-source and 40 closeout-source files. Earlier omitted originals are not
reconstructed. Full final export: 21227520 bytes, SHA-256
cd9b87f85bcd630ddf3dd8a599b3b4c8e74676671e55a8664aacecbd21c5474b.
The private handoff supplies readable source deltas, complete source transports, original
record hashes and labelled sanitized derivatives. An initial local projection looked
in the wrong exported subtree for child receipts; its corrected derivative references
six already-preserved originals. That projection correction is not a test rerun.

New source preservation: 13 Python files / 2892456 bytes; inventory SHA-256
450286f81be78092a260482410f648aa106c61ff2c24bab16008ee56c858d21b.
The additive ledger is separately preserved and bound in the ordinary checkpoint.
Ruff/format on all 13 changed Python files, mypy on eight production modules, and diff
checks passed. These are native source-only checks, not the complete native-only gates.
Clean-lane containment/storage/export smoke e07ad19be62109d3 passed. Resume used the
existing protected descriptor and verified encrypted mapping; the redundant uncredentialed
imageinfo query is absent. No password value or derivative was displayed or published.

R1-R6 remain PARTIAL. Active assertions are mapped in the private engineering scope
review; missing complete cleanup-prefix/corruption/interruption/restart, controller
backpressure/descendant/reaping and exhaustive hook-disable/writer-role matrices remain
explicit. The census is not a complete transient-write or adversarial filesystem audit.
Complete current receipts, immutable implementation ancestor, exact-base parity, final
make ci-check and full control/privacy/site/native-only gates remain NOT RUN. No product
push or PR change; independent review PENDING. Runtime closeout/publication evidence is
external to this source checkpoint and must be read for its actual disposition.

Source109 remains UNKNOWN, excluded from successful validation, recovery deferred;
old storage cause and old container/three-volume absence remain unresolved. Old images,
keys and recovery tools remain unused; no shared Desktop/Lab/Biblos access. Authorized
outer clean-lane VM/native-image activity is distinct from guarded inner environmental
doubles and zero real experimental/provider/model activity or new scientific cost.
Frozen EXP-0001 inputs, order, budgets and zero retries remain unchanged. No V17, live
execution or merge. t09_remote_execution_bridge_review_repair_blocked.

### PR15-R5-CLEANUP-OWNERSHIP-03 — in progress (2026-09-09 UTC)

Start d21e53bec52c21f59ba39e358ec8370e91df8259, tree
8a844376ad6290f4decd1880db2c7ca06dd93b04; independent review CHANGES REQUIRED.
DoD: contained red characterization of descendant-held capture and first/second
capture-start failure; exact process/capture/descriptor ownership; one remaining
cleanup deadline including teardown; preserved primary/secondary failures and
conservative grants; partial-start, post-grant/ack-interruption and joined controller
regressions; all seven existing joined paths; bounded original export and closeout.
All items in progress. No full final gate, product push or PR mutation is authorized
for this partial increment. All R1-R6 remain partial. Source109 UNKNOWN/excluded/
recovery deferred; old/shared runtimes remain unused.

### PR15-R5-CLEANUP-OWNERSHIP-03 — focused repair checkpoint (2026-09-09 UTC)

Starting parent d21e53bec52c21f59ba39e358ec8370e91df8259, tree 8a844376ad6290f4decd1880db2c7ca06dd93b04.
Remote/PR remains a98b4b875ab4d101709d62bc7222b5c90681a893; required base
f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2. This is an ordinary preservation
checkpoint, not the final implementation/test ancestor or an independent approval.

The retained cleanup and related condition carriers now share RetainedProcessOwner.
The unreaped dedicated-session leader anchors exact process-group termination;
PID/PGID/SID and child ownership are checked before group signals, with no signals
after reaping. Bounded nonblocking capture runs in the bridge caller, eliminating
the capture-thread startup/ownership gap. Partial pipes, output files, Popen streams
and capture registrations have one owner. One original monotonic deadline reserves
teardown within its allowance instead of adding fresh one-second waits. Errors from
one release do not skip the remaining releases or replace the primary failure.
Cleanup pre-funds its failure transcript before allocation and reconciles only after
owned process/capture shutdown. Existing shared grants and all writer caps are unchanged.

Original contained red gic-pr15-ci-219e9c3395678f19: four failed nodes, pytest exit 1,
input a7715896e766d804b08070f2d28e7c7946ebc455ca58a02b64284b41898029c5.
First/second capture-start failures leaked owned outputs, masked the initial error
with an unstarted-thread join, and omitted the failure receipt. Descendant-held
pipes retained two workers and returned after 2.21864/3.27722 seconds against 0.8.
The regression's separate containment released its exact deliberately stranded
resources. Originals remain preserved; no historical red result was fabricated.
Separate first green 572144924360c82b: four passed; original errors retained,
no live recorded descendants/capture workers/open outputs and elapsed below 0.8.

Separate 71704bea9e7aae9c: 11 passed / one failed, including a successful positive
four-condition transaction. The new descendant fixture's wrong request-path lookup
was denied by the real output authority; its missing probe assertion failed.
Separate ca819c8d158f9e38: one joined descendant-interruption pass / three component
fixture setup failures from absent required control roots. These were corrected as
fixtures, not relabelled product defect reproductions. Separate b36c607900a029b9:
211 component passes, zero failures/errors/skips, 11.462 seconds. Do not add runs.

Two preparation-only attempts 1101f3c1c94500e6 and 55fed57ded91977c stopped before
pytest: the added helper-hash check was placed after test-user ownership transfer,
then before required initial root normalization. The corrected existing preparation
now verifies helper bytes between its established ownership transitions; no new
privilege or permission was added. Exact failed-preparation logs/source identities
and ordinary exact-owned ephemeral closeouts are preserved separately. These were
setup ordering defects, not storage-I/O failures. Earlier unexported cleanup console
originals are not reconstructed. Final export explicitly retains the two bounded
cleanup console files alongside parent/child JSON journals.

Final focused run gic-pr15-ci-338d696e54f68bfe: 219 passed (211 components and eight distinct joined
parameters), zero failures/errors/skips, pytest exit 0, 1295.213 seconds.
Input-manifest SHA-256 d1e5f4f27ce2a073d19a41e03aa6d5a7f4eef781a90e19a3f393aff45e54fc32; 894 source members and
354 candidate members. The guest source-integrity check passed; all current source
bytes matched the sealed snapshot before this additive ledger entry. All five changed
Python files match that snapshot. Final source archive/result identities, complete
per-node JUnit, commands/exits, actual original/derivative bindings and source maps
are in the private external handoff. This is dirty-development evidence rooted at
d21e53b, not a final-commit make ci-check certificate.

The assigned matrix covers both capture starts, both pipes, both output allocations,
Popen, parent-pipe close failure, leader exit/termination with inherited pipes,
TERM-ignoring descendants and blocked pipe writes; secondary finalizer failure and
changed group identity; and actual condition-carrier partial starts. The new joined
case runs retained cleanup/writers before a source-bound descendant and partial next
frame. It preserves prior grants/actual observations, no fabricated terminal ACK,
nonzero child outcome and unresolved cleanup, with no later condition and exact
process/descriptor release. All seven prior joined terminal outcomes remain active,
including four fresh runtime clients, actual finalizer/evaluator/checkpoint and
normal cleanup. One campaign is not assembled from component successes.

New named source preservation: five Python files / 619774 bytes; inventory SHA-256
a33d2eae8fe9bbb58d167943a3e75b3943b5b846bf45f60fcee397a59e51317d. The additive ledger is separately retained in the checkpoint record.
Targeted Ruff format/lint and diff checks passed. Mypy success is reused only for the
unchanged exact remote_bridge.py source hash. These are native source-only checks,
not the full native-only acceptance gates. Image remains
sha256:0928021614063435abaebc9771282edd681aa7dfe1e2960c1a86dda61b174a3a,
native linux/arm64, Python 3.11.14 / uv 0.11.7 / Quarto 1.9.38 and unchanged locks.
Clean-lane containment/storage/export smoke 39f5cd738ec28fd9 passed. Protected-descriptor
resume verified the existing encrypted clean mapping; no interactive imageinfo call.
Runtime closeout and private publication are external records, not inferred here.

Assigned ownership regressions are demonstrated; independent review is PENDING.
R1-R6 remain PARTIAL: exhaustive cleanup-prefix/corruption/resume, full controller IPC,
hook-disable and writer-role matrices remain incomplete. Owned inherited process groups
are tested; arbitrary session-escaping descendants or a hard preemption guarantee for
blocked native filesystem calls are not certified. No final source/receipt freeze,
current V16 regeneration, exact-base parity, full make ci-check/control/privacy/site/
native-only gate, product push or PR mutation occurred in this increment.

Source109 remains UNKNOWN/excluded from successful validation; recovery deferred.
Old storage cause and old container/three-volume absence remain unresolved. Old images,
keys and recovery tools remain unused; shared Desktop/Lab/Biblos are untouched.
Authorized outer clean-lane infrastructure and its existing generated credentials are
separate from guarded inner doubles and zero real experimental/provider/model activity.
EXP-0001 science, model, evaluator, data, task order, budgets and zero retries remain
unchanged. No V17, live grant, new scientific cost or merge.
t09_remote_execution_bridge_review_repair_blocked.

### Remaining coupled R1–R6 development matrix — in progress (2026-09-10 UTC)

Start d7f0921955aec8183a754646030cd6220b96d80d, tree
4a8206bb18ff5eaa6380cd7c9e5ecec2810a45ff; five ordinary descendants and
clean worktree/index verified. Remote/PR a98b4b8 and required f56dfc2 base
unchanged; open/draft/unmerged/auto-merge disabled. Joseph authorizes the
remaining identity/answer, durable controller cleanup-prefix, causal-hook,
controller IPC/lifetime and complete writer-mechanism development matrix.
The finite machine-readable requirement/source/node map is held in protected
development scratch and will accompany the single final private handoff.
All rows begin not-started pending reuse audit/new exact-source evidence.
Prior 219-pass focused development evidence and all original reds remain intact.
Scope: coherent source/test repairs, guarded focused container iterations and
one final matrix-focused selection. No full ci-check, final V16 regeneration,
product push/PR change, new runtime, Source109 recovery or independent approval.
Only existing gic-pr15-clean-ci may resume under its identity/resource/isolation
checks. Source109 UNKNOWN/excluded/recovery deferred; old/shared runtimes unused.
Assembly skill applies; explicit no-delegation instruction controls. Independent
review follows this assignment. No frozen-science change or real model cost.

#### Coupled matrix: unvalidated implementation checkpoint

The new joined prefixes exposed three concrete source defects: freeze publication
had no durable failed-before-publication continuation; the controller inferred a
failure phase from the preceding adapter audit entry; and interrupted cleanup
removed its retained credential before the same bounded continuation could use it.
The exclusive publisher now records an actual unpublished failure, the controller
tracks its selected phase explicitly, and final release owns credential destruction
when cleanup is interrupted. Missing published evidence still cannot mint absence.

Cleanup writer reconciliation now records each admitted temporary and exact old-file
retirement. Its independent full-root census compares occupancy change with actual
writes minus those retirements and baseline removals. Grants are not refunded.
Partial writes and retained temporaries remain counted; changed replacement identity
fails before replacement and unexplained census changes fail reconciliation.

Development run gic-pr15-ci-d328a2465cf11b05 passed 27 nodes (four joined cleanup
prefixes plus 23 actual-writer cases), pytest exit 0, input-manifest SHA-256
04c00d5e8380a9b9400ccdcfc57009da3ea7166834e37c0c460b4ffacbc9aee0.
Its exact-owned ephemeral resources were removed after verified export. Earlier
runs c590e93651f01d77, 3fb67325e02605d3 and 2ebf2eeb092162b1 retain their separate
red assertions, source archives and exported evidence. Fixture-parent creation,
clock binding and cleanup-prefix assertions were corrected without replacing
production phase results. No run is labelled validation of committed d7f092.

The broader downstream/coupling/IPC selection gic-pr15-ci-85d6229ed26d11f9 is still
running on input-manifest SHA-256
7a42acbe3dd980f01bbe9f64e697310b16b50ed630e6b0f47b71946ae7d19504.
Subsequent host edits, including completed-call replay and disconnect regressions,
are outside that sealed archive and remain unvalidated. This ordinary local
checkpoint preserves work; it is not a matrix-complete ancestor or receipt binding.
Source-only Ruff/diff checks and type checking of the four changed typed production
modules passed. Required remaining work is the complete coupled selection, failure
correction and one exact-source green matrix run. No independent finding is closed.

### PR15-COUPLED-MATRIX — source ready for combined development run (2026-09-10 UTC)

The current assignment starts at d7f0921955aec8183a754646030cd6220b96d80d
(tree 4a8206bb18ff5eaa6380cd7c9e5ecec2810a45ff). Ordinary preservation checkpoint
185be09d9a432ae54e9f392d02729e7b749c2653 (tree d3f2f8869b8d0aede9e3f3e927984a7d20fd44ea)
retains the first coherent matrix increment; it is not a validated implementation
ancestor. Remote/PR remains a98b4b875ab4d101709d62bc7222b5c90681a893; required base
f56dfc2c9346c9b8d8eea4380a3b2388b9668bd2 remains unchanged. No product push is
permitted in this assignment. This entry precedes the combined test snapshot;
final run/checkpoint and private-delivery records are external to the bytes they attest.

The finite protected development matrix maps 53 requirements to actual assertions.
The planned combined selection retains all eight prior joined nodes, 28 causal/failure
prefixes, the four-condition I/O-continuation path, the three component files, and the
legacy retained order/cap/first-pair-state regression. A combined pass is still PENDING
at this source-recording boundary. Independent review remains PENDING regardless.

Production changes: freeze publication records a typed, irreversible aborted-unpublished
state only from the actual exclusive publisher's failed create/link boundary before
publication. Published missing/corrupt evidence stays unresolved. Controller stop phases
now follow their actual current consumer. Cleanup resume retains the same credential
and grant until its terminal release. All campaign/control writer mechanisms use held,
no-follow identities and shared pre-growth leases; successful replacement reconciles
new writes against exact retired old bytes, while partial temporary writes and unused
capacity remain counted. Finalizer selection state and receipt writes now pass through
the existing control writer, including nested selection receipts and shrinking state.
After downstream failure sealing/export, the actual observed tail and unused admission
carry into cleanup without rewriting the prior sealed accounting snapshot.

The coupled lost-send negative exposed another real consumer gap: a failed runtime can
exit before any session file is published while leaving valid immutable raw evidence.
The retained completion reader now derives only incomplete/None/error from zero sessions
when the actual sealed host process status is nonzero. A zero exit with no session,
multiple sessions, changed process status, and malformed source remain rejected. No raw
session is fabricated, no sealed answer rewritten, and no such attempt is evaluated.
The complete joined failure/export/acknowledgement consumers now exercise this branch.

Distinct originals retained: c590e93651f01d77 (2 passed/1 failed), 3fb67325e02605d3
(4 failed), 2ebf2eeb092162b1 (21 passed/4 failed), d328a2465cf11b05 (27 passed),
85d6229ed26d11f9 (11 passed/7 failed), 14069fda17a058f5 (300 passed/7 failed),
c6a8080eaa9d6f7c (7 passed/2 failed), 375db2a5c7a51919 (7 passed). Do not sum them
into a green suite. Full run IDs, complete source manifests, original JUnit/exits,
source diffs and writer/phase/controller traces are retained in the private handoff.
The last targeted source input is e7da916930993c4e581c544fd88579433c519d94b81e47dbc9043f84044bc6ca.
The separate 14069 four-condition I/O path completed actual retained finalizer/evaluator/
first-pair checkpoint and cleanup; it does not certify the combined snapshot.

Original export defect 85d6: the collector/host member limits interrupted collection.
A bounded export-only continuation preserved the original JUnit and closed joined
artifacts, then removed exact-owned ephemeral volumes. It did not rerun the separate
focused-export remainder; omitted phase/campaign diagnostics were not reconstructed.
The existing exporter now validates both complete original indexes, bytes and hashes
before ephemeral cleanup, and retains exact per-condition runtime fault/census records.
Its higher finite transport/member limits remain within the owner's existing 1-GiB
export cap and do not alter scientific writer budgets or test acceptance.

Negative semantics stay distinct: half-close preserves possibly-sent reservation and
essential failure evidence with exact-owned cleanup. Rejected terminal acknowledgement
can leave verified raw export and resource cleanup while the shared failure projection
remains unsealed/unresolved, with actual exit zero retained and no evaluator/later
condition. Withheld host-transfer verification leaves remote-zero/privacy proof
unresolved; a different partial-transfer prefix demonstrates supported cleanup.
No successful receipt is inferred from a component pass or method-map boolean.

All runs use the existing gic-pr15-clean-ci ARM64 container lane, image
sha256:0928021614063435abaebc9771282edd681aa7dfe1e2960c1a86dda61b174a3a,
Python 3.11.14, uv 0.11.7, Quarto 1.9.38 and unchanged recipe/lock inputs.
This assignment's storage/containment smoke 006825c00571cc79 passed. The non-root,
network-none, read-only source/root, declared-volume, capped resource and precollection/
child effect guards remain active. No unguarded host pytest was used. Native source-only
Ruff/mypy/diff checks are labelled separately. Final make ci-check, full exact-base parity,
privacy/site/native acceptance, final V16 regeneration and product publication are NOT RUN
by this assignment's boundary. No independent R finding is claimed closed.

Source109: UNKNOWN, excluded from successful validation; recovery deferred. Its old
storage cause and container/three-volume absence remain unresolved. Old bundles/keys/
recovery tools and shared Desktop/Lab/Biblos remain unused. Fresh-lane operability is not
an old-fault cure. Existing infrastructure credential use/outer operations are separate
from fake inner effects, blocked forbidden dispatch and zero real experimental activity.
Frozen EXP-0001 science/model/evaluator/data/order/budgets/zero retries and historical
USD 36.36170860803283125 remain unchanged. New real provider/model cost USD 0.00.
No V17, live grant, PR mutation, merge or independent self-approval.


### Coupled matrix continuation — deterministic delayed attach input (2026-09-10)

Combined development run `gic-pr15-ci-c50140bc313e3cd6`, input-manifest
`925b7871e7ef1cc9a9a280a47c3c8b33b9add7b1ba2f84d18deaef5b83aca094`, retained
337 passes and one failure, no errors/skips, pytest exit 1, unchanged sealed source.
The attach-output-denial fixture wrote excess bytes while its runtime was still
exiting; the actual child was killed with status -9 before the asserted zero exit.
This is retained as a timing-fixture failure, not an invented zero exit or a new
storage incident. Both original export indexes were verified. Two exact saved
pre-corruption ownership records were separately copied and reread before cleanup;
future collectors include those named originals in the normal bounded export.

The bound container/attach leaf now buffers at most 8 MiB of actual fixture stdout,
observes the real runtime exit, then delivers those bytes over an actual pipe to
the unchanged retained capture/admission/essential-failure consumers. It delegates
process status and termination to the actual child; it supplies no successful
phase receipt or fabricated exit. The joined assertion requires observed zero
exit before delayed delivery, actual excess bytes, preserved zero/unscored status,
essential export and no later condition. Production caps and scientific inputs
are unchanged. Two component parameters independently carry real exits 0 and 7.

Run `gic-pr15-ci-ac1a339e6817279e` (source
`174f79c7bd691db9cc7f9a1379d6ee359b9db4c177c78e021122c6e773045328`)
passed the joined denial path but failed two new components: their `-I` option
prevented supported Python-child guard loading. The guard denied both launches;
the overall guard/gate exit was 90. Removing that test option preserves guarded
child execution. Run `gic-pr15-ci-317302ca3b9887b5` (source
`4698d29bdb9877c6a7044ff3592678862d280e33e9a76931858427fcdd9077de`)
then passed both components with pytest exit 0, but its original container command
failed export because no test requested a temporary directory. The collector now
admits an absent temporary root only when original JUnit contains no candidate
process node; synthetic component/candidate/unsafe-XML checks passed. Export-only
continuation `export-continuation-6948255a` completed both original indexes and
exact-owned cleanup. Original failed receipts were not relabelled.

All earlier run results remain separate. The complete 53-row development matrix
rerun is pending at this source-record boundary; its external final records must
bind all required nodes to these actual bytes before a matrix-complete checkpoint
is claimed. No final CI/parity, final V16 receipts, product push, PR mutation,
independent closure or Source109 recovery is authorized by this increment.


### 2026-09-10 — Accepted development matrix; finalization in progress

The owner delivered independent acceptance of the 53-row R1–R6 development
matrix at immutable checkpoint `0b27b74cbf160130b8177f47323e4d4f37a11986`
(tree `b0a610beb99da1456c63738feda5cb168b936d97`). The 340-pass run,
including all 37 joined parameters, is retained at private evidence commit
`fabc0e75f504c8e4e401a5fd986507908b3712a4`. This is progression authority,
not independent PR approval or a substitute for the final exact-commit gate.

The initial checkpoint was verified clean and designated externally. Required
finalization corrections now supersede that designation for affected current
receipts: preserve original parity JUnit and subprocess exits; admit only the
bounded local Git operations required by parity/conformance; and use the existing
canonical host-phase wire binding when no candidate fixture is present. The
initial capsule and agent-check failures are retained as development evidence.
A new clean implementation/test ancestor and normal generated V16 descendants
must follow affected focused checks. No current receipt may certify itself.

Source109 collection/post-test integrity remain UNKNOWN and recovery is deferred;
the original storage fault and old container/three-volume absence remain
unresolved. The fresh GIC-only lane does not cure that incident. Source106,
Source108 and the accepted matrix keep their separate original identities.
Final static/control/privacy/site/native and base/head parity gates, complete
export, publication and independent exact-head review remain pending. Final run
records belong outside the candidate; no post-validation tracked success edit is
required. Frozen science, zero retries and zero new real experimental cost are
unchanged. No V17, live authority, hosted CI, shared runtime or merge is granted.

Further pre-validation corrections preserve the normal shadow writers' shared
pre-growth admission, keep anti-shadow name tracking within lexical scope,
place nested incident Git fixtures in declared guarded scratch, and validate
frozen shared schemas at their exact recorded source ancestors. Nonsecret
context reset handles and fixture binding sentinels now have explicit role
names; the credential scanner and its patterns remain unchanged. The original
failed checks are retained externally. Current receipt generation, exact final
CI and independent review are still pending at this source boundary.

The next normal receipt attempt, `gic-pr15-ci-b39aceaa45da0e2a`, failed the
unchanged public-topology gate because incident receipts embedded raw regression
diagnostics. The producer now keeps actual exits in the public projection and
routes diagnostics to the private command log. A separate bounded probe traced
unscored incident-child evaluation to NLTK import without a private `HOME`;
incident subprocesses now create their own protected temporary home. An older
failure-envelope assertion also compared the sealed accounting snapshot with
later output consumption. Its regression now binds the actual held call-ledger
bytes and checks that later observed growth consumes the same reserved allowance
without changing the upper bound or provider history. Original failures remain
retained; a new source ancestor, regenerated receipts and final CI are required.
The historical-receipt tests also exposed an omitted runtime-identity role in
their existing temporary successor fixture. That helper now materializes the
test-owned file and derives its execution/condition/command references from the
actual bytes. Frozen V16 inputs remain unchanged; no persistent successor
package or live authority is created.

The next normal V16 generation passed at source ancestor `ced4df2ea33a138ac5a441a3a55769ad3542637b`, and its byte-verified 29-file receipt set was committed as ordinary descendant `f8ab49739b1f83fbf07000d1e71922e8dac69974`. The separate guarded native run then recorded 87 passes and one failure: Git rendered the same fixed UTC author/committer clock using `Z` rather than `+00:00`. The fixture assertion now compares exact epoch seconds, preserving the clock contract without depending on display spelling. The failed native run and receipt descendant remain retained. This test-source correction requires a new immutable ancestor, regenerated receipts and renewed exact-candidate validation; no final gate or product publication is claimed.

Normal generation then passed against `00e94b61c5123649227d7c0a8c4127ba03e7489e`, producing receipt descendant `b95ae42031aef013e5b6607d33a9a8dd51423943`; its guarded native counterpart passed all 88 tests. Exact-candidate run `gic-pr15-ci-c757f679362fbc22` passed lock/sync, format, lint, mypy and the aggregate agent check, but repository validation rejected three changed retained runtime files absent from the current source receipt. Site and base/head pytest parity were not reached. Source integrity, original export and exact-owned ephemeral cleanup passed independently.

The current shared-source receipt now includes the retained evaluator, finalizer qualification, evidence regression, runtime preflight and the four new campaign/candidate/environment/qualification helpers. Source-binding schema `4.0.0` and aggregate binding generation `7.0.0` identify that exact 51-file closure; historical source schema `3.0.0` retains its original 43-file set. This extends the existing proof contract without changing scientific packages or historical hashes. Normal-generation integration and per-file current-source mutation negatives cover the new members; a relabelled older aggregate generation must reject the new source schema. New immutable source, regenerated V16 receipts and the complete exact-candidate gate remain required.

The next exact-candidate run, `gic-pr15-ci-9d6a9cd96caddb7b` at receipt descendant
`452485a8dad1a30f1fe9a875a3876263e3bfbe11`, passed static, control, repository,
privacy and site gates. Its base pytest then exited 90 after guard denials;
head pytest and parity were not reached. The original base JUnit recorded 2,222
passes, 70 failures, 20 errors and two skips. Those outcomes are not a qualified
parity baseline. Original exports, source integrity and exact-owned cleanup
passed independently; the old image did not export its guard journals.

The corrected offline environment admits narrowly specified native process-state
queries, guarded isolated Python entrypoints and exact fixture Git operations.
Legacy system-Python spelling selects the pinned interpreter with a separate
fixture record. A source-bound empty container-inventory input completes one
existing pre-entry negative's low-level environmental closure, symmetrically for
base and head; actual retained consumers and original assertions still execute.
Unexpected caught denials remain failures. Immutable guard journals are now
exported and independently checked before cleanup. Focused run
`gic-pr15-ci-deeb44b364ae6511` passed all 156 tests; full baseline diagnosis and
renewed exact-candidate validation remain separate pending gates.

A base-diagnostic wrapper's missing scratch parent failed before pytest. Its
original exports were independently reconciled and the exact retained volumes
closed without changing the failed receipt. This also exposed an outer-launcher
contract gap: failed collection could remove the stopped container before its
results were verified. The active regression requires retaining started
containers with unresolved exports, with normal exact-owned stopping and
explicit unresolved evidence. This maintenance correction does not alter
experimental cleanup policy, scientific budgets or the accepted R1–R6 matrix.

The third complete exact-candidate run, `gic-pr15-ci-05ea63eaa724cda4` at
`0d1fc465744119ff433e8cde1ee2c4f7fc750a26`, passed static/control/privacy/site
checks and reproduced all 53 accepted matrix rows and all 37 joined parameters.
Its full parity gate nevertheless failed: base raw pytest had 2,282 passes,
30 failures and two skips; head had 2,916 passes, 41 failures and two skips,
including 14 new failures. No missing base nodes or weakened transitions were
reported. Complete original results, guard journals, source integrity and
exact-owned ephemeral cleanup were verified. This is a failed final candidate,
not final certification or a combined green suite.

The new failures exposed outdated negative-test setup: a no-op dirty delta on a
clean commit, doubles missing actual candidate/writer/fixture arguments, a held
cleanup component without its validated temporary contract/policy, a checkpoint
loader fault injected before cleanup, and a published-freeze fixture without its
prior durable publication intent. Historical plan tests now select their frozen
implementation and shared cleanup-schema ancestor explicitly while retaining
current exact versioned artifact pins. No expected historical hash or production
acceptance rule changed. Focused run `gic-pr15-ci-94d9af94f1878258` retained 11
passes and three setup failures; their corrected actual nodes all passed in
`gic-pr15-ci-34fa9f462dca1ffc` (14 passes, no failures/errors/skips). The original
red runs remain retained. New source/receipt descendants and the complete final
gate remain required; independent review is pending.
