# T09 control-plane stabilization implementation ledger

Status: **review repair complete; independent exact-head rereview and explicit merge authorization pending**

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

The first exact-base parity attempt failed closed with zero newly failing tests but
identified one missing base node: the strengthened capsule regression had been
renamed from
`test_state_capsule_represents_v16_incident_and_v17_absence`. The exact historical
node ID is retained while its assertions now prove nullable technical-blocker state,
resolved-incident provenance, the external governance gate, and V17 absence. This is
a test-identity preservation descendant only; it does not alter bound implementation
source or receipts. Final exact-head parity must be rerun after this correction.

## PR 1.2 live-capable production-effects repair assembly

Status: **complete — draft review required; closeout descendant exact-head GitHub
confirmation pending**

Target contract: the same `execute_category3_transaction` state machine and
`build_production_adapter_assembly` must accept an effect-neutral execution context,
package-specific low-level effects, and an externally validated fully bound authority
grant. Shared production source owns policy, validation, transitions, and accounting;
effects perform only requested typed operations. Deterministic CI binds the same
interfaces and assembly with no network or real effects.

```text
repository: abbudjoe/gic-lab
destination: phase-1/sira-pilot-autonomous-r2
branch: codex/t09-live-capable-production-effects
worktree: /Users/joseph/.codex/worktrees/t09-live-capable-production-effects
commit: f1d872d59c4952eb98467c2506850af7772f4454
tree: eb70e20024559d65b3fadd240f72d3522895ef04
parent_1: d0aff8a47e92013773d9d05b2cd90fb741658b03
parent_2: 658a5f21cc24b914c6fc494f391cefe35d0fa334
operator_attests_model: gpt-5.6-sol
operator_attests_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
live_authorization: false
scientific_interpretation_allowed: false
```

PR #13 is merged at the exact base; its reviewed head is exact parent two. The
original checkout and fresh worktree were clean. The requested branch and worktree
did not exist. No actual V17 plan/profile/condition/command package/authorization/
receipt root/run root or `AUTONOMOUS-0010` artifact exists. Retained public state
records external-and-not-present current authority and zero active provider instances.

### PR 1.2 assembly ledger

The authoritative LE-01 through LE-23 checklist, evidence requirements, and mapping
are in `docs/exec-plans/active/T09_CONTROL_PLANE_STABILIZATION.md`. LE-01 through
LE-23 are met by the exact immutable-base audit, implementation, focused conformance,
non-circular receipt rebind, local exact-base gates, draft PR #14, and its successful
first exact-head GitHub Actions run. The review-state-only closeout descendant that
records those external facts must pass the same exact-head gate before handoff.
Direct Sol/max self-review is mandatory; no subagent, model, thread, or task may
perform implementation, testing, review, Git, architecture, or scientific work.

### PR 1.2 planned source contracts

| Workstream | Source contract | Mapped DoD | Status |
|---|---|---|---|
| Shadow inventory | Every fake/scenario/canned/fixed assumption classified and moved below the shared effect-neutral boundary when behaviorally active | LE-02, LE-12, LE-16 | met |
| Runtime time | One injected monotonic/wall/sleep protocol with finite, nondecreasing, nonoverflow validation | LE-03 | met |
| Metadata/secret | Exact mutable credential buffer reaches one injected channel and is destroyed on every path | LE-04 | met |
| Package budgets | Exact aggregate/per-condition/order/model/tier/retry caps loaded from selected package documents | LE-05 | met |
| Condition session | Typed exact request and real-time typed event observer; shared retained budget boundary is the sole authoritative accountant | LE-06, LE-07 | met |
| Host transaction | Typed tracked archive, provider-entry, host qualification, image/runtime/browser/finalizer, and dynamic freeze receipts | LE-08 | met |
| Evidence chain | Exact file-backed raw manifest/receipt/ledgers feed offline finalizer and evaluator | LE-09, LE-10, LE-11 | met |
| Effect separation | Scenario-free live production assembly; shadow fault plan lives only in deterministic effects | LE-12 | met |
| Authority/loader | Fully bound authorization context plus exact path/hash/factory/protocol package-effect loading | LE-13, LE-14 | met |
| Conformance/control proof | No-network live-shaped temporary package, anti-shadow lint, schema/receipt/agent-check binding | LE-15, LE-16, LE-17, LE-18 | met |
| Preservation/handoff | Historical V16 proof, no-V17/false boundaries, tracked rebind, local full/parity gates, draft PR, and first exact-head CI pass | LE-19 through LE-23 | met |

