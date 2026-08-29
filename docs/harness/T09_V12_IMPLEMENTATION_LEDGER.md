# T09 V12 single model-metadata receipt implementation ledger

Status: **in-progress**. This is Category 1 implementation work only. V12 is
unauthorized, no live metadata request or Lambda launch is permitted, and the next
phase is exact-head ChatGPT review of one draft pull request.

## Source contract and provenance

The authoritative source contract is the current user instruction, **T09 V12 —
Fresh Sol/Max Reimplementation from the Exact V11 Base**. It narrows T09 to one
control-plane repair: one local model-metadata request produces one canonical
receipt; provider launch admits that receipt at the final transport boundary; the
host validates the admitted receipt durably and offline. Every V11 scientific,
budget, evidence, accounting, image, cleanup, and zero-retry field remains frozen.

```text
requested_model: gpt-5.6-sol
requested_effort: max
actual_task_model: gpt-5.6-sol
actual_task_effort: max
implementation_delegated_to_other_model: false
```

The active task's local runtime `turn_context` supplied the actual model and effort.
No subagent, delegated task, review thread, or other model is permitted. The usual
assembly independent-review stage is therefore replaced by a complete Sol/max
source/spec self-review before the external exact-head ChatGPT review.

## Scope

In scope: preserve and close superseded PR #5 without merge; implement the local
single-request preflight, canonical receipt, two-phase provider launch boundary,
durable offline host validation, fresh V12 proposal artifacts, validation wiring,
documentation, fake-only tests, local gates, draft PR, and exact-head GitHub Actions.

Out of scope: any real dotenv or credential access; authenticated OpenAI or Lambda
request; cloud mutation or paid compute; Docker, browser, SiRA, FanOutQA, evaluator,
or scientific execution; V12 run-root materialization; authorization consumption;
merge, auto-merge, Category 2, or Category 3.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
| --- | --- | --- | --- |
| V12-DOD-01 | Runtime provenance, exact repository/base/tree/parents, clean start, PR #5 identity, governing review, superseded branch, and fresh branch/worktree identities are verified; PR #5 is closed unmerged with the exact authorized comment and its branch is retained. | Runtime metadata, Git/GitHub identity checks, closure comment URL, post-closure checks. | met |
| V12-DOD-02 | V11 plan, authorization, host/attempt identities, private overlay, stopped evidence, and exact base history remain immutable; the retained 2,939-byte conflict evidence and 14,754-byte V11 plan keep their recorded SHA-256 identities. | Start/end byte/hash checks, base diff, historical tests. | met |
| V12-DOD-03 | A source-controlled local CLI strictly reads only `OPENAI_API_KEY` from one held safe dotenv file, consumes one-use authority after a send attempt, performs exactly one nonredirecting/nonretrying/nonpaginating model GET through an injectable transport, rejects replay/output reuse, and seals no secret material. | Fake-transport unit tests, filesystem and privacy regressions, source review. | met |
| V12-DOD-04 | One canonical receipt schema and deterministic semantic projection bind every required authorization/package/plan/run/model/endpoint/status/count/timestamp/public-contract field and enforce safe absolute mode-0600 no-follow single-link held-file I/O, bounded bytes, duplicate-field rejection, replacement detection, and no secret extensions. | Schema validation, mutation matrix, unsafe-file tests, deterministic hash tests. | met |
| V12-DOD-05 | Provider Phase A validates immutable bindings, safely retains the exact receipt/hash, consumes the single-use capability, fsyncs launch and send intent, and completes all local filesystem/subprocess preparation without a provider transport call; failure yields zero Lambda POSTs. | Fake preparation hooks and failure tests; durable state inspection. | met |
| V12-DOD-06 | Provider Phase B re-reads the retained receipt, recomputes its semantic SHA, samples time only after Phase A, admits age `<= 1800.0` seconds and rejects age `> 1800.0`, checks response/creation-before-launch ordering and every binding, then calls `transport.send()` immediately with no intervening filesystem write, subprocess, or blocking mutation. | Exact-boundary and mandatory crossing-window fake-clock regressions with `transport.calls == []` on rejection. | met |
| V12-DOD-07 | Provider launch makes zero OpenAI calls, performs at most one Lambda send, records truthful post-send chronology, and preserves conservative nonreplayable/outcome-unknown semantics after durable send intent. | Provider transport counters, journal/capability tests, source review. | met |
| V12-DOD-08 | Host uses `DURABLE_OFFLINE`, has no metadata transport or fallback, revalidates exact immutable and provider-entry bindings plus prelaunch ordering, ignores later wall-clock expiry, acknowledges the receipt SHA, and fails before run-manifest publication or empirical entry on drift. | Disabled-network tests at more than 1,800 and 3,600 seconds plus mismatch/file-security matrix. | met |
| V12-DOD-09 | Fresh `PLAN-EXP0001-PILOT-V12` and `AUTONOMOUS-0005` proposal identities bind one local GET, zero provider/host metadata requests, 1,800-second provider-final-boundary freshness, durable host semantics, replay false, and all authorization/execution/cloud/live flags false; no V12 run root exists. | Canonical plan/profile/contracts/schemas, validation, hash and absence tests. | met |
| V12-DOD-10 | The EXP-0001 scientific contract, model/service tier, SiRA/dataset/task/evaluator identities, order, retry count, interpretation, scientific projections, and both pair diffs are unchanged from V11. | Exact semantic projections, task hashes, pair-diff tests, base comparison. | met |
| V12-DOD-11 | Concise records cover PR #5 supersession, V11 stopped conflict, one-request ownership, final transport freshness, durable host validation, implementation ledger, preauthorization packet, plan/profile, and active Phase 1 state without a new governance track. | Tracked documents and repository validation. | met |
| V12-DOD-12 | Fake-only focused tests cover every required local/provider/host/invariant case, including the crossing-window regression; no active V12 test is skipped or xfailed and no real sleeps occur. | Focused pytest node/count record and test-source scan. | met |
| V12-DOD-13 | Formatting, Ruff, strict mypy, repository validation, privacy checks, `git diff --check`, raw full pytest classification, exact-base parity, portable Quarto/site validation, and exact-head `make ci-check` pass with zero newly failing or missing base nodes and no weakened transition. | Exact commands and result counts at final head. | partial — exact-head parity and CI gate pending |
| V12-DOD-14 | Sol/max self-review finds the implementation spec-conformant; normal commits are pushed only to the fresh branch; one draft PR targets the exact base, auto-merge remains disabled, exact-head Actions pass, and no merge or Category 3 work occurs. | Full diff review, commit/tree/PR/Actions identities, clean worktree. | partial — self-review and draft PR pending |

