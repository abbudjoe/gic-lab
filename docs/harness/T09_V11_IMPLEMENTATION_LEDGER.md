# T09 V11 Docker cidfile publication-race implementation ledger

Assembly status: **in-progress**

Started: 2026-08-28

## Source and target contracts

The authoritative task contract is `T09 V11 — Category 1 Docker cidfile
publication-race repair`, 17,159 bytes, SHA-256
`38023a00f3972b841b86279dc4092b0911aa4ec723a8b10f7e739189d64e34be`.
It is constrained by `AGENTS.md`, `docs/PLANS.md`, the active Phase 1 execution
plan, and the frozen EXP-0001 scientific contracts.

The exact base is `phase-1/sira-pilot-autonomous-r2` at
`1c6b093699288f37aa23526fe1e1672e50280093`, tree
`39501c69af3296ce271d38aa235c26d80175a4b1`, with parents
`503def0519e36f04b62b16158c72e11213b3bf9f` and
`a2b30012bdf09080da844451ad0d987dde5da646`. Work is confined to
`codex/t09-v11-cidfile-publication-race`.

The target is a descriptor-safe, publication-aware Docker cidfile reader that
preserves fail-closed metadata validation, exact daemon-published ID authority,
the existing command deadline, and exact-ID-only cleanup. The same package must
register fresh, statically unauthorized V11 identities without changing any
scientific field.

## Scope

In scope: the narrow cidfile reader repair; deterministic fake-only unit and
integration regressions; source-bound V11 runtime, execution, command, condition,
plan, schema, ledger, and preauthorization artifacts; local validation;
independent spec-conformance review; one commit series, one normal push, and one
draft PR.

Out of scope: credentials; provider or model requests; cloud mutation; paid
compute; live Docker, browser, SiRA, FanOutQA, evaluator, or scientific execution;
V8/V9/V10 evidence mutation or reinterpretation; empirical run roots; an
authorization overlay; merge or auto-merge.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| V11-DOD-01 | Exact repository, remote base, commit/tree/parents, clean start, retained zero-instance cleanup state, and immutable V8/V9/V10 evidence baselines are recorded before implementation. | Git identities, retained V10 closeout receipt, and deterministic evidence-root inventory hashes. | met |
| V11-DOD-02 | `_read_owned_docker_cidfile()` opens the exact path with no-follow/CLOEXEC where supported, validates the opened descriptor's regular-file/owner/link/write metadata, treats only a safe zero-length file as pending, and accepts only the exact prior 64-lowercase-hex format with its optional single trailing newline. | Focused reader unit tests, path-replacement regression, source review, and post-review smoke. | partial: implementation and first smoke pass; independent review and post-review smoke remain |
| V11-DOD-03 | Existing polling/deadline behavior remains bounded; durable authority begins only after a valid exact ID; changed IDs fail; timeout without publication never authorizes name-based removal; successful cleanup remains exact-ID-only. | Deterministic fake-process integration tests covering delayed publication, timeout, registration ordering, identity change, and cleanup. | partial: deterministic fake-process smoke passes; independent review and post-review smoke remain |
| V11-DOD-04 | The original transient-zero-length Category 3 sequence is reproduced against the old contract and passes under the repair without a live Docker daemon. | Focused regression fixture and exact failure-class assertion. | partial: focused regression passes; independent review remains |
| V11-DOD-05 | Fresh `PLAN-EXP0001-PILOT-V11` and `AUTONOMOUS-0004` host/attempt identities bind the repaired package; model metadata is ordered before Lambda launch; all scientific fields and all authorization/execution flags remain unchanged and false. | Canonical renderers, schema/hash tests, science projection, pair diffs, and exact plan bytes/SHA-256. | not-started |
| V11-DOD-06 | V8, V9, V10, and the stopped V10 Category 3 evidence remain immutable and V10 provider contracts remain version-addressable historical identities. | Start/end inventory equality, source diff, and historical contract regressions. | not-started |
| V11-DOD-07 | Focused smoke, formatting, Ruff, strict mypy, repository validation, privacy checks, raw suite classification, exact-base/head parity, diff check, and portable Quarto/site validation satisfy the task contract. | Exact commands, counts, and parity report recorded below. | not-started |
| V11-DOD-08 | Independent review finds the implementation and successor package conformant, or every valid finding is repaired and rereviewed before closeout. | Reviewer findings, dispositions, and post-review reruns. | not-started |
| V11-DOD-09 | Scope-reviewed changes are committed and pushed only to the task branch, and one draft PR is opened against the exact base with auto-merge disabled and no merge. | Final commit/tree, remote head/base, and PR state. | not-started |

