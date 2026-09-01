# Phase 1 — T09 control-plane stabilization

Status: **in-progress**

Plan role: **workstream**

Live authorization: **false**

Scientific interpretation allowed: **false**

## Source contract

This Category 1 workstream is governed by the operator-supplied
`T09 Control-Plane Stabilization and Agent Operating Foundation` contract. It
replaces version-selected runtime behavior with semantic capabilities, proves the
registered control plane offline, and rehearses the shared Category 3 transaction
through production wrappers over deterministic fake low-level effects before any
secret, authenticated request, provider action, paid compute, or scientific
execution.

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

The immutable base is commit
`450a10a51eda4c428f20b27d6b4aafc4f94d80f4`, tree
`f423d490ddacc2a1eba9cecebc6dbb05e982c55e`, with ordered parents
`be09fe18dd46d0e5fe1aa65cfac29190edfa8aac` and
`81649d0eb1a9c2773ea261014c2443e29fdb55a6`.

## Scope and boundaries

In scope are CP-01 through CP-20 below. Implementation, testing, direct
spec-conformance review, repository writes, Git operations, and architectural or
scientific decisions remain in this task. The shared controller may expose future
live-effect interfaces, but this workstream supplies only local network-disabled fake
low-level channels and can mint only shadow authority.

Out of scope are V17 or `AUTONOMOUS-0010` artifacts, live authorization, dotenv or
secret access, authenticated OpenAI or Lambda requests, cloud inspection or
mutation, live Docker/browser/SiRA/evaluator/condition execution, scientific
adjudication, merge, auto-merge, force-push, and delegated review or implementation.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| CP-01 | Exact base and historical evidence preserved | Git/GitHub identity checks, starting tree, V16 disposition, preservation tests | met |
| CP-02 | Semantic capabilities added to every contract | Registry audit and semantic-contract tests | met |
| CP-03 | Active runtime dispatch no longer depends on version allowlists | Classified inventory, capability dispatch, repository lint | met |
| CP-04 | Repository version lint passes | Focused validator tests and repository receipt | met |
| CP-05 | Registry completeness passes for every contract | Per-contract real-consumer matrix and deterministic receipt | met |
| CP-06 | V16 lifecycle omission reproduced and prevented offline | Mutant regression and direct autonomous-contract lifecycle test | met |
| CP-07 | Offline composition is complete and deterministic | Schema-valid per-contract composition receipts | met |
| CP-08 | Shared Category 3 controller is the production transaction path | Production-wrapper assembly over retained primitives with fake low-level effects | met |
| CP-09 | Full production-coupled happy-path shadow transaction passes | Deterministic V16 production-wrapper receipt | met |
| CP-10 | Required failure-matrix shadow scenarios pass | Per-scenario receipts and effect assertions | met |
| CP-11 | Exact validated control proofs precede secret/metadata access | Opaque proof types, binding validation, deterministic staging, zero-call forgery tests | met |
| CP-12 | State capsule is valid, concise, and agent-legible | Schema validation, deterministic bytes, privacy tests | met |
| CP-13 | V16 incident is linked to passing regressions | Incident validator and exact collected node IDs | met |
| CP-14 | Stable CLI and Make targets exist | CLI tests and direct command runs | met |
| CP-15 | `agent-check` is part of CI before parity | Make/workflow inspection and exact gate run | met |
| CP-16 | AGENTS/PLANS/PROJECT_STATE/COMPUTE_POLICY updated coherently | Document validation and direct review | met |
| CP-17 | No V17 package or live authority created | Repository searches and state checks | met |
| CP-18 | Scientific contract unchanged | Base/head science hashes and preservation tests | met |
| CP-19 | Full/parity/static/privacy/site gates pass | Required local validation contract | met |
| CP-20 | Draft PR open, exact-head CI green, no merge | GitHub PR, rereview, and Actions metadata | partial |

No item may be marked `met` without concrete evidence. The overall status cannot be
successful while any required item is partial, blocked, or not-started.

## Implementation mapping

- Capability dispatch, version lint, and registry completeness map to CP-02 through
  CP-06.
- Composition, validated proofs, the shared controller, production-wrapper assembly,
  fake low-level effects, shadow scenarios, and ordering map to
  CP-07 through CP-11.
- Capsule, incident ledger, CLI, Make/CI, and reviewed projections map to CP-12
  through CP-16.
- Preservation, full evidence gates, direct review, and PR handoff map to CP-01 and
  CP-17 through CP-20.

## Evidence and progress log

- 2026-08-31: verified the clean original checkout, correct GitHub remote, exact
  destination commit/tree/parents, merged PR #11 reviewed head, target branch and
  worktree absence, no V17 or `AUTONOMOUS-0010` artifacts, and the retained public
  V16 absence disposition supplied by the operator.
