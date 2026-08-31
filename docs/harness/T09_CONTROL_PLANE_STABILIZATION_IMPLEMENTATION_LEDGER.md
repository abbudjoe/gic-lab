# T09 control-plane stabilization implementation ledger

Status: **in-progress**

Live authorization: **false**

Scientific interpretation allowed: **false**

## Operator attestation

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

The runtime is not introspected. Implementation, testing, repository writes, Git
operations, architectural decisions, scientific decisions, and review are not
delegated.

## Exact starting identity

```text
repository: abbudjoe/gic-lab
destination: phase-1/sira-pilot-autonomous-r2
branch: codex/t09-control-plane-stabilization
commit: 450a10a51eda4c428f20b27d6b4aafc4f94d80f4
tree: f423d490ddacc2a1eba9cecebc6dbb05e982c55e
parent_1: be09fe18dd46d0e5fe1aa65cfac29190edfa8aac
parent_2: 81649d0eb1a9c2773ea261014c2443e29fdb55a6
starting_tree: f423d490ddacc2a1eba9cecebc6dbb05e982c55e
```

PR #11 is closed and merged at the exact base; its reviewed head is the exact second
parent. The original checkout and new worktree were clean when the worktree was
created. No target branch/worktree or V17/`AUTONOMOUS-0010` artifact existed.

## Assembly ledger

The authoritative CP-01 through CP-20 checklist and implementation mapping are in
`docs/exec-plans/active/T09_CONTROL_PLANE_STABILIZATION.md`. Review `5071206789`
reopened CP-05, CP-08, CP-09, CP-11, and CP-20 as `partial`; they cannot return to
`met` until production coupling, exact proof validation, real-consumer completeness,
direct review, local parity, and exact-head GitHub Actions all pass.

## Review repair assembly

Exact reviewed identity:

```text
review_id: 5071206789
reviewed_commit: 559d52c9339bf13fae6808178a5a65fe71706f74
reviewed_tree: 93706e4cb3f02e7833b14e2f42c3ea757ce55316
base_commit: 450a10a51eda4c428f20b27d6b4aafc4f94d80f4
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
implementation_delegated: false
```

| Repair item | Required evidence | Status |
|---|---|---|
| RR-01 | Opaque validated capsule, receipt-set, staging, and preparation types; no caller proof booleans/hash tuples | met |
| RR-02 | Exact binding-document, file, schema, semantic, commit/tree, contract/package, cross-binding, source, authority, and scenario validation | met |
| RR-03 | Production-wrapper adapter assembly over retained lifecycle, metadata, replacement, accounting, host/evidence, finalizer, and cleanup primitives | met |
| RR-04 | Tracked happy/failure receipts and agent-check use production wrappers with fake low-level effects | met |
| RR-05 | One real-consumer registry shared by completeness and production assembly | met |
| RR-06 | Forgery, registry mutation, production-coupling, and accounting regressions with no skips/xfails | met |
| RR-07 | Non-circular immutable receipts, incident/capsule/docs, and direct Sol/max self-review | in-progress |
| RR-08 | Focused/full/static/privacy/site/parity and exact-head GitHub Actions; draft PR comment and rereview handoff | not-started |

## Active-version dispatch inventory

The exact-base inventory was completed before behavior changes:

| Source surface | Exact-base occurrence | Classification | Disposition |
|---|---|---|---|
| `t09_provider_contracts.py` | V3/V4 finalizer guard, V12–V16 control-root list, V12–V16 metadata command list | active behavior dispatch | replaced by frozen capability fields and construction invariants |
| `t09_provider_contracts.py` | V3–V16 declarations, plan/control/archive/stage string generation | central registry declaration / generated identity formatting | retained; the registry is the only version-to-capability map |
| `t09_pragmatic_provider.py` | metadata set, four lifecycle branches, V11 authority branch, V11–V16 cleanup authority list, V8–V11 package-transition list, V6/V7 headroom list | active behavior dispatch | replaced by metadata, lifecycle, authorization, transition, and replacement capabilities |
| `t09_pragmatic_provider.py` | exact V9 stale-command migration branch | historical identity check | retained with one line-level historical annotation |
| `t09_model_metadata_receipt.py` | `MODEL_METADATA_CONTRACT_VERSIONS` and three consumers | active behavior dispatch | replaced by `MetadataPolicy` |
| `t09_sira_pilot.py` | V13–V16 command selector list | active behavior dispatch | replaced by `ProviderSelectorPolicy` |
| `t09_sira_pilot.py` | provider version in runtime/attempt IDs and receipt equality | generated identity formatting / historical identity check | retained |
| `t09_freeze_commands.py` | V12–V16 metadata fields and V13–V16 finalizer selector | active behavior dispatch | replaced by metadata and selector capabilities |
| `t09_remote_runner.py` | V11–V16 runner support, repeated V12–V16 metadata branches, V12–V16 typed stage identity | active behavior dispatch | replaced by authorization, metadata, and stage-identity capabilities |
| `t09_remote_runner.py` | exact receipt-version equality, V11 legacy inbound identity, versioned runtime-identity filename | historical/schema identity check / generated identity formatting | retained |
| `t09_evaluate_attempt.py` | provider qualification version equality | historical identity check | retained |
| `t09_local_finalizer_qualification.py` | explicit version/plan selector exclusivity and registry lookup | schema compatibility check | retained |
| `validation.py` | V9–V16 historical plan/schema projections | schema compatibility and historical identity checks | retained as the single explicit historical-module lint allowlist |
| remaining `src/giclab/` and pragmatic container references | Python/package/image/API version comparisons or prose | non-T09 package identity / schema compatibility | retained |