The host transaction additionally gates bounded replacement on
`ReplacementEligibleFailure`, which is emitted only after the production wrapper has
validated a retained provider-entry or host-preflight closeout. Generic failures and
receipt mutations cannot authorize a second launch.

### Authoritative condition-accounting decision

Option A, real-time typed event observation, is selected. The package condition
engine emits stable call/action/output/process/raw-publication events through an
observer supplied by the shared production wrapper. The wrapper applies the retained
`ProviderBudgetBoundary` in event order and validates the final outcome against that
single ledger. The effect may execute the exact remote runner but cannot maintain a
second authoritative accountant or choose caps/scientific policy. This decision must
be proven by multiple-call, multiple-role, known-error, ambiguous-send,
response-known/accounting-incomplete, admission, and zero-retry regressions.

### Exact-base shadow-assumption inventory

The machine receipt records these twelve source-proven assumptions against base
`f1d872d59c4952eb98467c2506850af7772f4454`, tree
`eb70e20024559d65b3fadd240f72d3522895ef04`. Each was a shared
production-wrapper defect at that base; deterministic equivalents are legitimate only
in `shadow_effects.py`, tests, or historical documentation.

| ID | Exact base source | Defect | Repair boundary |
|---|---|---|---|
| SA-01 | `production.py:73-74,105,160-163,415-417` | fake credential constants/equality and preconstructed metadata response | exact mutable parser credential to injected one-send metadata channel |
| SA-02 | `production.py:568-580,1305-1314,1670` | synthetic clock/sleep and fixed freeze/checkpoint epochs | validated injected monotonic, wall, and sleep domains |
| SA-03 | `production.py:1027-1076` | synthetic three-field stage payload | tracked-only archive plus request-bound acknowledgement and host rehash |
| SA-04 | `production.py:1238-1272` | reconstructed reduced provider-entry document | exact retained launch receipt consumed by typed preflight |
| SA-05 | `production.py:1274-1314` | synthetic qualification/freeze identities | request-bound host receipts and dynamic manifest hash |
| SA-06 | `production.py:1404-1503` | fixed caps, one CRITIC call, one browser action, shadow call IDs | exact package caps and arbitrary valid typed condition event stream |
| SA-07 | `production.py:1505-1543` | in-memory synthetic raw identities | exact file seal, call/action ledgers, process/completion evidence, export acknowledgement |
| SA-08 | `production.py:1545-1591` | synthetic finalizer paths/interpreter/dependencies | qualified-local effect request, pre/post raw seal, exact completion binding |
| SA-09 | `production.py:82-89,1593-1651` | canned task answers replaced condition output | evaluator consumes effect-produced finalized session |
| SA-10 | `production.py:38,148-286,568,979-1025,1743-1785` | `FakeScenario` required by and branched within production | `ShadowFaultPlan` exists only in deterministic effects |
| SA-11 | `adapters.py:25-74` | authority bound only a version/revision surface | full control/package/proof/effect/root/external authorization context |
| SA-12 | `production.py:75-76,249,286-382,614` | synthetic network/model/browser/image/provider fixture data in shared source | all fixture values below the effect boundary |

Current scanning classifies every retained occurrence as one of: legitimate
deterministic effect fixture, historical test fixture, documentation, or shared
production-wrapper defect. The last class is required to remain zero.

### Immutable implementation and receipt evidence