- 2026-08-31: created the fresh exact-base worktree at
  `/Users/joseph/.codex/worktrees/t09-control-plane-stabilization` on
  `codex/t09-control-plane-stabilization`; starting tree is
  `f423d490ddacc2a1eba9cecebc6dbb05e982c55e`.
- 2026-08-31: captured exact-base evidence from a clean detached tree. Raw pytest
  reported 1,869 passed, 24 inherited failures, and 5 skipped. Exact base-to-base
  parity passed with zero newly failing or missing-base nodes and zero invalid
  outcome transitions.
- 2026-08-31: implemented explicit V3–V16 semantic capabilities, removed active
  version dispatch, and added deterministic lint, registry, and composition receipts.
- 2026-08-31: the shared fake-only Category 3 controller passed the complete V16
  happy path and eleven mandatory failure/recovery scenarios. The lifecycle-omission
  fixture stops at composition with zero secret, metadata, or provider calls.
- 2026-08-31: added the goal/capsule, immutable incident, stopped V16 disposition,
  stable CLI, Make/CI gate, future receipt-binding schema, and reviewed projections.
  The aggregate `agent-check` passes for 14 contracts and 12 shadow scenarios.
- 2026-08-31: committed the shared runtime capability refactor at
  `25a23e6952618c800cd9e5d0efaca493af612b49` and bound its six evolved runtime
  sources in a non-circular receipt. Repository validation now distinguishes this
  reviewed control evolution from immutable V16 package bytes and confirms the only
  experiment-tree change is the stopped disposition.
- 2026-08-31: post-review focused T09/control validation reported **615 passed, 5
  inherited skips, and 1 inherited private-artifact node deselected**. The new
  control-foundation suite itself reports **61 passed** with no skip or xfail. Full
  raw pytest improved the exact-base result to **1,932 passed, 23 inherited failures,
  and 5 skipped** in 96.10 seconds; exact base-relative parity remains the
  authoritative regression gate.
- 2026-08-31: a historical package regression now proves the frozen V16
  instrumentation directly from its named package commit and proves the evolved
  control checkout fails closed when presented as that package. The V16 package
  bytes remain unchanged.
- 2026-08-31: direct review found one state-ownership gap: interpretation permission
  was emitted as a constant instead of being owned by the typed transaction state.
  Commit `ac99cabc31e06d3d96d6467f670511c11080bedd` repaired it; focused tests,
  repository validation, agent-check, privacy/boundary scans, and the 16-page Quarto
  render pass afterward.
- 2026-08-31: immutable control receipts bind clean ancestor
  `5efbe727648ae9e7077132aa9bf3033e4b35ec03`, tree
  `5fab7020bf157c6c31a68b1b2024ca10203d3106`. Repository validation now requires
  every receipt and checks schemas, semantic hashes, the common ancestor, all 12
  scenarios, and aggregate cross-bindings.
- 2026-08-31: exact-base parity on
  `a54c126a699980892b7e986e2c447b046c904cd7` passed with zero newly failing nodes,
  zero missing base nodes, and zero invalid transitions. It retained 23 inherited
  failures, symmetrically deselected five unavailable private nodes, and observed
  four inherited environment-sensitive nodes improve to passing.
- 2026-08-31: draft PR #12 is open against the exact destination branch with
  auto-merge disabled and no merge. GitHub Actions run `33432821217` passed on
  predecessor head `63e8b94ed7b3898d88d5e3bc5f2454af68e0e6b7`; this review-state-only closeout
  commit is subject to the same exact-head CI gate before handoff.
- 2026-08-31: exact-head review `5071206789` on
  `559d52c9339bf13fae6808178a5a65fe71706f74` required repair because tracked
  shadow evidence used a parallel pure-fake adapter path, preparation trusted
  caller booleans and hash-shaped strings, and several registry rows projected
  capability values instead of invoking production resolvers. CP-05, CP-08,
  CP-09, CP-11, and CP-20 were reopened as partial before repair mutation.
- 2026-08-31: the repair replaced public proof assertions with opaque validator-minted
  capsule, receipt-set, staging, and preparation types. One exact binding document now
  transitively validates file bytes, schemas, semantic hashes, commit/tree,
  contract/package identity, complete scenarios, aggregate bindings, source bindings,
  and false authority/science fields before the staging or effect boundary.
- 2026-08-31: one `CONTROL_CONSUMERS` registry now drives both completeness and the
  production adapter assembly. The shared controller executes retained metadata,
  launch/replacement, accounting, evidence, finalizer/evaluator, and cleanup logic over
  injected fake network/model/browser/provider/filesystem/subprocess channels. No live
  authority factory or live low-level implementation was added.
