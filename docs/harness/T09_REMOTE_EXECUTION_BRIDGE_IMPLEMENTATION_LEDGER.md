# T09 remote-execution bridge implementation ledger

Status: **in-progress**

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
| RB-18 | Historical V16 proof remains valid | Rebound/current and historical-root validation | not-started |
| RB-19 | No actual V17 artifact exists | Tracked/worktree boundary scan | met |
| RB-20 | Science and authority remain unchanged/false | Science hash diff, capsule, and receipt assertions | met |
| RB-21 | Full/parity/static/privacy/site gates pass | Required local validation contract | in-progress |
| RB-22 | Draft PR open, exact-head CI green, no merge | GitHub PR/check metadata | not-started |

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
- 2026-09-04: created
  `/Users/joseph/.codex/worktrees/t09-remote-execution-bridge` on
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

## Decisions and blockers

- The governing request prohibits delegation. Direct Sol/max self-review replaces
  the assembly workflow's usual subagent review; independent exact-head review is a
  later external gate.
- Temporary local subprocesses and private IPC are permitted only in isolated
  network-disabled tests. No real credential, cloud inspection/mutation, SSH,
  Docker, browser, SiRA, evaluator, or scientific condition is permitted.
- No irreducible blocker is currently known.