The live-capable implementation was committed without receipts as
`3488d986f7c16adc54adbc092a0c3b8457baca82`, tree
`e2b6260989b9a827cc543253a664df1541b50f68`. The historical duplicate-root
regression then received an ordinary descendant repair at immutable implementation
ancestor `cd9bed46576bd00af473af861c57800b4f350c9d`, tree
`8d34019a2d7addcf34ff35f507f82dea99ef38dd`. No history was rewritten.

Receipt descendant `d273910b2deb11dcd37dee33123f29bac7aeedcd`, tree
`486d701590574240ee6d5abdc2b2eea3a1181256`, regenerated the current 27-file V16
receipt root against that ancestor. Its control binding file SHA-256 is
`eae9100ffd6380346f35255ec0dc60d1ad4f62ef8c985b18a87a72ccc5e37c98` and semantic
SHA-256 is `bc19a164232c58a53d7ac4873917b509597a433e5967ea19a135cc2be84fef91`.
The source-binding receipt is 6,662 bytes with file SHA-256
`d9f9c2e75a18de569a928e4301b5cb96afb9393db1c6366eb964a6f5f8cd6dee` and semantic
SHA-256 `24e17e26142e808ffc8eb2e603199af929ee8f19491777885adf69a56ea05f96`.

`control/receipts/packages/v16/live-effect-conformance.json` is 8,623 bytes with
file SHA-256 `eb6cb0b9e15e331063213630a1e3cdc1fb9567f041bf43edeb8e041cfea5ef98`
and semantic SHA-256
`2a001bb775fbf7e8755f23b1f1ed4f70bb083ac2c65cdfd7f3f180f3d6c1500a`.
`control/receipts/packages/v16/anti-shadow-lint.json` is 7,059 bytes with file
SHA-256 `3ebe48bf443e894fded999e9c664e511537def9402f95a17ba7f6da80b7ac7cf`
and semantic SHA-256
`1612ceded30c71c0c46ef41e0859dce813dbed10a40aeceaa39e0758b0b7698f`.
The incident
`control/incidents/INC-T09-CONTROL-SHADOW-SHAPED-LIVE-BOUNDARY.json` is 3,490 bytes,
has file SHA-256 `fe5f69d3241032e2216110d1a3a6b47f37b68efb99d54e3541d9825d2ce70a85`,
and immutable-facts SHA-256
`77acccfd3017357271e2d1cda5b1ac9433899a3e9dcf4377d57662381f05d442`.

### Local final-gate evidence

At draft-PR head `5d047f3961c9d7ecd87c87362be07bfcf3cf2c12`, tree
`3ed1723bc985daf4680a828a9dd4cb0ed0d5cc0a`, Ruff format and lint, strict mypy over
86 source files, repository validation, goal-derived
agent-check, privacy/static checks, pinned Quarto 1.9.38 rendering of all 16 pages,
site validation, and `git diff --check` pass. The raw suite reports 2,113 passed and
23 inherited base failures plus the same five inherited private-fixture skips; it
adds no skip or xfail. The exact-base parity harness passes: zero newly failing nodes,
zero missing base collected nodes, zero missing base failures, zero invalid outcome
transitions, four newly passing nodes, and five symmetrically deselected unavailable
private-fixture nodes. The final documentation descendant must rerun this exact
command set before push.

### Draft PR and first exact-head GitHub evidence

Draft PR #14, `T09: make the production controller live-capable`, is open at
`https://github.com/abbudjoe/gic-lab/pull/14` against
`phase-1/sira-pilot-autonomous-r2`. It remains draft, unmerged, and has no auto-merge
request. GitHub Actions run `33580584620`, job `100093827365`, passed in 1h00m51s
against exact head `5d047f3961c9d7ecd87c87362be07bfcf3cf2c12`. Its deterministic
agent/control-plane gate and exact-base PR parity gate both passed; the parity result
reported zero newly failing nodes, zero missing base collected nodes or failures,
zero invalid outcome transitions, three newly passing nodes, and five symmetrically
deselected unavailable private nodes. GitHub emitted only its action-runtime Node 20
deprecation annotation. This documentation-only closeout descendant is subject to a
fresh exact-head Actions run before terminal handoff; that final run is necessarily
reported outside the commit it validates.