- 2026-08-31: the repaired shadow matrix contains one happy path plus fifteen exact
  failure scenarios, including known, incomplete, ambiguous, and admission-stopped
  model-call accounting. Focused production-coupling, registry-mutation, shadow,
  formatting, Ruff, and strict mypy checks pass.
- 2026-08-31: sealed repaired implementation ancestor
  `efd34ee5e468e474b163e351b8bcd5be97d1f768`, tree
  `7fda7a4f8c77aa24f207b860d819040e4680c290`, and regenerated 24 non-circular
  receipts from it. Binding file SHA-256 is
  `7a675d7dd4d9e04005943e2a9bc53e4c3bdfacdb1f723a1f64fd36628b0a4add`.
  All 20 requested forgery/bypass cases stop before staging and effects; all 31 exact
  shared-source members validate; the full control suite, retained provider/accounting
  focus, aggregate agent check, and repository validator pass. CP-05, CP-08, CP-09,
  and CP-11 are therefore met.
- 2026-08-31: direct Sol/max review added runtime-package, complete-capsule,
  command-package, and nonzero fake-accounting binding checks plus five regressions.
  Raw pytest reports **2,002 passed, 23 inherited failures, and 5 inherited private
  skips**. Exact-base parity reports base **1,866 passed / 27 failed** and head
  **2,002 passed / 23 failed**, with zero newly failing or missing nodes, zero invalid
  transitions, four inherited nodes newly passing, five unchanged symmetric private
  deselections, and `parity_passed: true`. CP-19 is met. CP-20 remains partial only
  for the exact-head GitHub Actions result and independent rereview.

## Decisions and blockers

- The governing request prohibits delegation. Direct Sol/max self-review replaces
  the assembly workflow's usual subagent review; independent exact-head review is
  reserved for ChatGPT.
- No live environment is required or permitted. Any implementation path that would
  read a secret, contact a provider, inspect cloud state, or execute science is a
  contract violation rather than a fallback.
- No blocker is currently known.

## PR 1.1 successor-target repair

Assembly status: **complete — draft review required**

The operator-supplied `T09 PR 1.1 — Make the Agent Control Target
Successor-Driven` contract governs the post-merge Category 1 repair. The exact base
is merge commit `d0aff8a47e92013773d9d05b2cd90fb741658b03`, tree
`a6801e99d8e6ed204bbfa49ca1f3f17ad8b793ec`, with ordered parents
`450a10a51eda4c428f20b27d6b4aafc4f94d80f4` and
`ccab5f1255f5a397ce14f1ebec7d96068bda91bc`. The required control contract is one
frozen, goal-compatible selected-runtime target used by every aggregate command.
There is no current/latest/default contract and selection never grants authority.

