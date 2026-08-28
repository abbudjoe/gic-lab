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
| V11-DOD-02 | `_read_owned_docker_cidfile()` opens the exact path with no-follow/nonblocking/CLOEXEC where supported, validates the opened descriptor's regular-file/owner/link/write metadata, treats only a safe zero-length file as pending, and accepts only the exact prior 64-lowercase-hex format with its optional single trailing newline. | Focused reader unit tests, real-FIFO and path-replacement regressions, source review, and post-review smoke. | met: 23 focused regressions pass, including a real FIFO, and final independent rereview is clean |
| V11-DOD-03 | Existing polling/deadline behavior remains bounded; durable authority begins only after a valid exact ID; changed IDs fail; timeout without publication never authorizes name-based removal; successful cleanup remains exact-ID-only. | Deterministic fake-process integration tests covering delayed publication, timeout, registration ordering, identity change, and cleanup. | met: deterministic fake-process integration, cleanup-authority, changed-ID, and deadline tests pass; final rereview is clean |
| V11-DOD-04 | The original transient-zero-length Category 3 sequence is reproduced against the old contract and passes under the repair without a live Docker daemon. | Focused regression fixture and exact failure-class assertion. | met: the old-reader fixture reproduces `unsafe`; the same sequence passes with the repaired reader |
| V11-DOD-05 | Fresh `PLAN-EXP0001-PILOT-V11` and `AUTONOMOUS-0004` host/attempt identities bind the repaired package; model metadata is ordered before Lambda launch; all scientific fields and all authorization/execution flags remain unchanged and false. | Canonical renderers, schema/hash tests, science projection, pair diffs, and exact plan bytes/SHA-256. | met: closure is rebound to `e91eccc`, both pair diffs and 11 exact plan tests pass, and final package rereview is clean |
| V11-DOD-06 | V8, V9, V10, and the stopped V10 Category 3 evidence remain immutable and V10 provider contracts remain version-addressable historical identities. | Start/end inventory equality, source diff, and historical contract regressions. | met: all historical regressions pass and fresh end inventories exactly equal all three baselines |
| V11-DOD-07 | Focused smoke, formatting, Ruff, strict mypy, repository validation, privacy checks, raw suite classification, exact-base/head parity, diff check, and portable Quarto/site validation satisfy the task contract. | Exact commands, counts, and parity report recorded below. | partial: every local gate is complete; first parity found two renamed historical node IDs, now restored, and the exact rerun remains |
| V11-DOD-08 | Independent review finds the implementation and successor package conformant, or every valid finding is repaired and rereviewed before closeout. | Reviewer findings, dispositions, and post-review reruns. | met: active-fixture, FIFO, and ledger findings were repaired; the independent final rereview returned CLEAN |
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
  **23 passed**. This is fake-only local evidence; it made no Docker or provider
  request.
- Focused source gate over the V11 cidfile and versioned-provider modules:
  **58 passed**, Ruff format/check passed, and strict mypy passed for all 64 source
  files. These checks used only deterministic local fixtures.
- Independent source review found the cidfile repair clean and identified one active
  fixture-promotion gap: three `test_t09_sira_pilot.py` fixtures still named V10.
  They were rebound to V11 while explicit historical V10 fixtures were retained; the
  reviewer's three exact regression selectors then passed (**3 passed**), and the
  independent rereview returned **CLEAN**.
- Final package review found that opening with blocking `O_RDONLY` could hang on a
  FIFO before descriptor metadata validation, and that ledger statuses overstated
  review closure. Commit `e91eccc01fa8d479cdfff270a8032dfb6283f5b4` adds
  `O_NONBLOCK` to the held-descriptor open and a deterministic real-FIFO regression;
  the focused 23-test suite, Ruff, and strict source typing pass. This ledger now
  records the remaining review and parity work as partial instead of met.
- Independent final rereview returned **CLEAN**: the reviewer confirmed that
  `O_NONBLOCK` precedes `os.open`, the real FIFO regression asserts the flag, the
  regenerated closure is internally bound, and this ledger records 231 collected /
  230 passed / 1 skipped with only parity and PR closeout pending.