### Direct Sol/max source review

The operator-attested direct review found no unresolved item and used no delegated
agent, model, thread, or task. Its required questions close as follows:

1. **Actual credential without fake substitution — yes.** `ModelMetadataChannel`
   accepts the mutable parser-selected credential (`effects.py:333-342`), and the
   wrapper forwards it without value comparison while using the injected wall clock
   (`production.py:256-273,701-806`). Success, channel rejection, one-send behavior,
   and buffer destruction are exercised at
   `test_effect_runtime_seams.py:151-206`.
2. **Injected real time and sleep — yes.** `_ValidatedRuntimeClock` preserves separate
   monotonic/wall domains and delegates sleep (`production.py:219-253`); the world,
   metadata boundary, freeze, condition admission, checkpoint, and cleanup all use
   that instance (`production.py:516,748-830,1815-1905,1973-1993,2152-2165,
   2662-2686,2752-2807`). Live-shaped delegation plus backward/nonfinite/overflow
   failures are covered at `test_effect_runtime_seams.py:109-149`.
3. **Arbitrary valid multi-call/multi-role/multi-action conditions — yes.** The typed
   request/event/outcome protocol is at `effects.py:543-641`; the sole authoritative
   observer applies the retained boundary per event and reconciles exact ledgers at
   `production.py:359-496,2025-2280`. Reactive and simulative multi-event shapes and
   known/ambiguous/accounting-incomplete sends are asserted at
   `test_live_effect_conformance.py:57-107`.
4. **Exact package-derived caps — yes.** Plan, execution contract, condition plan,
   command manifest, attempt order, model, tier, and zero retry are cross-validated at
   `production.py:1002-1318`. Exact values, plan drift, and cross-condition
   substitution are covered at `test_effect_runtime_seams.py:209-243` and
   `test_live_effect_conformance.py:110-149`.
5. **Raw evidence reaches finalizer and evaluator — yes.** Exact files and ledgers are
   validated during condition acceptance/export; the raw seal is checked before and
   after offline finalization; evaluation consumes only the finalized root and
   session hashes (`production.py:2166-2639`). Raw mutation, completion/finalizer
   drift, and effect-answer propagation are covered at
   `test_production_coupling.py:245-411` and the complete chain at
   `test_live_effect_conformance.py:152-175`.
6. **A package-only successor can supply effects and authority — yes.** Registration
   validates an exact tracked regular path/hash/size/factory/protocol before import,
   and loading requires a package-owned live grant over the full context
   (`effects.py:861-1023`). The production assembly then revalidates control, package,
   implementation, transaction root, and grant (`production.py:2945-2996`). Loader
   mutation coverage is at `test_package_effect_loader.py:97-300`.
7. **Shadow exercises the same wrapper — yes.** Deterministic effects implement the
   same `LowLevelEffects` protocol by composition, while both conformance and shadow
   enter `build_production_adapter_assembly` and `execute_category3_transaction`.
   Exact entry points and unchanged shared-source bytes are asserted at
   `test_live_effect_conformance.py:25-55`; all retained production-wrapper scenarios
   are asserted at `test_category3_shadow.py:69-286`.
8. **No fake/scenario/canned-answer assumption can alter live behavior — yes.** Shared
   production imports no fault plan and contains no deterministic credential, canned
   answer, fake time, shadow call ID, or scenario branch (`production.py:1-7`). Those
   values live below the boundary in `shadow_effects.py`; the narrow lint and injected
   forbidden-token mutations are asserted at
   `test_live_effect_conformance.py:178-204` and are bound into the V16 receipt root.

## PR #14 exact-head review 5088727234 repair assembly

