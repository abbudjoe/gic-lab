# T09 pragmatic calibration pilot task plan

Assembly status: **blocked-user-action**

Terminal state: **`t09-pilot-blocked-material-risk`**

Source contract: the user's `T09 PRAGMATIC CALIBRATION PILOT — REPAIR THE
CAMPAIGN WALL AND EXECUTE`, SHA-256
`1f8285ea3fc52f4084a945f1712870203463cb7fb92cc61ac2eeae47d119e4c7`.

Starting branch/commit: `phase-1/sira-pilot-pragmatic` at
`6ff5ea6a8c3c43d0b860ad69081c0f546ee5f93d`.

## Scope

In scope is the smallest plan-driven repair that replaces the inherited 3,600
second campaign wall with one 14,400 second actual-time campaign, preserves a
900 second cleanup reserve, freezes a V3 plan and fresh identities, executes at
most one Lambda `gpu_1x_a10` host and the four zero-retry attempts in the frozen
order, runs the pinned evaluator, retains private evidence, and closes every
owned resource.

Out of scope are changes to tasks, evaluator, model, SiRA revision, condition
configuration, scoring, treatment contrast, order, interpretation, training,
a second launch, condition retry, production infrastructure, or scientific
superiority/EXP-0001 conclusions.

## Definition of done

| ID | Requirement | Evidence | Status |
|---|---|---|---|
| T09-P3-01 | Preserve the exact scientific locks and calibration-only interpretation. | Dataset/evaluator/runtime contracts, scientific-hash regression. | met: exact dataset, task, evaluator, SiRA, model, order, and interpretation bindings pass |
| T09-P3-02 | Freeze `PLAN-EXP0001-PILOT-V3` and fresh host, four condition, evaluator, pair, and archive identities. | Plan, execution contract, condition plans, command manifests. | met statically: plan is 5,270 bytes / `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210`; every fresh identity and child hash is bound |
| T09-P3-03 | Enforce a 14,400 s billable-instance campaign, 900 s cleanup reserve, one instance, one launch, zero filesystem, termination by 13,500 s, and no theoretical-maxima admission sum. | Typed campaign limits and fake-clock regressions. | met locally: existing observer and one-shot provider boundary share typed limits; cutoff/ambiguity tests pass |
| T09-P3-04 | Charge setup, full condition walls, evaluator/evidence handoff, provider dispatch, and cleanup to the same actual campaign clock; admit each attempt only when its wall and required handoff/cleanup reserves fit. | Host runner and focused timing tests. | met locally: conservative launch-send origin and exact boundary tests pass |
| T09-P3-05 | Keep model-call, token, OpenAI-cost, browser-step, condition/pair/total wall, output, disk, Lambda-duration/cost, attempt, and zero-retry caps effective. | Runtime cap tests and exact command/config diff. | met offline: cap/evidence tests pass and command package `8e8d5827df4688a8748828145ea0990d8397c771ae3add43790bbd45f732984d` reports both pairs valid |
| T09-P3-06 | Pass exact local preflight and freeze a clean reviewed pre-run commit before empirical entry. | Preflight receipt, Git commit/hash, plan bytes/hash, independent review. | blocked at the dynamic preflight: reviewed package `9dc7363561ec96812072e2c7824141d75b028332` was frozen, but rebuilding the pinned runtime produced `sha256:07875dc67336b90021df5ab920860a56268bbc9f3aada70accec23848d9905cf` instead of the required `sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c` |
| T09-P3-07 | Record the current-turn cloud authorization in the private cloud ledger and launch no more than one exact A10 host in `us-east-1` with no persistent filesystem. | Cloud-run ledger and private provider receipts. | met: the single-use ledger bound package `9dc7363`; exactly one `gpu_1x_a10` host launched in `us-east-1`, with zero persistent filesystems and no second launch |
| T09-P3-08 | Run Task A reactive then simulative exactly once and seal the automatic first-pair continuation decision. | Attempt/evaluator evidence and checkpoint receipt. | blocked before empirical entry: neither Task A attempt ran and the checkpoint was not reached |
| T09-P3-09 | Run Task B simulative then reactive exactly once only if the checkpoint passes and remaining wall admits the next attempt. | Attempt/evaluator evidence or typed stop receipt. | blocked before empirical entry: neither Task B attempt ran |
| T09-P3-10 | Retain reconstructable, structurally redacted private evidence and valid evaluator outcomes for every consumed attempt. | Evidence indexes, outcome schemas, archive manifest/hash. | met for the maximal preflight-only failure prefix: zero attempts were consumed, no evaluator outcome exists, and the private stage/provider archive is sealed and hash-bound |
| T09-P3-11 | Prioritize cleanup, terminate the exact owned instance, verify terminal/absent state, and restore/delete only owned security resources. | Host cleanup, provider closeout, zero-instance/security receipts. | met: owned containers and temporary secret material were removed; the exact host is terminal/absent; zero T09 instances and restored security state are provider-verified |
| T09-P3-12 | Reconcile actual calls, tokens, actions, wall, OpenAI/Lambda/total cost and update compute/project/experiment/readiness/decision/notebook records without a scientific conclusion. | Post-run commit and repository validation. | met: 0 model calls, 0 tokens, 0 browser actions, USD 0 OpenAI, and USD 0.414064252316667 Lambda are recorded without an EXP-0001 outcome |
| T09-P3-13 | Pass focused tests, independent spec review, post-review smoke, `make validate`, privacy scans, `git diff --check`, and the final repository gates appropriate after evidence capture. | Command log in this plan. | partial: post-run 57-test focused suite, validation, formatting/diff hygiene, and portable-Quarto full gate with 1,333 tests / 16 pages pass; independent closeout review and post-review smoke remain |

## Implementation mapping

- Campaign timing and attempt admission: `src/giclab/harness/lambda_campaign_lifecycle.py`,
  the parameterized `src/giclab/harness/lambda_l2m_observer.py`,
  `src/giclab/harness/t09_sira_pilot.py`, and
  `containers/sira-smoke/pragmatic/t09_remote_runner.py`.
- Frozen identities, limits, tasks, evaluator, commands, and evidence:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/` and
  `contracts/`.
