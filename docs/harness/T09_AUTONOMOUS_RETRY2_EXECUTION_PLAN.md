# T09 Autonomous Retry 2 Execution Plan

Status: **terminal — stopped at first-pair checkpoint**

Source contract: current-turn user instruction, `T09 Autonomous Retry 2 — Repair
Provider-Call Accounting and Complete the Calibration Pilot`, SHA-256
`aea63a42cf0270ad0a41a929b4b8eb19dd1c3af73abfe97163c1d90e6077d3da`.

Starting commit: `f6d175f3464ceef11e3f6c02d6aba30fe4ceb9f6`.

Target branch: `phase-1/sira-pilot-autonomous-r2`.

Authorization identity: `AUTH-T09-AUTONOMOUS-RETRY2-2026-08-27`.

Objective identity: `OBJ-T09-V9-CALIBRATION-0001`.

## Workstream and scope

This workstream reconstructs the 33 V8 simulative provider attempts, repairs the
existing provider budget boundary so every send has durable atomic accounting,
qualifies the exact runtime without a live task call, freezes a fresh V9 package,
and executes at most four new zero-retry calibration attempts. The scientific
contract remains EXP-0001, SiRA `93fb8d72...`, `gpt-4o-2024-11-20`, the pinned
FanOutQA snapshot/tasks/evaluator, and the exact A-reactive, A-simulative,
checkpoint, B-simulative, B-reactive order.

In scope are the smallest evidence-grounded accounting repair, V8 adjudication,
focused fake-transport tests, exact-container qualification, one simultaneous A10,
local-volume evidence retention, cleanup, and terminal reconciliation. Out of scope
are planner/treatment/prompt/tool/browser/evaluator/scoring changes, condition
retries, a new task set, scientific comparison, training, and production claims.

## Definition of done

| ID | Contract | Required evidence | Status |
| --- | --- | --- | --- |
| AR2-01 | Preserve V8 bytes and reconstruct all 33 simulative attempts into closed typed categories. | Source-bound archive hashes and machine-readable per-call adjudication. | met |
| AR2-02 | Establish the exact cause of the three unmatched attempts without treating them as zero usage or unknown by default. | Retained events/log structure and source-level causal trace. | met |
| AR2-03 | Extend the existing provider budget boundary with stable call IDs and durable lifecycle states. | Code, typed ledger, and lifecycle transition tests. | met |
| AR2-04 | Atomically reserve calls, input/output tokens, and cost before send under concurrency. | Call/token/cost cap race regressions. | met post-terminal; repair retained separately from frozen V9 and exact empirical release regression passed three times |
| AR2-05 | Disable all automatic retries and reject a second send for one logical call. | Constructor/source assertions and duplicate-send regression. | met |
| AR2-06 | Terminally reconcile responses, provider errors, known transport failures, and unknown outcomes while retaining unknown reservations. | 33/30/3, response-write, shutdown, and bound-accounting tests. | partial empirically; one V9 response remained nonterminal, while the post-terminal primitive repair and exact regression are retained for a successor package |
| AR2-07 | Flush in-flight writers for a bounded interval and type remaining sends unknown. | Flush-success and timeout regressions. | met in focused and exact-container tests |
| AR2-08 | Preserve the complete privacy-safe call ledger in raw and essential-failure seals. | Seal/reconstruction regression and credential scan. | met |
| AR2-09 | Pass all 23 focused offline regressions, repository validation, typing, and diff hygiene. | Command outputs and committed repair. | met before empirical entry |
| AR2-10 | Pass exact-container accounting plus established runtime preflight with zero task model/browser activity. | Machine-readable qualification receipt. | met after five retained repair iterations |
| AR2-11 | Bind cloud work to one A10, no persistent filesystem, declared time/cost caps, fresh identities, verified local volume, and terminate-after-retention cleanup. | Cloud ledger, volume contract, provider receipts. | met |
| AR2-12 | Freeze a clean V9 commit, exact image, four commands, two valid pair diffs, and fresh run manifest. | Commit/image/manifest hashes and clean-tree receipt. | met |
| AR2-13 | Execute Task A reactive and simulative once each with complete terminal provider accounting and reconstructable raw evidence. | Attempt ledgers, manifests, evaluator records, usage, cleanup; zero retry. | partial; reactive valid-scored, simulative consumed infrastructure-invalid with reconstructable essential evidence |
| AR2-14 | Apply the predeclared first-pair checkpoint and continue only if every operational criterion passes. | Receipt-bound checkpoint decision. | met; stop before Task B |
| AR2-15 | If admitted, execute Task B simulative and reactive once each under the same frozen package. | Equivalent Task B evidence and pair matching; zero retry. | not applicable; continuation gate denied admission |
| AR2-16 | Retain and independently verify evidence, remove containers/browser/core/secrets, terminate the exact provider instance, and restore provider security. | Local-volume verification and terminal provider closeout. | met; global cleanup projection validation remains a disclosed limitation |
| AR2-17 | Run post-termination broader gates, independent spec-conformance review, update the terminal ledger, and publish the non-comparative handoff. | Test results, reviewer verdict, disposition/control records, final report. | in progress; post-terminal repair retained and review rerun pending; 39 broader historical-fixture tests and six frozen-format checks remain disclosed |

