# T09 remote-execution bridge implementation ledger

Status: **local-validation-in-progress**

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

## Decisions and blockers

- The governing request prohibits delegation. Direct Sol/max self-review replaces
  the assembly workflow's usual subagent review; independent exact-head review is a
  later external gate.
- Temporary local subprocesses and private IPC are permitted only in isolated
  network-disabled tests. No real credential, cloud inspection/mutation, SSH,
  Docker, browser, SiRA, evaluator, or scientific condition is permitted.
- No irreducible blocker is currently known.
