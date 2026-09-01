# T09 control-plane stabilization implementation ledger

Status: **local review repair complete; exact-head GitHub rereview pending**

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
| RR-07 | Non-circular immutable receipts, incident/capsule/docs, and direct Sol/max self-review | met |
| RR-08 | Focused/full/static/privacy/site/parity and exact-head GitHub Actions; draft PR comment and rereview handoff | partial — local gates pass; exact-head Actions and independent rereview remain |

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
  coupling, registry-mutation, CLI, Ruff, and strict mypy checks pass.
- 2026-08-31 direct review found and repaired one remaining proof-binding gap: the
  capsule runtime package now cross-binds the selected provider contract, the
  successor-package state is typed, complete capsule control flags are mandatory,
  and every shadow receipt that reaches package resolution cross-binds the selected
  command package. Happy-path preparation also proves nonzero fake model/browser
  accounting, zero retry, and zero projected real cost. Five additional forgery
  regressions bring that focused file to **29 collected tests**.
- 2026-08-31 final-source raw pytest: **2,002 passed, 23 inherited failures, 5
  inherited private skips** in 204.61 seconds. Exact base/head parity compared base
  **1,866 passed / 27 failed** across 1,893 collected nodes with head **2,002 passed /
  23 failed** across 2,025 collected nodes. It reported zero newly failing nodes,
  zero missing base nodes, zero invalid outcome transitions, four inherited failures
  newly passing, and the unchanged five-node symmetric private deselection;
  `parity_passed` is true.

## Immutable control receipts

Every repaired receipt binds clean implementation ancestor
`efd34ee5e468e474b163e351b8bcd5be97d1f768`, tree
`7fda7a4f8c77aa24f207b860d819040e4680c290`, rather than its own commit.

| Receipt | Bytes | File SHA-256 |
|---|---:|---|
| `control/receipts/active-version-lint.json` | 5,091 | `db1bdb7fbf820841d1804edc6ea30a9b69fd6beeb5a8b63fd4ea1339735611bb` |
| `control/receipts/registry-completeness.json` | 89,819 | `5a278bfa744369d57a928d478dbaab0eebe1b61078104b31b22c6a5549c82a04` |
| `control/receipts/v16-composition.json` | 2,166 | `a1fff974a89c3a13bfa2bfbff4ff2a0409d2196965373f18f0576605122d6706` |
| `control/receipts/state-capsule.json` | 2,750 | `95a5214721394c4ab1631f5f9748a7fed00c08fe043b12aa8b4369e4b41f8176` |
| `control/receipts/category3-shadow/happy-path.json` | 42,287 | `23642d2fc1e5b308b582ba15e58c7ceb8ffb1f205f697768cdb03323e74e0999` |
| `control/receipts/incidents.json` | 1,053 | `44cfb1139e9686af2bc969d4b90ec44ef851c88506f499887410b0e3f6b4a180` |
| `control/receipts/t09-control-plane-source-binding.json` | 5,811 | `1bb40634ff0611b4b7d9a94542da28c32f1fe6f41bd7a1c0d2dd48e336e016b8` |
| `control/receipts/agent-check.json` | 9,162 | `4d35d1c0b0cb5a892163e4e0a283d31277fdbf246caefd4413dcf6b8c09bc3e1` |
| `control/receipts/t09-control-receipt-bindings.json` | 7,814 | `7a675d7dd4d9e04005943e2a9bc53e4c3bdfacdb1f723a1f64fd36628b0a4add` |

The binding document contains one happy path plus all fifteen exact failure artifact
identities; their canonical binding-map SHA-256 is
`a45b536e9774aa99c1b1776eced7f5e4f23e0bc37c9f901057ffc719442d8969`.
Its semantic SHA-256 is
`7bc690fa18fd4c6c24f461a4c317e2224c7bb8db7a4060e994333b8c6fdfcc8d`.
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

The required direct Sol/max, no-delegation source/spec review is complete. It found
the runtime-package/package-hash cross-binding gap described above, repaired it in
the final immutable source ancestor, and found no remaining spec-conformance defect.
The six required determinations are:

1. **Can PR 2 remain package-only? Yes.** `LowLevelEffects` and
   `EffectAuthorityGrant` are the complete external seams; the production assembly
   and controller are already shared source. The assembly probe and
   `test_registered_active_contract_reaches_production_adapter_assembly` prove no
   controller bypass or future shared-source change is required.
2. **Can future live effects execute the same controller without shared source
   changes? Yes.** `build_production_adapter_assembly()` accepts injected low-level
   channels and external authority, while both modes enter
   `execute_category3_transaction()`. This PR exposes no live-authority factory.
3. **Can a caller forge preparation with booleans or arbitrary hashes? No.** The
   request accepts one `ControlProofReference`; opaque proof/preparation types have
   no public trust constructor. The 29-node forgery suite covers the 20 mandatory
   bypasses plus runtime-contract, successor-package, complete-control, package-hash,
   accounting, constructor, and valid-binding cases, with zero pre-secret effects.
4. **Does shadow execute retained production primitives? Yes.** The happy receipt
   records retained metadata, launch/replacement, accounting, raw export, finalizer,
   evaluator, and cleanup calls. Seven primitive mutation tests fail at their exact
   phase, and the scenario suite covers retained replacement, evidence, finalization,
   privacy, termination, and byte-identical cleanup resume.
5. **Does registry completeness call every real consumer? Yes.** The single
   11-member `CONTROL_CONSUMERS` mapping drives both registry validation and
   production assembly. Disable, active-contract rejection, and wrong-handler
   parameterizations fail each applicable consumer; a declaration-only future
   autonomous contract resolves without an active-runtime edit.
6. **Does model-call accounting participate in shadow? Yes.** The happy path makes
   four retained reservations/reconciliations and four browser actions, each using
   24 input, 8 cached-input, 6 output, and 30 total fake tokens. Aggregate observed
   and charged-upper cost is USD 0.00044, projected real cost is USD 0.00, retries
   are zero, and known-error, response-incomplete, ambiguous-send, and admission-stop
   scenarios retain typed lower/known/upper accounting.
