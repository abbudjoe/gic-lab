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

## PR 1.1 successor-target repair assembly

Status: **complete — draft review required**

Target contract: one frozen `SelectedRuntimeTarget` resolved from
`control/goals/EXP-0001.yaml` or an exact goal-compatible explicit selector before
composition, staging, secret, metadata, provider, or condition effects. Adding one
central successor declaration and its package data must not require changes to the
shared aggregate-control files prohibited by the operator contract.

```text
repository: abbudjoe/gic-lab
destination: phase-1/sira-pilot-autonomous-r2
branch: codex/t09-control-target-selection
worktree: /Users/joseph/.codex/worktrees/t09-control-target-selection
commit: d0aff8a47e92013773d9d05b2cd90fb741658b03
tree: a6801e99d8e6ed204bbfa49ca1f3f17ad8b793ec
parent_1: 450a10a51eda4c428f20b27d6b4aafc4f94d80f4
parent_2: ccab5f1255f5a397ce14f1ebec7d96068bda91bc
operator_attests_model: gpt-5.6-sol
operator_attests_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
live_authorization: false
scientific_interpretation_allowed: false
```

PR #12 is merged at the exact base and its exact reviewed head is parent two. The
original checkout and fresh worktree were clean. The requested branch and worktree
did not exist. No V17 plan/profile/command package/identity/overlay/receipt root/run
root or `AUTONOMOUS-0010` artifact existed, and the goal recorded zero active provider
instances plus external-and-not-present current-turn authority.

### Fixed-target occurrence inventory

The complete pre-edit `V16|v16` scan covered `src/giclab/control/`, `Makefile`,
`.github/workflows/`, `tests/control/`, `docs/`, and `control/`. Occurrences are
classified by role rather than blindly removed:

| Surface | Classification | Pre-edit disposition |
|---|---|---|
| `src/giclab/control/agent_check.py` import, selected-composition variable/identity check, error, and shadow contract | current target selection | replace with the one selected-runtime target |
| `src/giclab/control/cli.py` `_verified_capsule` calls and receipt-refresh contract lookup | current target selection | replace with the shared resolver; remove historical annotations |
| `src/giclab/control/cli.py` `v16-composition.json` write and binding reference | package filename/projection | derive `<selected-version-lower>-composition.json` |
| `Makefile` `category3-shadow --provider-contract V16` | current target selection | remove fixed selector; default to goal resolution |
| `.github/workflows/ci.yml` | no V16 occurrence | retain goal-selected Make path |
| `src/giclab/control/composition.py` consumed V16 blocker | historical observed identity | retain as exact historical evidence logic |
| `src/giclab/control/state_capsule.py`, `proofs.py`, `shadow.py`, `production.py` | no literal V16 selection | preserve; extend only typed target/capsule or root binding where required |
| `control/goals/EXP-0001.yaml` historical package and V16 absence basis | historical observed identity / package projection | retain V16 history; update only current subgoal/action and selected projection |
| `control/incidents/INC-T09-V16-LIFECYCLE-REGISTRY.json` | historical observed identity | retain immutable incident unchanged |
| `control/receipts/category3-shadow/*.json`, `agent-check.json`, `registry-completeness.json`, `incidents.json`, `state-capsule.json` | historical evidence fixture | retain until non-circular current-V16 rebinding |
| `control/receipts/v16-composition.json` and its binding entry | package filename/projection | retain current V16 filename; generation becomes target-derived |
| `tests/control/test_category3_shadow.py`, `test_composition.py`, `test_control_proof_forgery.py`, `test_incidents.py`, `test_production_coupling.py`, and `test_registry_validation.py` | historical evidence fixture | retain exact V16 adjudication and mutation coverage |
| `tests/control/test_cli.py`, `test_contract_capabilities.py`, `test_state_capsule.py`, and `test_version_lint.py` | test fixture | preserve useful V16 fixtures; add current/successor compatibility cases |
| `docs/DECISIONS.md`, `docs/PROJECT_STATE.yaml`, architecture/ADR/active plan, stabilization ledger/packet, and V15/V16 historical ledgers/packets | documentation | retain historical facts; update active PR 1.1 and PR 2 boundary projections |

