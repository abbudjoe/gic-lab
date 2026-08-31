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
- 2026-08-31 source binding: commit
  `9d4fef32cbf2bd8859701b4b14410f77a0201543`, tree
  `2ccd8eeb79030fa401e28f2c7edbdfa40da598ff`, six shared runtime sources, semantic
  SHA-256 `3c0451b3a9fd528e36d3f505956adc7986d3b15f05dd481724466f6bf1042cbf`.
  `giclab-validate all` passes with unchanged scientific/package artifacts and no
  future package identity.

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

Pending. Review will cover the single source of runtime behavior, identity versus
capability, complete registry coverage, shared shadow/live control flow, effect
isolation, pre-secret ordering, authority/science separation, capsule legibility,
incident accretion, resource economy, and the future V17 package boundary.