There were no test fixtures in the scanned runtime roots. Tests remain outside the
runtime lint scan and directly exercise both prohibited and permitted examples.

## Evidence log

- 2026-08-31 preflight: remote, clean checkout, fetch, destination identity, exact
  tree/parents, PR #11 identity, branch/worktree absence, no-V17 boundary, and retained
  V16 provider-absence evidence all matched the governing contract.
- 2026-08-31 exact-base raw/full suite from a clean detached worktree: **1,869
  passed, 24 failed, 5 skipped** in 75.18 seconds. The failures are inherited
  historical/private-artifact and stale historical-projection expectations.
- 2026-08-31 exact base-to-base parity: **passed** with zero newly failing nodes,
  zero missing base nodes, and zero invalid outcome transitions. The comparator
  observed 23 unchanged head failures, five symmetric private deselections, and four
  environment/materialization-sensitive base failures that passed in the head-side
  exact-base worktree.
- 2026-08-31 semantic capability and dispatch smoke: the V3–V16 mapping, every
  autonomous lifecycle including V16, contradiction checks, active-version AST lint,
  and complete per-contract consumer matrix pass. The focused capability/lint/registry
  plus retained V12–V16/provider suite passes; focused Ruff and strict mypy are clean.
- 2026-08-31 control-foundation suite: **61 passed** with no skips or xfails after
  adding composition, Category 3 state machine/fakes, 12 scenario receipts, capsule,
  incident validation, and future control-receipt bindings. Focused Ruff and strict
  mypy pass for the complete new control package.
- 2026-08-31 aggregate agent check: **passed**. It reports 14/14 registered contract
  matrices/compositions complete, active-version findings 0, one resolved incident
  with three passing exact nodes, 12/12 shadow scenarios valid, and a schema-valid
  deterministic state capsule.
- 2026-08-31 post-review focused suite: **615 passed, 5 inherited skips, 1 inherited
  private-artifact node deselected** in 66.22 seconds. The new control-foundation
  suite reports **61 passed** with no skips or xfails.
- 2026-08-31 post-review raw/full suite: **1,932 passed, 23 failed, 5 skipped** in
  96.10 seconds. This is one fewer failing node than the exact base; the remaining
  failures are the inherited stale historical projections and unavailable private
  artifacts. Exact base-relative parity is still required for the final regression
  decision.
- 2026-08-31 public site: the pinned Quarto 1.9.38 tool rendered all 16 notebook
  pages and `giclab-validate site` passed.
- 2026-08-31 exact-base parity: **passed** on
  `a54c126a699980892b7e986e2c447b046c904cd7` with zero newly failing nodes, zero
  missing base nodes, and zero invalid outcome transitions. The comparator reports
  23 unchanged inherited failures, five symmetrically deselected unavailable private
  nodes, and four inherited environment-sensitive nodes newly passing.
- 2026-08-31 source binding: commit
  `9c8f65dcaf9f9e6960cc41e2f46ffa801d20d6b3`, tree
  `2c6a3539dda1ca11475e5b1fdfa6be6f6d21a863`, six shared runtime sources, semantic
  SHA-256 `bac2c3100b79a8262182c6f3da93f97a0c1932ceb0e0c89e25b59368cd151386`.
  `giclab-validate all` passes with unchanged scientific/package artifacts and no
  future package identity.
- 2026-08-31 review handoff: draft PR #12 is open against
  `phase-1/sira-pilot-autonomous-r2`, with auto-merge disabled and no merge. GitHub
  Actions run `33432821217` passed on predecessor head
  `63e8b94ed7b3898d88d5e3bc5f2454af68e0e6b7`; this review-state-only closeout
  commit must pass the same exact-head CI gate before the terminal handoff.