The six active fixed selections are therefore the agent-check target, verified
capsule target, receipt-refresh target, mandatory shadow target, composition receipt
filename, and Make `category3-shadow` target. No active selection annotation is
accepted as historical identity.

### PR 1.1 DoD state

The authoritative CT-01 through CT-22 table and mapping are in
`docs/exec-plans/active/T09_CONTROL_PLANE_STABILIZATION.md`. CT-01 and CT-02 are met
by the identity evidence and inventory above. CT-03 through CT-22 remain
`not-started`; none may become `met` without the exact planned evidence.

### Pre-edit evidence

- `git fetch origin --prune` completed normally after one transient local ref-lock
  race was resolved; local and remote destination both resolve to the exact base.
- `make state-capsule` passed at the base and emitted V16/not-created V17, Category 3
  false, scientific interpretation false, and semantic SHA-256
  `1d0eed149c8869b5e5a69e7bc68b115bea6d59c6b9fb14f25ee30851bb7017c3`.
- `make agent-check` passed at the base for 14 contracts and all 16 required shadow
  scenarios; aggregate semantic SHA-256 is
  `7905e9f5fac085c2d9e627265f23f3d582f69cb5bc3c600a357cd6c233d017af`.

### PR 1.1 implementation evidence before receipt rebinding

One frozen `SelectedRuntimeTarget` now owns aggregate selection. It binds source,
goal-record SHA-256, historical and successor identities/status, selected provider
contract and plan, selected command-package SHA-256, package status, and false
authority/science flags. The same resolver is used by state-capsule, compose, shadow,
agent-check, and receipt refresh. An exact explicit selector must equal the
goal-derived target; no current/latest helper exists.

The current goal-derived receipt is:

```text
source: goal-record
historical_contract_version: V16
successor_contract_version: V17
successor_status: not-created
selected_provider_contract_version: V16
selected_plan_id: PLAN-EXP0001-PILOT-V16
selected_command_package_sha256: 377e45728dc53221e42e7910d0f13f14ed219dd947371c48d9730f1f3140507b
goal_record_sha256: 59b8f4e2aacd795db5bda02a54786c6cf5bf3c5a0a95228827352af349f178e0
semantic_sha256: 3ba8075fbb264d06a58830783d56b3ae91cfd85316c74ac7e52a8e56a2e48297
live_authorization: false
scientific_interpretation_allowed: false
```

A test-owned temporary package changes only the temporary goal/package data and one
in-memory equivalent of the future central declaration. It resolves:

```text
source: goal-record
historical_contract_version: V16
successor_contract_version: V17
successor_status: package-bound-not-authorized
selected_provider_contract_version: V17
selected_plan_id: PLAN-EXP0001-PILOT-V17
selected_command_package_sha256: 8821992e34769c936c9f4fed7ab92934701db27c104c2df399acca0e5f11d789
goal_record_sha256: 5a09e4e974a4d1024d569d8ef9ee36c1fd06297b98d6f3233a794c65c286222d
semantic_sha256: 53e14adc49ac69f7ef43e3602af42db26557417522daad57a520ce6ec634cad7
live_authorization: false
scientific_interpretation_allowed: false
```

That temporary successor passed 15-contract real-consumer registry completeness,
selected composition, the happy path plus all fifteen production-wrapper failures,
state capsule, agent check, CLI state-capsule, CLI shadow, receipt refresh to
`control/receipts/packages/v17`, and binding validation. Every scenario after package
resolution named the synthetic V17 command digest; `lifecycle-unsupported` alone
carried no command digest because it stopped during offline composition. Hashes of
every `REQUIRED_SHARED_SOURCES` member were identical before and after package
selection. Two equivalent temporary roots generated byte-identical JSON trees.

All target/package selection failures occur inside the filesystem-only resolver
before aggregate composition or an adapter boundary. Instrumented counts are:

```text
secret reads: 0
metadata requests: 0
provider calls: 0
condition reservations: 0
```