Status: **review repair and exact-head gate evidence complete; independent external
rereview and explicit merge authorization pending**

The pre-edit audit verified PR #14 open, draft, unmerged, based on
`f1d872d59c4952eb98467c2506850af7772f4454`, with auto-merge disabled. Both the
remote PR head and task branch were exactly
`3291af1e64ec1ea89b8773a586c97a917f1052a2`, tree
`69b7d0346456cad080ca258bc137662d7d632d26`. Exact-head Actions run
33589428237/job 100120211545 was successful; review 5088727234 was the only review
state and required changes. The destination, original checkout, task worktree,
authority/science flags, and no-V17 boundary all matched the operator contract.

No implementation, testing, review, Git, architecture, or scientific decision was
delegated. The operator-attested model/effort were `gpt-5.6-sol` / `max`; runtime
metadata was neither inspected nor used.

### Four repaired findings

- **Checkpoint:** `ProductionCategory3World.checkpoint` revalidates both Task A raw,
  finalizer, evaluator, command-pair, and retained selection records. It obtains typed
  provider lifecycle cost, authoritative aggregate usage, injected-clock wall values,
  and conservative frozen-plan projection, then calls retained
  `first_pair_decision`. The controller treats `stop-before-task-b` as a clean stop
  with zero Task B reservation/entry and persists the exact returned reasons.
- **Failure evidence:** condition execution returns typed success or infrastructure
  failure outcomes. Every post-entry infrastructure failure is reconciled, sealed via
  `mark_essential_failure_sealed`, bounded to 67,108,864 bytes, exported,
  acknowledged, consumed, unscored, nonretryable, and followed by cleanup. Nonzero
  exits never reach finalizer/evaluator, including completed outcomes with answers.
- **Authority:** a package may supply external overlay source/policy but cannot mint a
  trusted grant. The shared validator calls the selected contract's authorization
  validator and alone mints opaque `ValidatedLiveEffectAuthority`. One durable private
  state transaction binds effect, metadata, launch, cleanup, and terminal consumption;
  reservation precedes secret access and any failure/replay is nonreplayable.
- **Held identity:** effect bytes execute from a held no-follow descriptor and exact
  Git blob, not `spec_from_file_location` or `.pyc`. Shared code derives and holds the
  transaction-root device/inode/owner/mode/mount identity. Raw, finalized, and
  evaluator artifacts remain sealed and descriptor-held across consumers. All held
  resources are released only after cleanup and terminal evidence materialization.

The authoritative condition accountant remains the production wrapper's real-time
event observer. Deterministic fault injection remains entirely below the shared
effect boundary. Runtime-only paths, inode values, and private authorization hashes
are not published; the conformance receipt contains stable semantic attestations, and
equivalent successor repositories produce byte-identical complete receipt trees.

### Immutable implementation and rebound receipts

The core source/test/control-input commit is
`e4e65ef24b97151c09fc9ccfe1e0d0083f797a1e`, tree
`2de4e90efa2d85b5c4662bc8f47f72375659acae`, directly descended from the reviewed
head. The first immutable implementation ancestor used for receipt generation was its
ordinary source-closure descendant
`adafa96342d0c407189cd0b260cf017fb4d79f3e`, tree
`45562750df7fa3935c3b7b1af37e4c63bf244caa`. That descendant only renames the Python
authority-state member that collided with the repository secret scanner; the durable
serialized state remains `reserved-before-secret`. Full-suite evidence then exposed
that a Task B essential-failure export carried checkpoint state without the newly
authoritative checkpoint decision receipt. Ordinary compatibility-closure commit
`4163cad097767f6056cb21792d3d6d5894f2ccd7`, tree
`eb733fa3ecc5e8b306928badfe61a3c2c24e04e3`, adds that decision receipt to the bounded
control snapshot, its allowlist, and the restored identity assertion. Exact-base
parity then caught that the repaired raw-export phase changed one automatic pytest
parameter ID. Ordinary parity-identity closure commit
`7a809850722c175d01dc1567b73680995908072e`, tree
`909c9afe42e6ca7845aed3c5b0453b3846d78004`, preserves the exact historical node ID
while continuing to assert the repaired `condition-execution` phase. It is the final
immutable implementation ancestor. The 27-file current V16 receipt root was generated
from that clean ancestor in an external staging directory and copied only after its
file inventory matched the existing sealed root.

