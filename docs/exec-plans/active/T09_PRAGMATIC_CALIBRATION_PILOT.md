# T09 pragmatic calibration pilot execution plan

Assembly status: **in-progress**

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
| T09-P3-01 | Preserve the exact scientific locks and calibration-only interpretation. | Dataset/evaluator/runtime contracts, scientific-hash regression. | met locally; final package binding pending |
| T09-P3-02 | Freeze `PLAN-EXP0001-PILOT-V3` and fresh host, four condition, evaluator, pair, and archive identities. | Plan, execution contract, condition plans, command manifests. | partial: identities frozen; final reviewed hashes pending |
| T09-P3-03 | Enforce a 14,400 s billable-instance campaign, 900 s cleanup reserve, one instance, one launch, zero filesystem, termination by 13,500 s, and no theoretical-maxima admission sum. | Typed campaign limits and fake-clock regressions. | met locally: existing observer and one-shot provider boundary share typed limits; cutoff/ambiguity tests pass |
| T09-P3-04 | Charge setup, full condition walls, evaluator/evidence handoff, provider dispatch, and cleanup to the same actual campaign clock; admit each attempt only when all four fit. | Host runner and focused timing tests. | met locally: conservative launch-send origin and exact boundary tests pass |
| T09-P3-05 | Keep model-call, token, OpenAI-cost, browser-step, condition/pair/total wall, output, disk, Lambda-duration/cost, attempt, and zero-retry caps effective. | Runtime cap tests and exact command/config diff. | met locally; final pair manifest regeneration pending |
| T09-P3-06 | Pass exact local preflight and freeze a clean reviewed pre-run commit before empirical entry. | Preflight receipt, Git commit/hash, plan bytes/hash, independent review. | not-started |
| T09-P3-07 | Record the current-turn cloud authorization in the private cloud ledger and launch no more than one exact A10 host in `us-east-1` with no persistent filesystem. | Cloud-run ledger and private provider receipts. | not-started |
| T09-P3-08 | Run Task A reactive then simulative exactly once and seal the automatic first-pair continuation decision. | Attempt/evaluator evidence and checkpoint receipt. | not-started |
| T09-P3-09 | Run Task B simulative then reactive exactly once only if the checkpoint passes and remaining wall admits the next attempt. | Attempt/evaluator evidence or typed stop receipt. | not-started |
| T09-P3-10 | Retain reconstructable, structurally redacted private evidence and valid evaluator outcomes for every consumed attempt. | Evidence indexes, outcome schemas, archive manifest/hash. | not-started |
| T09-P3-11 | Prioritize cleanup, terminate the exact owned instance, verify terminal/absent state, and restore/delete only owned security resources. | Host cleanup, provider closeout, zero-instance/security receipts. | not-started |
| T09-P3-12 | Reconcile actual calls, tokens, actions, wall, OpenAI/Lambda/total cost and update compute/project/experiment/readiness/decision/notebook records without a scientific conclusion. | Post-run commit and repository validation. | not-started |
| T09-P3-13 | Pass focused tests, independent spec review, post-review smoke, `make validate`, privacy scans, `git diff --check`, and the final repository gates appropriate after evidence capture. | Command log in this plan. | not-started |

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

## Decisions and blockers

- The current-turn user message is the sole execution authority. Tracked plans
  remain `authorized: false`; a single-use private overlay will bind the clean
  pre-run commit, exact plan/hash, identities, caps, and allowed actions.
- The empirical boundary is the first task model request or task browser action.
  Before that boundary common infrastructure defects may be repaired; after it,
  code and scientific configuration remain frozen and a consumed attempt is
  never retried.
- No user action is currently required. A genuine authenticated Lambda console
  or Jupyter checkpoint will be requested only after the local freeze and exact
  preflight are complete.

## Next permitted phase

Create the immutable implementation ancestor and obtain independent
spec-conformance rereview. Cloud mutation remains forbidden until rereview passes,
all final hashes bind, the package is clean, exact preflight passes, and the private
cloud authorization ledger is sealed.