The new incident is
`control/incidents/INC-T09-CONTROL-FIXED-TARGET-SELECTION.json`, 2,028 bytes, file
SHA-256 `3f3fd02630a79e63474812b92e8d7a63e6b4b43387dec26c93c90dfb79210334`,
with immutable-facts SHA-256
`8de67dfbe99733d6f0bf7322b7fcda7cc975619b713948d414d5ba0689743408`.
Its exact target-selection and active-lint nodes pass alongside the retained V16
incident regressions.

Focused evidence so far:

- current/lightweight target selection and package-failure suite: passed;
- current capsule, incident, registry, CLI, composition, and version-lint suite:
  passed;
- full synthetic successor path plus equivalent-root byte determinism, rerun after
  direct command-byte validation and no-overwrite publication hardening:
  `2 passed in 330.61s`;
- Ruff and strict mypy over changed source: passed.

No V17 path exists in the working tree, no experiment artifact changed, no live
secret/provider/cloud/scientific operation ran, and all authority/science flags
remain false. At this checkpoint, CT-03 through CT-20 were met after the
non-circular current-V16 rebind recorded below; CT-21 and CT-22 still awaited final
gates and the draft PR.

### PR 1.1 non-circular current-V16 receipt rebind

The immutable implementation ancestor is commit
`c6f0d7af1f10b2b8b110d8225b2c54c1d2709fbd`, tree
`04926d20fd7743a1f3433b3fb1cb9b27e23582d1`. A clean-tree receipt refresh generated
24 files under the temporary exact package root `control/receipts/packages/v16`.
Its file matrix exactly matched the retained 24-file V16 root; the generated bytes
were copied into `control/receipts/`, and the temporary package root was removed.
No V17 receipt root was created.

```text
binding file SHA-256: 596e98cffb2be51ca69a746a0b718adb96ff8dae38a02fd578bdd9a44f0814f6
binding semantic SHA-256: 81d12b7794fe0475c172ed8949966947584160e389709409d096c3798dd5e196
source-binding file SHA-256: 2f2be3d5df421fef8e4e53b3bb85e97674cb3f977a024c23e7d516bd37fca944
source-binding semantic SHA-256: 51a72cd6bd8f38d90c12a09f118ac2e53615270fc370d63ba343e7df5a2e52ad
agent-check file SHA-256: a1301987e4e5ed42784ce14f19c57c8e62c9c3eca26991d096d52a4e8540bc81
agent-check semantic SHA-256: 0e04aa2c170a192b4734ce3d5a986dc66bbd0afae9fec244a9609f83f8a4e43b
state-capsule file SHA-256: 7bdb247a4e116390be5c7a07bfe1576265274f089db1ac6cf08ed6e029b76ba8
state-capsule semantic SHA-256: 474bb95a27777f421c9219828b4799c80ea16d9539717ba658de541a753916f5
V16 composition file SHA-256: a95a1cead6e5938eee424c14f89f0c703030d8f323d470f51c9ddcfc6063e95e
V16 composition semantic SHA-256: fecf96fa652648a03f83a6234835ed1b3b6f7148fb7f15e0a7c82367d9f826f2
```

The binding and all 24 transitive receipt files validate against that ancestor.
Proof-forgery, capsule, and non-subprocess incident focus reports 38 passed and one
intentional incident-regression node deselected; `make validate` passes. CT-17 is
met. At this receipt-rebind checkpoint, CT-21 and CT-22 remained pending final gates
and draft-PR CI.

### PR 1.1 final gates and direct review

The exact repaired candidate `4c3d82e0dd7f6f8e3163f9219c6e9e1904e3b7c7`
passed the complete local `make ci-check` in 953.17 seconds against exact base
`d0aff8a47e92013773d9d05b2cd90fb741658b03`. Base-relative pytest reports base
1,998 passed / 27 failed and head 2,031 passed / 23 failed after five symmetric
private-node deselections. There are zero newly failing nodes, zero missing base
collected nodes, zero missing base failures, zero invalid outcome transitions, zero
xfails/xpasses, and four inherited nodes newly passing. Raw full pytest reports
2,031 passed, 23 unchanged inherited failures, and five inherited skips in 710.89
seconds. No control test contains a skip/skipif/xfail marker.