- 2026-08-31 review-repair implementation: added opaque document-backed control
  proofs, exact transitive receipt validation, deterministic staging validation, one
  real-consumer registry, one production-wrapper assembly, and one shared controller
  accepting shadow-only fake channels or future separately reviewed live channels.
  The production shadow exercises retained metadata, provider launch/replacement,
  accounting, evidence, finalizer/evaluator, and cleanup primitives. Focused shadow,
  coupling, registry-mutation, CLI, Ruff, and strict mypy checks pass; receipt
  regeneration, proof-forgery coverage, full gates, direct review, and CI are pending.

## Immutable control receipts

Every repaired receipt binds clean implementation ancestor
`9e93d7e0d76bc98f8b008f335147d5002aa96156`, tree
`4ebfa95173a15eb1e68228c516d715bbff30b8b5`, rather than its own commit.

| Receipt | Bytes | File SHA-256 |
|---|---:|---|
| `control/receipts/active-version-lint.json` | 5,091 | `03a85394ed98f8e71526ffd647384393c1aee6e41effba47ad52e4d93ef884fb` |
| `control/receipts/registry-completeness.json` | 89,819 | `261b71c5a03246a94e9ae0d2ed5620baed8b62ae420971b62b1d31c6673b4d83` |
| `control/receipts/v16-composition.json` | 2,166 | `aa3296ac1e1f6adbc9a40713f3c6392abe5cd93d11eca0fdda7c19e958466a4d` |
| `control/receipts/state-capsule.json` | 2,750 | `b0e79967078cfeb9e47257a704120b69c94c7bc09a62d209a3fe2c77b71fb133` |
| `control/receipts/category3-shadow/happy-path.json` | 42,287 | `b5cfeddab36ea3c4d6986c545f1729893793d65fb7e56bd1f1b5416f02a03d09` |
| `control/receipts/incidents.json` | 1,053 | `eb4d022cb2dc546967b1c1bc9b18f0f791dd345de9cfd5857ed1dc3f2506b4ae` |
| `control/receipts/t09-control-plane-source-binding.json` | 5,650 | `ee85fb42992aee5e1ca74c9d74ddd6e2e363aaffe4262b647914ace8885c913f` |
| `control/receipts/agent-check.json` | 9,162 | `95a714ec8dd72521b103ae45505e8dbd06e48a4e85c173e8dad365067deadf4a` |
| `control/receipts/t09-control-receipt-bindings.json` | 7,814 | `e96ce55e7cfb2f6d9f9e3565bf99da2c4a008a1921b062828560059712680076` |

The binding document contains one happy path plus all fifteen exact failure artifact
identities; their canonical binding-map SHA-256 is
`8fa2dacb92a6abe0b4529275c03d4e6cf17943fb358d363ea7d12fa9b684a59f`.
Its semantic SHA-256 is
`2ee26cd5c1cec9163ba8ee53bd5a4bb9220e8118d5e494797e2afeeddfbd9c98`.
`giclab-validate all` and the runtime validator reject byte, schema, semantic,
identity, scenario, cross-binding, source-set, authority, and science drift.

## Control architecture evidence

- Capability source: `src/giclab/harness/t09_provider_contracts.py`.
- Version-dispatch lint: `src/giclab/control/version_lint.py`.
- Real-consumer definitions and completeness:
  `src/giclab/control/consumers.py` and
  `src/giclab/control/registry_validation.py`.
- Effect-free composition: `src/giclab/control/composition.py`.
- Shared transaction, production wrappers, and fake low-level effects:
  `src/giclab/control/category3.py`, `src/giclab/control/production.py`, and
  `src/giclab/control/adapters.py`.
- Exact proof minting and binding validation: `src/giclab/control/proofs.py`.
- Happy/failure matrix: `src/giclab/control/shadow.py`.
- Agent orientation and incident accretion: `src/giclab/control/state_capsule.py` and
  `src/giclab/control/incidents.py`.
- Future package boundary: `schemas/t09-control-receipt-bindings.schema.json`.

## Direct review log

The earlier direct review is superseded by exact-head review `5071206789`. A new
direct Sol/max review will be recorded only after proof-forgery coverage, immutable
receipt validation, full local/parity/site gates, and the final source diff pass. It
must answer with source and tests whether PR 2 remains package-only, future live
effects use this same controller without shared-source changes, caller assertions
cannot forge preparation, shadow invokes retained production primitives, registry
completeness invokes every real consumer, and model-call accounting participates in
shadow execution.