```text
control binding file bytes: 9288
control binding file SHA-256: 472279d990fe21eac36972917622677b38af3f415c9542b17e56580c73e9e12f
control binding semantic SHA-256: a6316e56acf4dbba20edc8695e82b3f97d47e1cc95d59a58049a3d1e155d69d0
source binding bytes: 6662
source binding file SHA-256: 5b27d7c96cb839093b0863c0107df51c6e46011d86111331e7ebc1d024c92ccf
source binding semantic SHA-256: 807fc0e4d05dec675784a5f79093c3fcec4c1e9e041536744a3fdac896ecbe4b
live-effect conformance bytes: 14804
live-effect conformance file SHA-256: ae01346a70d8702e6629b7bd6fb39e7f94cc818e8aa72b44b8d17fcf5ba423a6
live-effect conformance semantic SHA-256: 6342b6dd78fee0b5b21c85c91ae2a69ec55a0b6fb45f6cc6a6494c764e675a1a
anti-shadow lint bytes: 7134
anti-shadow lint file SHA-256: fb176cb2967e78b5e5f11c01c5bfa21120b4c9d5b719fc761947ce3fed8a22bb
anti-shadow lint semantic SHA-256: 7d69061004f6bb1426455bb1c2319e0c23a7cb6c90acc6355ad1c8773466bf5c
incident aggregate bytes: 6091
incident aggregate file SHA-256: 78fc4a9c63ddb2299c02a50a85b9c97cd50a79d7090d015aa112c60c637417ab
incident aggregate semantic SHA-256: 637f14d39d020d190f77d884b0fdc6c264ea5cd46273d704001727b7c4017edc
review incident bytes: 5746
review incident file SHA-256: a78c5f9b6fe1b2274673089cab22ef325fafeebaec79a9d5e94fdca87597d112
review incident immutable-facts SHA-256: 3718f419cb03edda7e2b781f2858caffae589dc1918ead2fa05621e1468ccd52
```

### Focused evidence and DoD state

The consolidated checkpoint/failure/authority/loader/held/conformance/shadow/coupling
matrix passes all 173 collected nodes. All 20 exact review-incident nodes and every
older incident node pass. The historical receipt suite passes 11 nodes. The complete
temporary successor path passes, and the two separate-copy successor receipt roots
are byte-identical. Ruff format/lint, strict mypy over 86 source files, schema checks,
and `git diff --check` pass at the implementation ancestor.

| ID | Required outcome | Status |
| --- | --- | --- |
| RR-01 | Exact PR/base/head verification preserved | met |
| RR-02 | Accepted effect-neutral architecture preserved | met |
| RR-03 | Retained `first_pair_decision` is authoritative | met |
| RR-04 | Both Task A attempts valid and scored before Task B | met |
| RR-05 | Pair/finalizer/cost/time/cleanup gates enforced | met |
| RR-06 | Clean checkpoint stop remains operational and nonscientific | met |
| RR-07 | Every post-entry failure yields bounded essential evidence | met |
| RR-08 | Nonzero exits are infrastructure-invalid and unscored | met |
| RR-09 | Failure evidence sealed/exported/acknowledged/nonretryable | met |
| RR-10 | One opaque external authority transaction owns all phases | met |
| RR-11 | Contract authorization prefix/source enforced | met |
| RR-12 | Live authority is single-use and non-forgeable by duck typing | met |
| RR-13 | Effect source is held and exact bytes execute | met |
| RR-14 | Transaction-root identity is shared-derived and held | met |
| RR-15 | Raw/finalized/evaluator paths remain held and sealed | met |
| RR-16 | Updated conformance proves all four repairs | met |
| RR-17 | Package-only V17 boundary remains truthful | met |
| RR-18 | Historical V16 proof remains valid | met |
| RR-19 | No actual V17 artifact exists | met |
| RR-20 | Science and authority remain false and unchanged | met |
| RR-21 | Full/parity/static/privacy/site gates pass | met — exact final-head results are recorded in the PR #14 handoff comment |
| RR-22 | Draft PR updated and exact-head Actions green | met — exact run/job/head are recorded in the PR #14 handoff comment; rereview remains external |