## Implementation mapping

| Work item | Mapped DoD | Target contract |
| --- | --- | --- |
| Local metadata preflight and receipt module | V12-DOD-03, V12-DOD-04, V12-DOD-07 | One source-owned authenticated GET can produce only one secret-safe canonical receipt. |
| Provider receipt retention and two-phase launch | V12-DOD-04 through V12-DOD-07 | All local mutation precedes a last-possible fresh-clock admission followed immediately by one transport send. |
| Host runtime handoff | V12-DOD-04, V12-DOD-08 | The exact provider-admitted receipt is sufficient forever for immutable offline host admission; no network fallback exists. |
| V12 plan/profile/contracts/schemas | V12-DOD-02, V12-DOD-09, V12-DOD-10 | Fresh operational identities change only metadata-receipt ownership and keep execution unauthorized. |
| Documentation, tests, and validation | V12-DOD-01, V12-DOD-11 through V12-DOD-14 | Every completion claim is tied to exact local/CI evidence and one review-only draft PR. |

## Starting evidence

- Repository: `abbudjoe/gic-lab`; original worktree:
  `/Users/joseph/Documents/gic-lab`.
- Base branch: `phase-1/sira-pilot-autonomous-r2`; commit
  `42a8ce6945c29f4221e03bb836f18421e50f3b1e`; tree
  `4271fccaf870cfd6a7963ac43daba5b616a0104a`; ordered parents
  `1c6b093699288f37aa23526fe1e1672e50280093` and
  `6d8757b8bdd5e0f2c688639d9b14360d6bc2eced`.
- Superseded PR #5 closed at the unchanged head
  `b169affba4d4cf7492c55f762fb3eb2ab4e52bf1`, tree
  `79ab2e671b219932e6c693a034f1e138596d297c`, without merge or
  auto-merge. Its remote branch remains intact.
- Fresh worktree:
  `/Users/joseph/.codex/worktrees/t09-v12-sol-model-metadata-receipt-handoff`;
  branch `codex/t09-v12-sol-model-metadata-receipt-handoff`; clean starting
  HEAD and tree equal the exact base.
- Untouched-base raw pytest completed with inherited failures. Exact base-vs-base
  parity collected 1,662 nodes on both sides: detached base 1,627 passed / 35
  failed; checked-out base 1,631 passed / 31 failed; zero skipped/xfail/xpass,
  zero newly failing, zero missing base-collected nodes, zero weakened transitions,
  and `parity_passed: true`.

## Progress and decisions

- 2026-08-29: Verified active GPT-5.6 Sol/max provenance before any Git or
  GitHub mutation. No delegation occurred.
- 2026-08-29: Verified every repository and PR identity, including substantive
  review `5058602134` at the exact candidate head.
- 2026-08-29: Closed PR #5 as superseded without merge using the exact authorized
  comment; retained the candidate branch and review history unchanged.
- 2026-08-29: Created the fresh branch/worktree from the exact V11 base without
  merge or cherry-pick and captured the untouched-base raw/parity baseline.
- Freshness boundary decision: `PRELAUNCH_FRESH` is inclusive at exactly
  1,800.0 seconds and rejects strictly greater age. The sampled time is owned by
  final Phase B admission, after every potentially blocking local preparation.
- Host decision: `DURABLE_OFFLINE` validates immutable bindings and provider-entry
  chronology, never current wall-clock expiry, and provides no network fallback.
- Exact formatted Sol implementation ancestor:
  `80c940b1f2da03bee2cb277ce2ddd63e3a9f8d27`. The static package binds
  that commit without importing any PR #5 commit.
- Final V12 plan: 16,293 bytes; SHA-256
  `0cfa8f7a43f706ca7cdfaf4f100356dde38437909b583cce354275c4ea995b8c`.
- Focused V12 receipt/provider/host matrix: 33 passed, zero skipped or xfailed.
  The full crossing-window `launch_campaign` regression crossed the freshness
  limit during Phase A, retained a nonreplayable capability and send intent, and
  made zero fake Lambda POSTs.
- Strict Ruff and package mypy passed; repository contract validation passed
  after regenerating every exact V12 source, runtime, condition, execution, and
  command-manifest binding.
- Raw full pytest against the actual worktree source classified 1,700 nodes as
  1,664 passed, 31 failed, and 5 skipped. The failures are inherited historical
  fixture, stale historical expectation, local-path, or Docker availability
  failures; exact-base node and transition classification remains the parity gate.
- The portable Quarto 1.9.38 render completed all 16 pages and site validation
  passed using the pinned runtime already retained in the original repository.

## Blockers and next permitted phase

No blocker is currently known. The only permitted successor after Category 1 is
external ChatGPT exact-head review of the new draft PR. Merge, authorization, and
Category 3 execution remain separate and prohibited in this task.