- Provider mutation uses one exact, single-use T07-pragmatic Lambda request path in
  `src/giclab/harness/t09_pragmatic_provider.py`. It retains source-derived redacted
  receipts, never retries a launch, and adds no persistent service or watchdog.
- Scientific attempts/evaluator/evidence reuse the reviewed T09 runtime overlay.
- Governance and closeout use the existing registry, project state, Phase 1 plan,
  decision log, readiness record, compute manifest, and sanitized notebook.

## Evidence and progress log

- 2026-08-13: verified the exact requested branch and clean starting commit.
- 2026-08-13: confirmed the T09 runtime already contains condition execution,
  evaluator, evidence, cap, staging, and cleanup paths; provider entry and
  condition execution are intentionally fail-closed behind the adjudicated
  3,600-second lifecycle blocker.
- 2026-08-13: confirmed the retained V2 task/evaluator/pairing contract and the
  user's diagnosis that the campaign wall is the execution blocker to repair.
- 2026-08-13: independent source review correctly found that the first V3 draft had
  changed only the host clock and accepted caller-authored provider receipts. The
  draft was not frozen or launched.
- 2026-08-13: repaired the root controls: the existing observer now consumes a typed
  immutable lifecycle (T07 defaults unchanged; V3 is 14,400/13,500/900), provider
  entry/closeout receipts are reconstructed from retained structural projections,
  launch ambiguity durably forbids a second launch, exact-target cleanup can recover
  through bounded GET reconciliation, and finalized attempt evidence is streamed and
  hash-verified before the next attempt. Focused source tests, Ruff, strict mypy, and
  `git diff --check` pass; package hashes remain intentionally unbound pending review.
- 2026-08-13: immutable rereview of the first repair failed ten material controls.
  The follow-up repair now rejects malformed 2xx ambiguity, cleans every identity from
  a multi-ID launch incident, validates owned state against source-bound entry evidence
  before termination, polls projected owned identities through active/terminating to
  terminal, preserves the full 3,600-second condition wall, reserves 600 seconds for
  evaluator/export plus 60 seconds for termination dispatch, requires a received
  off-host export acknowledgement before later empirical entry, allowlists provider
  projections, makes aggregate staging optional, and delegates every read-only GET to
  the retained T07 observer transport. Cloud admission remains closed for rereview.
- 2026-08-13: subsequent immutable reviews drove the disk/archive headroom repair and
  the immediate provisional exact-ID ownership/cleanup path. Initial frozen source commit
  `e5edff3f1b256aaa17ad7bc79c255d82350964c7` received independent **PASS** with
  39/39 source-focused tests and no material residual; no external request occurred.
- 2026-08-13: rebound the V3 plan (5,270 bytes, SHA-256
  `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210`),
  runtime identity (`6011ba3930dc143473f7ae91d96364480b1c20f6e0931e4800d1e13b7cb8ec0d`),
  execution contract (`fd0c60f089d75f64cbdb83fb2d90d00446f1c566db7bccbbfd56c4fcccf6891c`),
  all four child plans, and the generated command package
  (`8e8d5827df4688a8748828145ea0990d8397c771ae3add43790bbd45f732984d`).
  Both normalized actual-argv pair diffs are valid. All 43 T09 tests, all 13
  Phase-1 control tests, repository validation, Ruff, and strict mypy pass.
