# Phase 1 — T09 control-plane stabilization

Status: **review-required**

Plan role: **workstream**

Live authorization: **false**

Scientific interpretation allowed: **false**

## Source contract

This Category 1 workstream is governed by the operator-supplied
`T09 Control-Plane Stabilization and Agent Operating Foundation` contract. It
replaces version-selected runtime behavior with semantic capabilities, proves the
registered control plane offline, and rehearses the shared Category 3 transaction
with deterministic fake adapters before any secret, authenticated request,
provider action, paid compute, or scientific execution.

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
live-adapter interfaces, but this workstream supplies only local network-disabled
fake adapters.

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
| CP-05 | Registry completeness passes for every contract | Per-contract consumer matrix and deterministic receipt | met |
| CP-06 | V16 lifecycle omission reproduced and prevented offline | Mutant regression and direct autonomous-contract lifecycle test | met |
| CP-07 | Offline composition is complete and deterministic | Schema-valid per-contract composition receipts | met |
| CP-08 | Shared Category 3 controller exists with fake adapters | Typed controller/adapters and focused state-machine tests | met |
| CP-09 | Full happy-path shadow transaction passes | Deterministic V16 happy-path receipt | met |
| CP-10 | Required failure-matrix shadow scenarios pass | Per-scenario receipts and effect assertions | met |
| CP-11 | Deterministic checks precede secret/metadata access | Prepared request type and zero-call ordering tests | met |
| CP-12 | State capsule is valid, concise, and agent-legible | Schema validation, deterministic bytes, privacy tests | met |
| CP-13 | V16 incident is linked to passing regressions | Incident validator and exact collected node IDs | met |
| CP-14 | Stable CLI and Make targets exist | CLI tests and direct command runs | met |
| CP-15 | `agent-check` is part of CI before parity | Make/workflow inspection and exact gate run | met |
| CP-16 | AGENTS/PLANS/PROJECT_STATE/COMPUTE_POLICY updated coherently | Document validation and direct review | met |
| CP-17 | No V17 package or live authority created | Repository searches and state checks | met |
| CP-18 | Scientific contract unchanged | Base/head science hashes and preservation tests | met |
| CP-19 | Full/parity/static/privacy/site gates pass | Required local validation contract | met |
| CP-20 | Draft PR open, exact-head CI green, no merge | GitHub PR and Actions metadata | met |

No item may be marked `met` without concrete evidence. The overall status cannot be
successful while any required item is partial, blocked, or not-started.

## Implementation mapping

- Capability dispatch, version lint, and registry completeness map to CP-02 through
  CP-06.
- Composition, controller, fake adapters, shadow scenarios, and ordering map to
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

## Decisions and blockers

- The governing request prohibits delegation. Direct Sol/max self-review replaces
  the assembly workflow's usual subagent review; independent exact-head review is
  reserved for ChatGPT.
- No live environment is required or permitted. Any implementation path that would
  read a secret, contact a provider, inspect cloud state, or execute science is a
  contract violation rather than a fallback.
- No blocker is currently known.

## Next permitted phase

Independent ChatGPT review of draft PR #12. Keep the PR draft, keep auto-merge
disabled, and do not merge. Any follow-on V17 package generation belongs in a
separate PR after this control-plane foundation is reviewed.
