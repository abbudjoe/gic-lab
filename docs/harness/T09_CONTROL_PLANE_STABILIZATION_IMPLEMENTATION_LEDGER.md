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
`docs/exec-plans/active/T09_CONTROL_PLANE_STABILIZATION.md`. Every item begins
`not-started`; evidence and final per-item states will be updated incrementally.

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

## Immutable control receipts

Every receipt below binds clean implementation ancestor
`5efbe727648ae9e7077132aa9bf3033e4b35ec03`, tree
`5fab7020bf157c6c31a68b1b2024ca10203d3106`, rather than its own commit.

| Receipt | Bytes | File SHA-256 |
|---|---:|---|
| `control/receipts/active-version-lint.json` | 4,937 | `223f8f11d910215f615145ffd972db62e7a602293f34a8a64bc37e7fbb05c612` |
| `control/receipts/registry-completeness.json` | 53,387 | `f889ae9ae2ca7857dfcf08c86459cb0b953a24417ccbf34e91fe7e4af4b2a03a` |
| `control/receipts/v16-composition.json` | 2,166 | `e85a6f11022cf7b8f0e855d6c3abd0d127dd3df7f5ca2756fc04ed0031a7abf4` |
| `control/receipts/category3-shadow/happy-path.json` | 20,417 | `49fbdc2f68a3604274dc1e44e388ee00efa0fbb9151f70491254bc510698ec81` |
| `control/receipts/state-capsule.json` | 2,750 | `5f529eddccf31cee3365937cd1d246fd6ae1daec5ee0d01ad7d13b66f0529a02` |
| `control/receipts/incidents.json` | 917 | `16205084add2ef9d2cb50f3907c7c5a94bb056ab4e19c5d0f66e679e2e66f4ab` |
| `control/receipts/agent-check.json` | 7,783 | `55f548bbfb206547bfd64bdef1fcc74b8627f0c9dca79707714d06595d531d77` |

The complete 12-file shadow directory has a canonical file-identity matrix SHA-256
of `1affe422c0b25ccf46fd717493ff9ccdd8c666877570ef1791ccdd788fa25904`.
`giclab-validate all` rejects a missing receipt, semantic drift, schema failure,
non-ancestor identity, incomplete scenario, or aggregate cross-binding mismatch.

## Control architecture evidence

- Capability source: `src/giclab/harness/t09_provider_contracts.py`.
- Version-dispatch lint: `src/giclab/control/version_lint.py`.
- Consumer completeness: `src/giclab/control/registry_validation.py`.
- Effect-free composition: `src/giclab/control/composition.py`.
- Shared transaction and strict fakes: `src/giclab/control/category3.py` and
  `src/giclab/control/adapters.py`.
- Happy/failure matrix: `src/giclab/control/shadow.py`.
- Agent orientation and incident accretion: `src/giclab/control/state_capsule.py` and
  `src/giclab/control/incidents.py`.
- Future package boundary: `schemas/t09-control-receipt-bindings.schema.json`.

## Direct review log

Direct review is complete with no remaining finding. It confirmed:

- `PROVIDER_CONTRACTS` and its plan-ID projection are the sole active registry;
  immutable version identity is separate from semantic capability dispatch;
- the repository AST gate reports zero prohibited active-version dispatches, and all
  14 registered contracts resolve their complete consumer/composition matrices;
- shadow rehearsal uses the shared Category 3 controller, while the only available
  adapters are strict local fakes and `PreparedCategory3.live_effects_permitted` is
  false;
- validated receipt mode blocks before staging/secret/metadata when its receipt set
  is absent, and the lifecycle omission stops at composition with all external-call
  counts zero;
- metadata, provider capability, scientific-attempt prefix, evidence, cleanup, and
  interpretation permission are separately owned transaction state. Review found
  the interpretation field had originally been emitted as a constant; commit
  `ac99cabc31e06d3d96d6467f670511c11080bedd` moved it into the typed state and the
  post-repair control suite and agent check pass;
- fake evaluator outputs remain shadow control evidence, ambiguous launch remains
  non-zero/unknown, and infrastructure failures never produce scientific scores;
- the capsule is concise, deterministic, public-safe, and never infers authority;
  the incident is hash-bound to three passing regressions;
- only the sanitized V16 disposition changed under the experiment tree, no V17 or
  `AUTONOMOUS-0010` artifact exists, no live adapter or authority was created, and the
  future package must bind the complete validated receipt set in a separate PR.