- 2026-08-13: the full gate with the retained portable Quarto 1.9.38 binary passed:
  lock/sync, Ruff, strict mypy over 61 source files, all 1,332 tests, repository
  validation, all 16 notebook pages, and site validation. The only Quarto diagnostic
  was the known nonfatal output-path warning. Tracked-file privacy/secret and public
  path regressions are included in this passing suite.
- 2026-08-13: final package review rejected one stale V2 evaluator hash in the
  runtime identity. Rebound the current evaluator across runtime and execution
  contracts, cascaded every child/command hash, and added a cross-contract regression
  that requires runtime evaluator identity, execution binding, and current bytes to
  agree. The rejected `10f221c44e8568a71e0b34866115ed04980ffb4c` package was never launched.
  The replacement full portable-Quarto gate passed all 1,332 tests, 16 pages, and
  repository/site validation.
- 2026-08-13: the first authenticated provider prelaunch retained six source-bound
  read-only GET receipts and proved zero running instances, but correctly stopped
  before launch when the image-catalog validator treated the provider's one-row-per-
  region response as a duplicate frozen image. No POST, launch, paid instance, model
  request, browser action, or SiRA attempt occurred. The source-only repair filters
  the frozen image by `us-east-1` before cardinality enforcement; zero or duplicate
  regional matches still fail closed. Commit
  `6f7c3112777a8b253f085d058972259fad30778f` received independent **PASS** and is
  the reviewed replacement implementation ancestor.
- 2026-08-13: froze and independently reviewed clean package
  `9dc7363561ec96812072e2c7824141d75b028332`; its plan is 5,270 bytes with SHA-256
  `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210`.
  The private single-use authorization ledger validated and was consumed by exactly
  one launch of `gpu_1x_a10` in `us-east-1` with no persistent filesystem.
- 2026-08-13: installed the plan-pinned Python 3.11.14 and frozen project environment
  on the host before empirical entry. The exact runtime preflight then failed closed:
  the pinned sources rebuilt image
  `sha256:07875dc67336b90021df5ab920860a56268bbc9f3aada70accec23848d9905cf`,
  not the frozen T07 identity
  `sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`.
  The frozen image was absent locally, from the retained T07 bundle, and from the
  bound registry reference. Substitution was prohibited, so execution stopped before
  model metadata, a task browser action, evaluator loading, or empirical entry.
- 2026-08-13: no condition/evaluator attempt ran. The automatic first-pair checkpoint
  was not reached. Actual usage is 0 model calls, 0 input/cached/output/total tokens,
  0 browser actions, and USD 0 OpenAI cost.
- 2026-08-13: staged the maximal private preflight-failure prefix, verified its
  1,195,031-byte archive at SHA-256
  `941c61b58ac2fd8717c06ae2f8ef25616ed23c7e36ba64e88d9944924d084bc1`,
  terminated the exact host, observed terminal/absent and zero T09 instances, and
  verified security restoration. Conservative provider wall was 1,155.528146 seconds
  (0.320980040555556 A10-hours), estimated at USD 0.414064252316667. The final private
  archive manifest is
  `740aa70a7f6a7e659f776038ab35366a6d3448a656d2396a8eda0f3c887df5f2`.
- 2026-08-13: post-run reconciliation passed 57 focused T09/Phase-1 tests,
  repository validation, Ruff formatting/lint, strict mypy over 61 source files,
  all 1,333 repository tests, portable Quarto 1.9.38 render of all 16 pages, site
  validation, and `git diff --check`. Independent closeout review remains before the
  final clean handoff commit.

## Decisions and blockers

- The current-turn user message was the sole execution authority. Tracked plans
  remain `authorized: false`; the single-use private overlay was consumed by the one
  permitted launch and cannot be replayed.
- The empirical boundary is the first task model request or task browser action.
  Before that boundary common infrastructure defects may be repaired; after it,
  code and scientific configuration remain frozen and a consumed attempt is
  never retried.
- The exact frozen T07 container image was not retained as a loadable artifact and
  cannot be reconstructed to its frozen digest from the pinned sources alone. This is
  an execution blocker, not a scientific result or a publication-only blocker.

## Next permitted phase

Do not replay V3. A future run requires either the exact frozen image as a verified
loadable artifact or a fresh plan revision that requalifies and binds a replacement
runtime while preserving the scientific contract. Either path requires a new clean
package, independent review, and fresh current-turn execution authorization.