```text
make format: passed; 201 files unchanged
make lint: passed; Ruff clean
make typecheck: passed; strict mypy clean over 82 source files
make validate: passed
make agent-check: passed in 70.20 seconds
make test: 2,031 passed; 23 inherited failures; 5 inherited skips
make site: 16 pages rendered; validation passed in 64.02 seconds
git diff --check: passed
make ci-check: passed in 953.17 seconds
```

Draft PR #13 is open at `https://github.com/abbudjoe/gic-lab/pull/13` against
`phase-1/sira-pilot-autonomous-r2`. It is draft, open, and has no auto-merge request.
GitHub Actions run `33504105523`, job `99843964275`, passed the exact candidate head
in 23m51s. This documentation-only closeout descendant must pass the same exact-head
local and GitHub gates before final handoff; no bound shared source changes in this
descendant.

Direct Sol/max self-review answers:

1. **Can PR 2 select V17 without editing shared aggregate control code?** Yes. The
   synthetic package changes only temporary goal/package data plus the in-memory
   equivalent of one central registration; every `REQUIRED_SHARED_SOURCES` byte is
   unchanged while registry, composition, shadow, capsule, agent-check, refresh, and
   binding validation select V17.
2. **Do state-capsule, shadow, agent-check, and receipt generation select the same
   target?** Yes. All consume one validated `SelectedRuntimeTarget`; current and
   synthetic aggregate tests cross-bind its version, plan, command digest, goal
   digest, and composition semantic digest.
3. **Can a caller select an incompatible historical or future contract?** No. An
   explicit selector must exactly equal the goal-derived selection. V15 fails in the
   current state, V16 fails after the synthetic successor is package-bound, and V17
   succeeds only in that package-bound state.
4. **Can an existing sealed receipt root be overwritten?** No. Exact package roots
   are reserved without replacement; sealed, partial, symlinked, absolute, escaped,
   and incompatible roots fail. The legacy V16 root is readable but is not a CLI
   overwrite target.
5. **Does target resolution occur before every effect boundary?** Yes. Aggregate CLI
   handlers resolve before composition/adapters, and malformed goal/package cases
   retain zero secret reads, metadata requests, provider calls, and condition
   reservations.
6. **Does adding V17 require only central declaration, package data,
   package-specific effects, and package-specific receipts?** Yes. The synthetic
   full path proves the shared controller/proof/production/aggregate/selection files
   require no byte change. Any future need to change them returns to a separate
   Category 1 repair.

All CT-01 through CT-22 outcomes are met. The terminal state remains draft review
required: no merge or auto-merge is authorized.

## PR #13 review 5078551304 repair assembly

Status: **local repair and validation complete; parity, PR update, and exact-head Actions pending**

The exact reviewed identity was verified before mutation:

```text
review_id: 5078551304
reviewed_commit: ccb5ee0fc454111a976c6de951d798a630a537b9
reviewed_tree: 4a5c617e3746cf3148b2d4dc85764e49d2096288
base_commit: d0aff8a47e92013773d9d05b2cd90fb741658b03
branch: codex/t09-control-target-selection
pr: 13
pr_state: open-draft-unmerged
auto_merge: disabled
operator_attests_model: gpt-5.6-sol
operator_attests_effort: max
implementation_delegated: false
```

The local and remote task heads matched the reviewed commit, the destination still
matched the exact base, the worktree was clean, the review contained exactly the
four supplied findings and no unresolved review threads, and no tracked V17 package,
receipt root, or `AUTONOMOUS-0010` identity existed. Goal and bound-receipt authority
and science flags remained false.

Exact root-cause inventory:

| Finding | Reviewed defect | Repair contract | Status |
|---|---|---|---|
| A | `validate_selected_runtime_target_document()` and capsule proof validation substitute the mutable working-tree goal; repository validation selects only one current root | Resolve a serialized target from exact goal bytes in its bound commit, enumerate every sealed root, and apply current-goal compatibility only to the active root | met |
| B | `_publish_receipt_tree()` creates the final root and moves children individually, so interruption can expose an unrecoverable partial root | Validate and sync one same-parent staging tree, then commit it to an absent final path with one no-replace directory rename | met |
| C | AST lint misses `V16_PROVIDER_CONTRACT` imports, aliases, names, and attributes | Track versioned provider-contract symbols and reject their use in active runtime code with narrow registry/historical exceptions | met |
| D | Goal/capsule names a resolved incident as blocker and recommends completed implementation | Separate nullable technical blocker, external governance gate, and next subgoal; cross-check blocker status against the append-only incident ledger | met |

