# T09 V10 provider accounting and closeout implementation ledger

Assembly status: **successful — implementation, review, all local gates, commit,
task-branch push, exact-base publication under explicit user authorization, and draft
PR closeout are complete**

Started: 2026-08-27

## Source and target contracts

The current user task is the authoritative Category 1 implementation contract. It is
constrained by `AGENTS.md`, `docs/PLANS.md`, the active Phase 1 plan, and the frozen
EXP-0001 scientific contracts. The target is a reviewable V10 successor package with
the existing reservation repair protected, one canonical offline-refinalization
receipt, and durable early cleanup authority. No live provider, model, browser, SiRA,
FanOutQA, evaluator, pilot, or cloud action is authorized.

Required base is `phase-1/sira-pilot-autonomous-r2` at
`503def0519e36f04b62b16158c72e11213b3bf9f`; starting tree is
`e033d28cee5478367cbdfc821e6b81c237ce8e44`. The accounting-repair ancestor is
`bb56edc68367e85b3a918f4b086c65cd578a231c`.

## Scope

In scope: provider-accounting regression protection; a deterministic, schema-bound
network-disabled refinalization receipt; versioned early cleanup state and fake-only
cleanup tests; an executable-but-unauthorized V10 plan; concise provenance and
preauthorization records; local validation; review; one commit, push, and draft PR.

Out of scope: V9 evidence mutation or reinterpretation; scientific changes; a new
infrastructure framework; credentials; provider/model requests; cloud mutation; live
Docker, browser, SiRA, FanOutQA, evaluator, or pilot execution; merge or auto-merge.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| V10-DOD-01 | Exact repository/base/ancestor/cleanliness checks and untouched full-suite baseline are recorded. | Git identities and baseline `make test`. | met |
| V10-DOD-02 | Outstanding provider reservations remain derived from owned per-call records with `math.fsum`, exact-empty semantics, atomic admission, one terminal per send, zero retries, and explicit lower/upper bounds. | Focused provider lifecycle, V8 33/30/3, V9 12-call three-pass, concurrency, flush, and shutdown tests. | met |
| V10-DOD-03 | `finalization-complete.json` is the one deterministic canonical offline-refinalization receipt and binds every required raw, science, source, runtime, evaluator, replay, mutation, semantic-output, and terminal identity under a JSON schema. | Schema tests, deterministic replay, identity-drift negatives, raw-manifest mismatch, privacy canary, and selector revalidation. | met |
| V10-DOD-04 | Exact provider ownership and later cleanup targets are retained in one durable versioned journal before package/source/image/secret/container/browser/campaign work; cleanup and a basic receipt do not require pilot state. | Failure-stage, missing-state, already-absent, repeated-cleanup, partial-persistence, exact-target, production fake-transport, and secret-canary tests. | met |
| V10-DOD-05 | Fresh `PLAN-EXP0001-PILOT-V10` and `AUTONOMOUS-0003` identities bind the repaired controls while all execution and compute permissions remain false. | V10 plan/schema validation, exact bytes/SHA-256, typed command render, science-hash regression, and command/config pair diff. | met |
| V10-DOD-06 | V8/V9 remain immutable historical evidence and every scientific field, timing bound, evidence cap, zero-retry rule, credential boundary, and interpretation limit is unchanged. | Historical hashes plus plan/contract regression tests and concise records. | met |
| V10-DOD-07 | Focused smoke, spec-conformance review, post-review smoke, formatting, Ruff, strict mypy, validation, privacy, full suite, diff check, and portable site gate satisfy the baseline policy. | Exact commands and results in this ledger. | met |
| V10-DOD-08 | Scope-reviewed changes are committed and pushed only to the task branch, and one draft PR is opened against the exact required base without auto-merge. | Final commit/tree, remote head/base, PR number/URL/state. | met — task branch pushed without force; draft PR #3 is open against the exact required base; auto-merge is disabled |

## Implementation mapping

| Work item | Mapped DoD | Target contract |
|---|---|---|
| Owned reservation projection and regressions | V10-DOD-02, V10-DOD-06 | The per-call reservation map is authoritative; aggregate projections are recomputed and an empty map is exactly zero. |
| Canonical completion receipt and schema | V10-DOD-03, V10-DOD-06 | Receipt creation follows immutable raw validation, is network/model/browser inert, contains no private payload, and deterministically identifies its full closure. |
| Early cleanup journal and closeout receipt | V10-DOD-04, V10-DOD-06 | Exact owned cleanup authority survives every pre-campaign failure and every update is a hash-chained immutable version. |
| Unauthorized V10 packet | V10-DOD-05, V10-DOD-06 | Fresh identities and unchanged science are executable by design but unavailable to any execution path until a later separately authorized Category 3 turn. |
| Review, gates, and PR | V10-DOD-07, V10-DOD-08 | No new regression, type, validation, privacy, or site failure; draft PR only. |

## Baseline evidence

- `git rev-parse phase-1/sira-pilot-autonomous-r2` ->
  `503def0519e36f04b62b16158c72e11213b3bf9f`.