```text
operator_attests_model: gpt-5.6-sol
operator_attests_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

### PR 1.1 scope and boundaries

In scope are the target resolver, aggregate target plumbing, safe versioned receipt
roots, active-selection lint, one control-design incident, synthetic successor
fixtures, non-circular V16 receipt rebinding, reviewed projections, and CT-01 through
CT-22 below.

Out of scope are tracked V17 package artifacts, `AUTONOMOUS-0010`, live effects or
authority, real secret/provider/cloud/scientific execution, V16 replay, merge,
auto-merge, force-push, and delegation. Direct Sol/max self-review is the required
review path because the governing operator contract prohibits subagents.

### PR 1.1 definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| CT-01 | Exact base and merged PR 1 history preserved | Git/GitHub identity and clean-worktree checks | met |
| CT-02 | All active fixed V16 selections inventoried | Classified implementation-ledger inventory | met |
| CT-03 | One typed goal-compatible target resolver exists | Target unit tests and source review | met |
| CT-04 | Current goal resolves V16 | Target receipt and aggregate CLI tests | met |
| CT-05 | Synthetic package-bound successor resolves V17 | Temporary-repository synthetic package test | met |
| CT-06 | Agent check contains no fixed package target | Source lint and V16/V17 aggregate tests | met |
| CT-07 | CLI aggregate commands contain no fixed package target | Parser/command integration tests | met |
| CT-08 | Make/CI defaults contain no fixed package target | Make/workflow inspection and direct targets | met |
| CT-09 | Receipt generation supports safe versioned roots | Output-root and generated-binding tests | met |
| CT-10 | Existing sealed root cannot be overwritten | Sealed-root regression | met |
| CT-11 | Binding validator accepts package-specific roots | Temporary-root binding validation | met |
| CT-12 | Active-version lint catches fixed contract selection | AST lint regressions and zero-finding receipt | met |
| CT-13 | Synthetic successor completes registry/composition/shadow/agent-check | Full synthetic successor path | met |
| CT-14 | Synthetic successor requires no shared aggregate-control edits | Before/after shared-source byte map | met |
| CT-15 | All target failures precede effect boundaries | Zero-call counters and ordering tests | met |
| CT-16 | Incident linked to passing regressions | Incident validator and exact node IDs | met |
| CT-17 | Current V16 receipts remain valid or are correctly rebound | Immutable ancestor and binding validation | met |
| CT-18 | PR 2 boundary is explicit and enforceable | Architecture/packet/ledger text plus source-byte test | met |
| CT-19 | No tracked V17 artifact exists | Git path scan | met |
| CT-20 | Science and authority boundaries unchanged | Hash, capsule, proof, privacy, and false-flag tests | met |
| CT-21 | Full/parity/static/privacy/site gates pass | Required final command set | met |
| CT-22 | Draft PR open, exact-head CI green, no merge | GitHub PR/run metadata | met |

### PR 1.1 implementation mapping

- Target parsing, package validation, goal compatibility, and explicit selection map
  to CT-03 through CT-05 and CT-15.
- Agent-check, CLI, Make/CI, versioned receipt roots, binding validation, and lint map
  to CT-06 through CT-12 and CT-17.
- The synthetic successor fixture and unchanged-source proof map to CT-13, CT-14,
  CT-18, and CT-19.
- The incident, authority/science preservation, full gates, and draft PR handoff map
  to CT-01, CT-02, CT-16, and CT-20 through CT-22.

### PR #13 exact-head review repair

Assembly status: **implemented and locally validated — parity and exact-head GitHub gates pending**

Review `5078551304` examined commit
`ccb5ee0fc454111a976c6de951d798a630a537b9`, tree
`4a5c617e3746cf3148b2d4dc85764e49d2096288`, against the unchanged exact base and
reopened the receipt-history, publication, lint, capsule, preservation, and final
review gates. The governing repair contract requires historical proofs to remain
valid after a successor becomes current, complete-tree publication to be atomic and
recoverable, the original versioned-constant selector form to be linted, and the
capsule to distinguish technical incidents from external governance.

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| RC-01 | Historical targets resolve from exact goal bytes bound to each receipt's immutable control commit/tree | Bound-goal hash/target/package tests | met |
| RC-02 | Every sealed V16 and package-specific receipt root is enumerated and fully validated | Multi-root inventory and drift/removal tests | met |
| RC-03 | Only the active root must additionally equal the current goal-selected target | V17-current/V16-historical compatibility tests | met |
| RC-04 | Receipt publication uses one complete-tree no-replace commit and never exposes an unrecoverable partial final root | Nine-boundary interruption/concurrency matrix | met |
| RC-05 | Successful equivalent receipt publications remain byte-identical | Two-root deterministic generation test | met |
| RC-06 | Active lint rejects direct, attributed, and aliased versioned provider-contract constants | Direct-constant AST matrix and zero-finding repository receipt | met |
| RC-07 | Capsule separates unresolved technical incidents from external governance gates | Goal/schema/capsule consistency tests | met |
| RC-08 | Resolved incidents cannot be current blockers; incident history remains append-only | Incident/capsule mutation regressions | met |
| RC-09 | Synthetic V17 traverses every shared aggregate path while retained V16 validates historically | Full temporary successor/root proof | met |
| RC-10 | All proof, target, and publication preconditions remain before secret/provider/condition effects | Zero-call focused assertions | met |
| RC-11 | V17/package-only boundary, no-live-authority, no-science, and no-tracked-V17 invariants remain exact | Shared-source byte map, Git path scan, EXP-0001 tree identity | met |
| RC-12 | Focused/full/parity/static/privacy/site and exact-head GitHub gates pass; PR remains draft/unmerged | Required command set, PR metadata, Actions result | in-progress |

Implementation mapping: target/proof and repository enumeration changes map to
RC-01 through RC-03 and RC-09; CLI publication maps to RC-04 and RC-05; AST lint
maps to RC-06; goal/capsule/incident validation maps to RC-07 and RC-08; ordering,
preservation, receipt rebinding, and final review map to RC-09 through RC-12. The
operator prohibits delegation, so direct Sol/max source/spec review replaces the
assembly workflow's subagent review.

Local final-gate evidence on 2026-09-01: the complete focused repair batch passed
176/176 nodes without skips or xfails; the raw suite reported 2,067 passed, the same
23 inherited failures, and the same five inherited private-fixture skips; Ruff,
strict mypy, repository validation, goal-derived V16 agent-check, pinned-Quarto site
render/validation, and `git diff --check` passed. Base-relative parity, the draft PR
update, and exact-head GitHub Actions remain the only RC-12 work.

## Next permitted phase

Complete this PR 1.1 assembly on `codex/t09-control-target-selection`, open one draft
PR against `phase-1/sira-pilot-autonomous-r2`, obtain exact-head GitHub Actions, and
stop without merge. A later PR 2 may be package-only within the explicit boundary;
this work must not create V17 package artifacts or authority.