The authoritative RC-01 through RC-12 evidence checklist and implementation mapping
are recorded in `docs/exec-plans/active/T09_CONTROL_PLANE_STABILIZATION.md`. No RC
item may become `met` until its focused evidence and the final exact-head gates pass.

### Review-repair implementation and focused evidence

Historical proof validation now has two explicit entry points. The ordinary
`validate_control_receipt_set()` validates a root only against immutable state bound
inside that root: `bound-goal-record.yaml`, the binding's exact control commit/tree,
the sealed registry receipt's exact registered-version set, package artifact bytes,
all constituent receipt bytes and semantic hashes, the complete scenario matrix, and
the exact shared-source binding at that commit. It does not consult the working-tree
goal for compatibility. `validate_current_control_receipt_set()` first establishes
that historical proof and then separately requires equality with the current
goal-derived target and current shared-source bytes. Category 3, generation, and the
one active repository root use the latter; retained roots use the former.

Repository validation enumerates `control/receipts/` plus every sealed
`control/receipts/packages/v<integer>/` root. It rejects a missing legacy root,
unsealed/unsafe package roots, duplicate version seals, version/path contradictions,
missing or added-conflicting artifacts, byte/semantic drift, invalid source ancestry,
and any state in which other than exactly one root is current-compatible. The first
simultaneous synthetic run exposed that V16 `not-created` was still testing V17
absence against the expanded working registry. Commit
`7d7fc964e883fb6ec593d14c57b5f8d4e146ec52`, tree
`1530c61f0bbf1429fa64a55f5dfcdc41e30add28`, corrected the primitive by resolving
historical absence/presence against each root's sealed registry receipt. The rerun
passed all 11 historical/current-root tests, including a current synthetic V17 root
and retained fully validated V16 root in the same temporary repository.

Receipt publication now prepares and validates one complete same-parent staging tree,
fsyncs every file and directory, fsyncs the parent, and commits the directory with
one native no-replace operation (`renamex_np(RENAME_EXCL)` on macOS or
`renameat2(RENAME_NOREPLACE)` on Linux). The final path is never created child by
child. A complete identical concurrent winner is accepted without replacement; a
concurrent or pre-existing unsealed root is atomically preserved at the deterministic
`.v<version>-unowned-partial-recovery` path before retry; and a sealed root is
immutable. The 11-case publication suite covers failure before publication, after the
first child, halfway through preparation, immediately before commit, immediately
after commit, post-publication validation, complete and partial concurrent creators,
an existing seal, an existing unowned partial root, and byte-identical equivalent
successes. Every failure leaves the final root absent or complete/sealed/byte-valid;
normal retry is not permanently blocked.

The AST lint detects `^V[1-9][0-9]*_PROVIDER_CONTRACT$` through direct imports,
aliases, loaded names, module attributes, assignments, returns, and calls throughout
active control modules. Central registry declarations pass. There is no historical
module allowlist: the tracked receipt reports an empty allowlist, and only exact
historical assertions with line-scoped annotations may use a constant. An annotation
cannot exempt assignment-based selection. All 23 lint tests pass and the repository
receipt has zero findings across 101 scanned files.

The goal and capsule now separate `blocking_incident: null`, the next technical
subgoal, and a typed external governance gate requiring independent exact-head review
and explicit merge authorization. A declared incident must exist and validate; a
resolved incident cannot be the current blocker; an unresolved incident remains
permitted. The recommended action consults external governance and remains truthful
both before merge and after merge pending a separately authorized V17 goal update.
Capsule, incident, and proof-forgery focused tests preserve false repository authority,
Category 3, live authorization, and scientific interpretation.

The implementation commits before receipt publication are:

```text
primary four-finding implementation commit: 55fc82f0e56a42890c76bbb13ce0a301eaed9b56
primary implementation tree: f68314de3dfe779c6d14e9eddffb4f095f341a9b
historical-registry closure commit: 7d7fc964e883fb6ec593d14c57b5f8d4e146ec52
final immutable implementation tree: 1530c61f0bbf1429fa64a55f5dfcdc41e30add28
```