The linked review incident is resolved, `blocking_incident` is null, and independent
exact-head rereview plus explicit merge authorization remains the external governance
gate. The next technical subgoal is package-only V17 generation after reviewed merge.
No live authorization, secret, provider, cloud, browser, SiRA, evaluator, condition,
or scientific execution occurred; added OpenAI/provider cost is USD 0.00.

## PR #14 second exact-head rereview 5097085114 repair assembly

Status: **repair and non-circular receipt regeneration complete; exact-final-head gates pending**

The pre-edit audit verified exact reviewed head
`a4b0fef4c8e2dd98941fd5f812acc208b8a5e47f`, tree
`32986899e94f980bdf648872cb82cb8f3b8c1700`, against unchanged base
`f1d872d59c4952eb98467c2506850af7772f4454`, tree
`eb70e20024559d65b3fadd240f72d3522895ef04`. PR #14 remains open, draft,
unmerged, and without auto-merge; exact-head Actions run 33687000382/job
100436733425 remains successful. Review 5097085114 is the only newer review and has
no unresolved thread. The task worktree, destination, branch head, no-V17 boundary,
and false repository/Category 3/live/scientific authority state all match the
operator contract.

No implementation, testing, review, Git, architecture, or scientific-boundary
decision is delegated. All evidence is deterministic and network-disabled.

### Residual findings and planned evidence

1. **Provider lifecycle cost:** replaced effect-authoritative self-consistent cost with
   a shared-derived proof over the exact provider profile/price source, retained
   provider entry/ownership/closeout intervals, prior preflight history, injected
   wall/monotonic observation, and exact monetary arithmetic. Checkpoint safety
   defaults are removed. Evidence: direct lifecycle mutation matrix and checkpoint
   coupling tests pass.
2. **Essential failure envelope:** payload, manifest, completion receipt, and
   export acknowledgement inside one finite envelope; enforce exact canonical schemas,
   complete aggregate/member caps, held identities, and complete privacy traversal.
   Evidence: cap, schema, privacy, mutation, export, and inherited failure matrices
   pass.
3. **Held-root terminalization:** privacy scanning is descriptor-rooted after a
   pathname mismatch, return typed unresolved privacy state when needed, and guarantee
   authority terminalization plus all descriptor release through a controller-level
   `finally`. Evidence: full-controller root-replacement and injected terminal failure
   tests pass.
4. **Public runtime topology:** public evidence uses only the stable held-root projection
   and a
   repository receipt privacy gate for absolute runtime roots and device/inode/UID
   values. Evidence: fresh-root byte identity and injected topology tests pass. The
   old tracked receipt tree is deliberately rejected until non-circular regeneration.

### Second-rereview definition of done