## Implementation mapping and planned evidence

- AR2-01–AR2-02 map to the immutable V8 simulative archive and a new public-safe
  accounting adjudication; the source archive is never rewritten.
- AR2-03–AR2-07 map to `src/giclab/harness/sira_gate_a.py`,
  `src/giclab/harness/sira_gate_a_runtime.py`, and focused accounting tests.
- AR2-08 maps to the provider lifecycle ledger plus the existing raw and essential
  sealing paths in `containers/sira-smoke/pragmatic/t09_remote_runner.py`.
- AR2-09–AR2-12 map to focused tests, exact-container receipts, clean commits, V9
  contracts/identities, and the frozen run manifest.
- AR2-13–AR2-16 map to immutable attempt archives, lifecycle/budget ledgers,
  uniform finalization, the checkpoint, verified local retention, and provider
  closeout.
- AR2-17 maps to this ledger, terminal control surfaces, post-cleanup gates,
  independent review, and the final response.

## Progress and decisions

- `2026-08-27`: verified the exact clean starting commit and created the requested
  branch. No cloud, model, or browser mutation occurred.
- `2026-08-27`: extracted the retained V8 simulative archive into a private temporary
  root. The immutable event stream contains 30 response receipts and three explicit
  `RateLimitError` provider-failure events; detailed adjudication is in progress.
- `2026-08-27`: adjudicated all 33 calls. All were confirmed sends: 30 successful
  response receipts and three known provider errors, with zero unknown outcomes or
  duplicate/internal retries. The three critic errors each recorded retry forbidden
  and one provider attempt. The exact defect is the budget boundary exception branch,
  which persisted open reservations and an unreconciled count but never terminally
  classified known provider errors. The 30 receipts establish observed lower bounds
  of 58,469 tokens and USD 0.2845925; the retained 308,977 tokens and USD 2.7540625
  are reservation-inclusive upper bounds.
- Decision: user instructions prohibit a new independent pre-live review checkpoint.
  Independent assembly conformance review therefore occurs after provider cleanup,
  while focused deterministic gates remain mandatory before live qualification.
- `2026-08-27`: passed exact-container accounting, core-suppression, Chromium,
  immutable V4 finalizer, cleanup, and privacy-safe sealing qualifications with zero
  task model calls and zero task browser actions. Frozen package commit is
  `630e6f9fcd22f6998d14e4fa48aee2224f6b2808`; the retained image is
  `sha256:abe8ed38...`; frozen-run-manifest SHA-256 is `9f75c6d1...`.
- `2026-08-27`: Task A reactive entered once and produced a valid evaluator score
  of `0.0` for an incomplete condition attempt: 20 calls, 40,152 tokens, five
  browser actions, and USD 0.1232325. Its independently verified raw archive is
  retained off-host.
- `2026-08-27`: Task A simulative entered once and was consumed
  infrastructure-invalid. Eleven calls terminally reconciled; the twelfth reached
  `response_received` with a durable actual-usage receipt but not
  `usage_reconciled`. The essential failure seal is independently verified. The
  first-pair checkpoint therefore stopped the campaign and Task B was not run.
- `2026-08-27`: post-termination reproduction established the precise primitive:
  subtractive binary floating-point reservation bookkeeping produced a tiny
  negative residue when the final of twelve concurrent reservations was released.
  A repair that derives reservation totals from the owned per-call map using
  `math.fsum` passed the exact twelve-call release order three times and all 26
  focused accounting tests. It is retained in distinct post-terminal commit
  `bb56edc68367e85b3a918f4b086c65cd578a231c`; the frozen V9 scientific package
  remains `630e6f9fcd22f6998d14e4fa48aee2224f6b2808`, and this campaign was neither
  altered nor rerun.
- `2026-08-27`: removed the temporary local secret and host-key material. Provider
  closeout proves one launch, 2,850.081638813019 active seconds, USD
  1.0212792539079985 Lambda cost, terminal-or-absent state, zero T09 instances, and
  restored security.
- `2026-08-27`: post-termination `make validate`, mypy, the 26 focused V9
  accounting tests, and the public site build/validation passed. The full test run
  completed with 1,473 passing and 39 failing historical/stale-fixture tests. The
  aggregate check stops earlier on six pre-existing formatting drifts in frozen
  source/test files; changing those bytes would contradict the retained V9 runtime
  identity, so both broader limitations remain explicit rather than being rewritten.

## Budgets, blockers, and next phase

Authorized ceilings are USD 10 pre-empirical Lambda, USD 8 empirical Lambda, USD
40 OpenAI, USD 58 new aggregate, and USD 90 cumulative reserved upper bound; 12
preflight active hours, 6 hours per preflight instance, one simultaneous instance,
one empirical launch, 4,620 model-call attempts, 4,000,000 tokens, 120 browser
actions, four condition attempts, zero retries, and zero persistent filesystems.

No further empirical transition is permitted under this campaign. A successor must
first repair and qualify the postrun reservation projection plus the disclosed
offline-control-snapshot and package-transition closeout gaps using network-free
tests, then obtain fresh identities and explicit current-turn authorization while
preserving the unchanged scientific contract and zero-retry policy.