The corrected clean ancestor generated 25 V16 files, including the bound goal
snapshot, and the exact generated tree was projected into the retained legacy root.
The temporary package-V16 root and its obsolete first-generation stash were removed;
no package-V17 root was created.

```text
binding file SHA-256: f3007917cd0d1a521225136e077578b16d3785a8b0f625befedaf61f25df7a3b
binding semantic SHA-256: d90907feaa2cbe3ddbedbfe307c247fb0742b7238d8c5df8bdb490d382c81ea0
bound goal bytes: 2222
bound goal SHA-256: 81fbc17fd66de0d5b5010bb1ff93e8868dd4ec0be59cb8e146b3171b19f5d7f6
source-binding file SHA-256: a850cfce493ec9712caf6d8b41f0fe4493ba8388d2e0f4ef7d2b35577ce80eff
source-binding semantic SHA-256: 99e96addaf59b11cc2e7615cdc217959b2b67945a92d3909caadcbcaa514e61f
agent-check file SHA-256: 69d701e21fcb5745acb91a15ed98efc5908b843cee4f726505566487d5b1b2fa
agent-check semantic SHA-256: 57ab3d7257e15d4142f7a8276166aac73bf28a0c6dfd8568ca8755d62bd8ac6c
state-capsule file SHA-256: 06dc572c3432e56897f1637f1c6adba99d5ed7bb1f19a1cf646ee7590a22d65b
state-capsule semantic SHA-256: eaf2a628e3bfb258728ca3c7304023718b19f1709be14e325d8f3f0dff151e98
V16 composition file SHA-256: e6aba2bb32660ced0a924b4656ab9f41837a69bf7cb9b8cce040507580dffaeb
V16 composition semantic SHA-256: 165f859a953a0bb4f1e407ad75b2effaa5348a7a03c63dfc4e5a72cdfedfd5c1
```

The fixed-target incident remains resolved and append-only. It is 2,186 bytes with
file SHA-256 `c7cf0d3f2b3c84e13a7f7877657535284d91cc7fac7a5b6e51c41729b5513681`
and unchanged immutable-facts SHA-256
`8de67dfbe99733d6f0bf7322b7fcda7cc975619b713948d414d5ba0689743408`.
Its four exact regression nodes pass.

Focused ordering assertions remain:

```text
real secret reads: 0
metadata requests: 0
provider calls: 0
condition reservations: 0
```

At this checkpoint RC-01 through RC-11 are met. `make validate`, the 48-test
publication/lint/capsule/incident batch, the 21-test target/error/aggregate batch, and
the 11-test simultaneous historical/current-root batch pass. RC-12 remains
in-progress until the full/parity/static/privacy/site gates, exact descendant commit,
draft-PR update, and exact-head GitHub Actions complete.

The complete focused review-repair batch covers target selection, historical/current
roots, publication interruption, direct-constant lint, capsule/incident consistency,
proof forgery, production coupling, registry completeness, and all shadow scenarios:
**176 passed, 0 failed, 0 skipped** in 665.74 seconds. The final raw repository suite
reports **2,067 passed, 23 inherited failures, and 5 inherited private-fixture skips**
in 774.57 seconds. The sole stale review-repair-era test was corrected in ordinary
descendant commits `864fe50856657ac9e521c112d02b70fc968383e6` and
`baca8d77395d2f55975b5a1887639fbea9ec142c`: it now mutates the actual sealed
`agent-check.json` bytes and proves the historical root rejects the bound-file hash
drift, instead of mocking the retired current-goal projection loader.

Final local static and orientation gates at that descendant are green: Ruff format
and lint cover 203 files, strict mypy covers 82 source files, `giclab-validate all`
passes, `make agent-check` selects goal-derived V16 across 14 registered contracts
and all 16 shadow scenarios, and pinned Quarto 1.9.38 renders all 16 public notebook
pages before `giclab-validate site` passes. `git diff --check` is clean. Exact
base-relative `make ci-check`, the PR update, and exact-head Actions remain before
RC-12 can become met.