- Source-bound V11 package rendering produced runtime profile SHA-256
  `726eeef3be208ad22b3279f8192fa55cfba259d14bf85424716b4f3e71a4a850`,
  runtime identity SHA-256
  `ca1bacf58c869067f61b8d43ba54a7589b7f7077e1ee49e9ff6d8b30e0be33ae`,
  execution contract SHA-256
  `97a1c22064284d0f812e6cac87dae836ad516a423c7ad9f4a0039c696c22b43d`,
  and command-manifest SHA-256
  `c36e1417b4668f6a0ae99abd63e4f3c6344c2af6c0942e2ac036633b3817a4e1`.
  The execution schema remains SHA-256
  `096e0a589a102b5cbf270eb3f8a14d9b9dd6cf7a48fb9397b1f126b1af8b6525`,
  and the reviewed-ancestor-bound plan schema is SHA-256
  `3291af39c50ce4f186008adc56d79fc1715adc539a1faea92c2fb3bff4988a7f`.
  Both machine pair diffs are valid and all authorization/execution flags are false.
- `PLAN-EXP0001-PILOT-V11.yaml` is 14,754 bytes with SHA-256
  `34a405d06521bd3fb55379721dff9c5795954fcb099d641587e2169b37575411`;
  its 11 exact plan/schema/hash/science/identity/metadata-order tests pass. The V10
  plan remains exactly 13,426 bytes at SHA-256
  `17c6502c625e0a3fcabc99180b0a432a60b27557be6a88f3289e45720951b38b`.
- The combined active/historical runner suites
  `tests/test_t09_v11_cidfile.py tests/test_t09_pragmatic_provider.py
  tests/test_t09_retry5.py tests/test_t09_sira_pilot.py
  tests/test_t09_v10_plan.py tests/test_t09_v11_plan.py` collect 231 nodes and pass
  230 with one intentional skip. Historical V8/V10 expectations are now verified
  from their exact frozen Git objects instead of being reinterpreted through the V11
  runner.
- `make validate` passes after registering V11 schemas, validating V10 Python source
  bindings at its immutable reviewed ancestor, and restricting the run-profile prior
  disposition to the two exact accepted historical shapes.
- Global Ruff format/check and strict mypy pass over 161 formatted files and 64 source
  files respectively; `git diff --check` and the V11 privacy/canary regression pass.
- The final unfiltered raw suite truthfully records **1,586 passed, 5 skipped,
  76 failed**. The failures are the same inherited historical control-plane
  assertions and local ledger prewrite-floor failures with only 5.3 GiB free. No
  exclusion was added or broadened; the required exact-base/head parity gate decides
  whether any failure is new.
- The repository-bundled portable Quarto 1.9.38 path rendered all 16 notebook inputs,
  generated four public views, and passed site validation. Quarto emitted its known
  nonfatal project/output-path warnings.
- End-of-implementation inventories equal their baselines exactly: V8 168 files /
  93,440,074 bytes /
  `ac15202827352819570d89bc18253f78aafe58ee4206a4f1a3858b3847b96dab`;
  V9 160 / 14,487,048 /
  `65e7baf79841744d3eadd23131bea5287fd49839873a90dca5be60cd5e4212d6`;
  V10 38 / 40,227,911 /
  `d1d1d65eb3b2c68d9e08d59adf21fcff433d89071a6bb3352301ae0f94815357`.
  No V11 run root or authorization overlay exists.
- Exact-base/head parity against `1c6b093699288f37aa23526fe1e1672e50280093`
  at package commit `7f5620dbf4b45dc7bb48bdcd9da1117c1aaec789` reported
  zero newly failing and zero invalid outcome transitions, but correctly failed for
  two missing base-collected nodes whose test functions had been renamed during V11
  promotion. Their exact historical node IDs are restored while retaining the V11
  assertions; both focused nodes pass, no exclusion changed, and exact parity will be
  rerun against the resulting commit.

## Blockers and user actions

None at start. Any repository identity mismatch, unavoidable live-runtime
dependency, or inability to preserve exact-ID cleanup authority is terminal under
`blocked_exact_cidfile_or_successor_plan_repair`.

## Next permitted phase

Commit the parity-node preservation, rerun exact-base/head parity, then push and open
one draft PR. V11 remains unauthorized; no provider, secret, live runtime, or
scientific action is permitted.