- `git merge-base --is-ancestor bb56edc68367e85b3a918f4b086c65cd578a231c 503def0519e36f04b62b16158c72e11213b3bf9f` -> success.
- Starting worktree: clean; task branch created from the exact base.
- Untouched `make test`: **1474 passed, 39 failed in 48.39s**.
- Baseline failures are the exact historical-version/control-plane set in
  `test_exp0001_protocol.py` (6), `test_lambda_ssh_key_fingerprint.py` (1),
  `test_phase1_closeout.py` (2), `test_t08_sira_smoke.py` (1),
  `test_t09_retry3.py` (7), `test_t09_retry4.py` (4), `test_t09_retry5.py` (6), and
  `test_t09_sira_pilot.py` (12). The final run must add none.

## Progress and decisions

- 2026-08-27: Starting verification and baseline capture passed before edits.
- 2026-08-27: Confirmed the base retains the `bb56edc...` repair unchanged. It
  rebuilds reservation projections from the owned per-call map with `math.fsum` and
  has no subtractive reservation bookkeeping.
- 2026-08-27: Chose to evolve the existing finalization completion receipt rather
  than introduce a second competing downstream receipt.
- 2026-08-27: Chose one small hash-chained cleanup journal with injected exact-target
  actions; no general cloud orchestration layer will be added.
- 2026-08-27: The first independent conformance review failed because the initial V10
  packet still selected V9 execution assets and cleanup was only a tested primitive.
  The repair now has a separate typed, statically unauthorized V10 execution plane;
  the provider initializes cleanup inside its exact-owner protective block; the remote
  runner receives the hash-bound journal and registers exact secrets and containers;
  global cleanup can close from that journal without pilot state.
- 2026-08-27: Historical V9 remains on its frozen validation path. The V10 successor
  has its own schema, typed loader, deterministic command rerender, and pair-diff gate,
  preventing successor constants from retroactively reinterpreting V9.
- 2026-08-27: Rereview found that short-lived utility and finalizer Docker IDs were
  not entering the optional-state-independent journal. The common owned-Docker path
  now polls the daemon cidfile while the process is live, durably registers the exact
  ID, records verified normal removal, and preserves truthful removal evidence even
  when journal registration fails. Interruption and registration-failure regressions
  close through the journal with no pilot state.
- 2026-08-27: A same-path replay of the exact base identified one new V8 sealing
  fixture failure that aggregate counts had hidden. The primitive now takes explicit
  scientific-source and synthetic-lifecycle identity sets, preserving the historical
  V8 manifest while retaining strict V10 production ordering.

## Evidence log

- Final focused matrix: **61 passed** — 51 accounting, canonical receipt, early
  cleanup, and V10 plan cases plus 10 production/no-pilot/provider/V8 integration
  cases.
- The V9 release-order test executes the exact 12-call order three consecutive times
  and asserts an exactly empty positive-zero condition and aggregate projection.
- Production fake transports prove exact provider termination and security restoration
  when early-journal initialization fails, a single cross-host journal continuation,
  exact utility-container registration before process completion, and no-pilot cleanup.
- Independent spec-conformance review: passed after each material finding was repaired
  and rereviewed. Post-review focused smoke: passed.
- `make format`: passed. Ruff: passed. Strict mypy: passed. `make validate`: passed.
  Privacy/secret canaries and `git diff --check`: passed.
- Portable Quarto 1.9.38 `make site`: passed, including final site validation.
- Final `make test`: **1508 passed, 37 failed in 36.14s** versus the untouched start
  **1474 passed, 39 failed in 48.39s**. All 37 residual failures are members of the
  exact starting historical set; there are zero additions. Two historical fixtures
  were necessarily repaired in scope and now pass:
  `test_execution_schema_and_all_static_file_bindings_resolve` (typed unauthorized V10
  package closure) and
  `test_pragmatic_provider_entry_and_closeout_receipts_are_exact_and_source_bound`
  (durable cross-host cleanup continuation and closeout).
- Current V10 plan: 13,083 bytes; SHA-256
  `c6f36ffb0e719c2152c00fdd3f92cb18aa10a89e4a4a2e0f1179b167d6cfb68a`.
- The implementation commit `873196050eaf2138529929e1dc823cfdebcdc4e9`
  (tree `c30a7d9a6de9b3b299a87bf0ed3b2371b4e5ac0e`) was pushed without force to
  `origin/codex/t09-v10-accounting-closeout-repair`.
- Under explicit user authorization in a later turn, the missing remote base ref was
  published exactly at `503def0519e36f04b62b16158c72e11213b3bf9f` without force.
- Draft PR #3, `https://github.com/abbudjoe/gic-lab/pull/3`, was opened against that
  exact base. It is draft, open, mergeable, and has no auto-merge request. This
  ledger-only success update advances the final task head; the exact final commit and
  tree are reported after final push verification.

## Closeout and next permitted phase

No Category 1 blocker remains. Draft PR #3 now requires exact-head review by ChatGPT,
user approval of the reviewed SHA, and a separate Category 2 merge-only turn. No
Category 3 action is permitted; V10 remains unauthorized and unexecuted until fresh
Category 3 Luna authorization binds the exact merged commit and plan SHA-256.