| ID | Required outcome | Status |
| --- | --- | --- |
| SR-01 | Exact PR/base/head identity verified | met |
| SR-02 | Prior four headline repairs preserved | met |
| SR-03 | Provider price and intervals bind retained lifecycle evidence | met |
| SR-04 | Every consumed provider slot is cost-accounted | met |
| SR-05 | Provider cost cannot be understated by an effect | met |
| SR-06 | Mandatory checkpoint evidence has no pass defaults | met |
| SR-07 | Complete essential envelope is finitely bounded | met |
| SR-08 | Every essential envelope member is schema/privacy validated | met |
| SR-09 | Terminal privacy scan includes failure envelopes and exports | met |
| SR-10 | Root pathname replacement cannot escape controller terminalization | met |
| SR-11 | Every reserved authority exit reaches a terminal single-use state | met |
| SR-12 | Descriptor release is guaranteed | met |
| SR-13 | Public/tracked receipts retain no runtime topology | met |
| SR-14 | Updated conformance proves all residual repairs | met |
| SR-15 | Incident and state capsule are truthful | met |
| SR-16 | Historical V16 proof remains valid | met |
| SR-17 | No actual V17 artifact exists | met |
| SR-18 | Package-only V17 boundary remains truthful | met |
| SR-19 | Authority and scientific interpretation remain false | met |
| SR-20 | Full/parity/static/privacy/site gates pass | not-started |
| SR-21 | PR body reflects exact final identities | not-started |
| SR-22 | PR remains draft, unmerged, and auto-merge disabled | met |

### Focused and non-circular receipt evidence

The four focused files collect 134 tests: 56 checkpoint/provider-lifecycle tests, 42
essential-envelope tests, 25 held-identity/terminalization tests, and 11 conformance
tests. Before receipt regeneration, 133 passed and the topology gate deliberately
rejected the old tracked V16 root. After the root was regenerated, the previously
failing anti-shadow node passed with zero topology findings; the complete 134-node
rerun remains part of the exact-final-head gate sequence below.

Core source/tests culminate at commit
`be6f435003c5031071dac59fecd6a0ab0c45c892`, tree
`134d232b64c3c8957168d07705fd2d827bf64c8b`. Incident/goal/document inputs were
frozen at receipt-binding ancestor
`db32bba7b87cae7e08083d6f6b332b126f8ff57a`, tree
`3dc148643ddf610d2b3698898296de98381f827a`. The receipt descendant is commit
`39df4177fa8b89816c1cddbf884fa81a5d41ac4e`, tree
`443324a504d1900206e8d0bda12a5c9151f04d37`.

Exact regenerated identities:

- `live-effect-conformance.json`: 17,131 bytes; file SHA-256
  `dd4f58ce79b136c70daf2a3c19d7a14681771c3269f3cc279becaf5b7efec063`;
  semantic SHA-256
  `43de22eb09b4890e5f3fdab6e6e8b64dec9cb3fa5df5c44db66161e2ff13770b`.
- `anti-shadow-lint.json`: 7,648 bytes; file SHA-256
  `1ad1919eae920c31e105427f78f988228a8deae6c3d803ce26fd6441bf967745`;
  semantic SHA-256
  `cf2f6c3b76d81a9f332286e641871dbbe750727449bbd2dbfb47ae9667b56bd2`.
- `incidents.json`: 8,159 bytes; file SHA-256
  `ec85d7ebac2595732ff89914db50bf0088a80555018f5244f04cc0bf94c2bfc5`;
  semantic SHA-256
  `6a8eb978c5d245e655b098ebaa3ee341c84980fced74398d5b92ffc3f3b308c0`.
- source binding: 6,662 bytes; file SHA-256
  `61603781e0c06e5cc0294313e341c283d520abee64720947c3ee7620ed3ef1d9`;
  semantic SHA-256
  `cf3292e576ebd4d3fc909309c678f5979ff168822f693d9d053da4994e0a295c`.
- aggregate binding: 9,288 bytes; file SHA-256
  `59cd459072359c75395a796b2e7edbe0370d309bdd2596e894148f942c7d0038`;
  semantic SHA-256
  `f5c04f8d7ef31aad5dbfc9dc37cfba142bd4dcf962e8edd83e4f2120cd00dfeb`.
- linked incident source: 4,942 bytes; file SHA-256
  `f33aada9e8504f7eaf6805ec6df2c561e0be82d523d350533e2c99952402fa66`;
  immutable-facts SHA-256
  `5c419c5ef3e0777c7cb7199a66fb3fb73bf3880a44338e941a0bd4ecc2fa6a5d`;
  status `resolved`.