## Implementation mapping

| Work item | Mapped DoD | Target contract |
|---|---|---|
| Descriptor-safe cidfile reader | V11-DOD-02, V11-DOD-06 | One held descriptor supplies both metadata and bytes; safe emptiness is pending, while unsafe metadata and nonzero malformed content are terminal. |
| Publication and cleanup regressions | V11-DOD-03, V11-DOD-04 | The existing 50 ms bounded process loop observes publication without resetting its deadline or inventing cleanup authority. |
| Unauthorized V11 package | V11-DOD-05, V11-DOD-06 | Fresh nonreplayable identities preserve the V10 science, budgets, order, finalizer, and evidence contracts while requiring model availability before paid mutation. |
| Validation, review, and PR | V11-DOD-07 through V11-DOD-09 | Every required local and parity gate is truthful; the result is one draft review surface only. |

## Baseline evidence

- `origin/phase-1/sira-pilot-autonomous-r2` resolved to the exact required base.
- The base tree and two parents match the source contract; the reviewed V10 head is
  the second parent.
- The starting worktree was clean; the V11 branch did not exist locally or remotely.
- Retained V10 closeout reports `terminal_or_absent: true`,
  `zero_t09_instances: true`, `security_restored: true`, one launch, one
  termination request, and no empirical campaign start. No provider request was
  made for this verification.
- V8 inventory: 168 files / 93,440,074 bytes / aggregate SHA-256
  `ac15202827352819570d89bc18253f78aafe58ee4206a4f1a3858b3847b96dab`.
- V9 inventory: 160 files / 14,487,048 bytes / aggregate SHA-256
  `65e7baf79841744d3eadd23131bea5287fd49839873a90dca5be60cd5e4212d6`.
- V10 stopped-run inventory: 38 files / 40,227,911 bytes / aggregate SHA-256
  `d1d1d65eb3b2c68d9e08d59adf21fcff433d89071a6bb3352301ae0f94815357`.

## Progress and decision log

- 2026-08-28: Starting verification passed and the exact task branch was created
  from the required merge commit without rebasing, resetting, or modifying the
  base branch.
- 2026-08-28: The observed zero-byte file followed by the exact 64-byte ID is
  classified as a publication-state race. The repair will change only the reader's
  safe-empty state; authority, timeout, and cleanup contracts remain fail-closed.

## Evidence log

- `PYTHONPATH=src uv run --no-sync pytest -q tests/test_t09_v11_cidfile.py`:
  **22 passed**. This is fake-only local evidence; it made no Docker or provider
  request.
- Focused source gate over the V11 cidfile and versioned-provider modules:
  **57 passed**, Ruff format/check passed, and strict mypy passed for all 64 source
  files. These checks used only deterministic local fixtures.
- Independent source review found the cidfile repair clean and identified one active
  fixture-promotion gap: three `test_t09_sira_pilot.py` fixtures still named V10.
  They were rebound to V11 while explicit historical V10 fixtures were retained; the
  reviewer's three exact regression selectors then passed (**3 passed**), and the
  independent rereview returned **CLEAN**.

## Blockers and user actions

None at start. Any repository identity mismatch, unavoidable live-runtime
dependency, or inability to preserve exact-ID cleanup authority is terminal under
`blocked_exact_cidfile_or_successor_plan_repair`.

## Next permitted phase

Implement and smoke the descriptor-safe reader and deterministic publication
regressions. V11 remains unauthorized; no provider, secret, live runtime, or
scientific action is permitted.
