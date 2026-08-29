# Phase 1 — Artifact Execution

Status: **in-progress**

Started: 2026-08-08

## Source contract

The authoritative package contract is the original Phase 0.75-to-Phase 1 build
package as amended by
`GIC_Lab_H2K_Option_Preservation_Addendum_v1_1`, especially its updated execution
roadmap and T07 through T15 prompts. Repository authority is further constrained by
`AGENTS.md`, `docs/PLANS.md`, `docs/COMPUTE_POLICY.md`,
`docs/SECURITY_AND_SECRETS.md`, the locked EXP-0001 protocol/run profiles, and the
successful Phase 0.75 plan.

T06 opens this plan but authorizes no execution. Each live API/model/browser or cloud
work item requires the exact current-turn human authorization declared by its task
contract. A proposed budget, eligible profile, historical conversation, or this plan
is not authorization.

## Target contract

Produce a source-grounded artifact-execution and directional-reproduction record for
the released SiRA and SR²AM artifacts through sequential, separately authorized smoke
and pilot gates. Preserve raw-to-normalized lineage, exact cost and compute accounting,
condition isolation, safe cleanup, and precise reproduction-level labels. RQ-H2K may
consume trace-completeness infrastructure evidence only; it remains planned/deferred
and cannot add an experiment, condition, training path, learned kernel, or later phase.

## Scope

In scope: T07 through T15; the authorized SiRA paired smoke and pilot; evidence-only
analysis between execution gates; read-only SR²AM Lambda preflight; separately
authorized SR²AM smoke and pilot; raw artifact retention and hashes; regulation-
decision provenance; compute/API accounting; public preliminary reporting; and the
current Phase 1 closeout.

Out of scope: any execution without the exact current-turn authorization; protocol
adaptation to observed effects; confirmatory claims; a new EXP-0001 condition; a
harness-to-kernel comparison; learned-kernel training or distillation; Phase 2; and
cloud mutation outside a fresh exact current-turn bounded T07 or T12/T14 authorization
contract. Frozen Gate L2M/L3/L4 work and historical Gate L1 read-only inventory grant
no mutation authority; one gate's authorization never carries into another.

## Phase definition of done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| P1-DOD-01 | Phase 0.75 is successful/completed; this is the one authoritative active plan; project execution/compute permissions remain false; only the disabled smoke profile is eligible for a later exact authorization. | Plan lifecycle/state/profile/readiness validation and public render. | met |
| P1-DOD-02 | T07 executes at most the one authorized SiRA smoke pair with complete raw, normalized, regulation-decision, budget, scoring, and cleanup evidence and no interpretation. | Immutable run/authorization records, artifacts/hashes, accounting, cleanup proof, and validation. | met; T08 documents nonblocking fields that T07 did not retain directly |
| P1-DOD-03 | T08 independently reproduces the smoke summary, separates infrastructure/protocol/upstream/future-track gaps, and leaves any pilot unauthorized. | Raw-to-summary checks, infrastructure-only trace-sufficiency report, review, and gate. | met |
| P1-DOD-04 | T09 first locks an executable calibration-only SiRA pilot and later executes it only under a fresh exact authorization, without outcome-adaptive changes, while reconciling every entered attempt. | Frozen task/order/evaluator/runtime records, enforced budgets, immutable authorization packet, and later complete attempt dispositions. | partial: V9 retained one valid incomplete reactive condition and one infrastructure-invalid unscored simulative condition; no realized pair or checkpoint exists. V10 stopped pre-empirically on a transient Docker cidfile publication race with verified cleanup. V11 stopped pre-launch on a model-metadata receipt contract conflict; V12 is the sole fresh unauthorized successor and awaits exact-head review and merge before any separate Category 3 authorization. |
| P1-DOD-05 | T10 produces a reproducible exploratory EXP-0001 analysis with uncertainty, exact reproduction level, cost/deviation reporting, and no internalization or mechanism-attribution overclaim. | Validated result summary, registry/notebook/ledger updates, review, and gate. | not-started |
| P1-DOD-06 | T11 produces a read-only, launch-ready SR²AM-v0.1-8B Lambda contract with current price, hard termination, source-grounded trace requirements, failure tests, and no mutation. | Audited runbook/contracts, dry-run/failure tests, authorization sentence, and gate. | not-started |
| P1-DOD-07 | T12 launches only the exactly authorized SR²AM smoke, retains and transfers required evidence, reconciles cost, and verifies provider termination. | Immutable cloud attempt, raw artifacts/hashes, compute ledger, monitoring, and terminal-state proof. | not-started |
| P1-DOD-08 | T13 validates SR²AM artifact fidelity, runbook safety/cost predictability, and infrastructure-only trace sufficiency before proposing an unauthorized pilot. | Recomputed evidence, source/adapter lineage, repaired tests, review, and gate. | not-started |
| P1-DOD-09 | T14 executes only a freshly authorized locked SR²AM pilot and verifies artifact transfer, accounting, and termination without in-run design changes. | Immutable pilot records, artifacts/hashes, compute reconciliation, and terminal-state proof. | not-started |
| P1-DOD-10 | T15 closes the current Phase 1 unit with validated SiRA/SR²AM evidence, precise reproduction levels, uncertainty/cost/deviation reporting, and one proposed next scientific workstream that is not begun. | Result summaries, registry/notebook/decision/risk updates, review, final gate, and plan disposition. | not-started |
| P1-DOD-11 | Every executed attempt has explicit current-turn authorization, immutable identity, append-only raw evidence, version/hash lineage, finite budget enforcement, secret isolation, and verified cleanup; failed infrastructure is never a scientific negative. | Run/compute/artifact ledgers, policy checks, failure evidence, and cross-task review. | partial: historical attempts remain immutable. V9 simulative is infrastructure-invalid and unscored with 12 confirmed sends, 12 known responses, 11 terminal transitions, one response-known nonterminal call, and zero unknown outcomes. V10 consumed one authorized host but no empirical condition; exact provider termination, zero running T09 instances, and restored security are verified. V11 repairs only the cidfile publication boundary and remains unauthorized. |
| P1-DOD-12 | Regulation/control evidence remains source classified; experiment assignment and ordinary prose are never called learned regulation; RQ-H2K outputs are infrastructure-only and do not affect EXP-0001 validity or interpretation. | Typed events, trace-sufficiency reports, negative boundary tests, and public wording. | not-started |
| P1-DOD-13 | Every implementation/analysis task passes focused smoke, independent spec-conformance review, post-review smoke, and its required full gate before the next dependency begins. | Per-task assembly ledgers with exact commands, artifacts, reviewer verdicts, and status. | partial |

## Work packages and implementation mapping

| Task | Work package | Mapped phase DoD | Current permission |
|---|---|---|---|
| T07 | Execute one authorized contained SiRA smoke pair; capture regulation-decision evidence without interpretation. | P1-DOD-02, P1-DOD-11 through P1-DOD-13 | complete: Retry 2 matched pair executed and cleanup verified; execution authority exhausted; no pilot authority |
| T08 | Analyze smoke infrastructure evidence and prepare an unauthorized pilot package. | P1-DOD-03, P1-DOD-11 through P1-DOD-13 | complete: evidence validated; pilot planning eligible but execution unauthorized |
| T09 | Lock and execute the two-task pragmatic calibration pilot under the fresh current-turn authorization. | P1-DOD-04, P1-DOD-11 through P1-DOD-13 | partial: V9, stopped V10, and stopped V11 evidence are immutable and ineligible for V12 pairing. V12 has fresh `AUTONOMOUS-0005` identities, is unauthorized and unexecuted, and awaits exact-head review, merge, and fresh Category 3 authorization. |
| T10 | Analyze and publish the exploratory SiRA pilot. | P1-DOD-05, P1-DOD-11 through P1-DOD-13 | blocked: T09 produced no complete pilot pair or checkpoint; the lone descriptive score supports no comparative analysis |
| T11 | Build and validate the read-only SR²AM Lambda preflight. | P1-DOD-06, P1-DOD-11 through P1-DOD-13 | blocked until T10 succeeds |
| T12 | Launch and monitor the separately authorized SR²AM Lambda smoke. | P1-DOD-07, P1-DOD-11 through P1-DOD-13 | blocked until T11 and authorization |
| T13 | Analyze the SR²AM smoke and prepare an unauthorized pilot. | P1-DOD-08, P1-DOD-11 through P1-DOD-13 | blocked until T12 succeeds |
| T14 | Launch and monitor the separately authorized SR²AM Lambda pilot. | P1-DOD-09, P1-DOD-11 through P1-DOD-13 | blocked until T13 and authorization |
| T15 | Analyze SR²AM pilot evidence and close the current Phase 1 unit. | P1-DOD-10 through P1-DOD-13 | blocked until T14 succeeds |

Work is sequential. A completed execution does not authorize its analysis successor,
and an analysis recommendation does not authorize the next execution.

## T07 assembly control

Assembly status: **Retry 2 complete: one reactive then one simulative smoke attempt
executed under the same frozen runtime; cleanup is verified, execution authority is
exhausted, and interpretation remains prohibited**

Historical bounded plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V3` (preserved, not current
execution authority).

T08 evidence-only independent reproduction and infrastructure adjudication is
complete. T09 froze the offline scientific/calibration contracts in
`PLAN-EXP0001-PILOT-V2` but found its provider lifecycle materially unsafe: the
inherited 3,600-second hard wall cannot cover four plausible attempts plus safe
staging/cleanup. No authorization packet or dynamic preflight is available.

Target contract: materialize and execute one matched reactive/simulative pair under an
exact human-approved provider/model, API-cost cap, wall-time cap, and cleanup contract;
preserve complete artifact and source-grounded regulation-decision evidence; and stop
without scientific interpretation or pilot progression.

The exact authorization fields, proposed USD 4.00 cap, pre-execution obligations,
expected artifacts, cleanup, questions, and infrastructure-only interpretation boundary
are in [`docs/readiness/PHASE_1_SMOKE_READINESS.md`](../../readiness/PHASE_1_SMOKE_READINESS.md).
The locked profile is
[`PLAN-EXP0001-SMOKE`](../../../experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml).

## T08 assembly control

Assembly status: **complete; independent review and safety rereview passed, focused and
full gates passed, and pilot execution remains unauthorized**.

T08 rehashed the 138-entry remote archive, 147-entry retained-local manifest, and
148-entry sealed-external manifest; verified exact source/destination equality;
reconstructed both condition records with field-level provenance; independently
recomputed the six-position command diff, four-field configuration diff, provider
accounting, and cleanup; and emitted terminal state
`smoke_evidence_validated_pilot_planning_eligible`.

The final full gate passed 1,284 tests, repository validation, a 16-page notebook
render, and site validation. Both independent review cycles returned clean PASS
verdicts after material provenance/control-plane and historical-fixture repairs.

The artifact pair is valid only as a one-step smoke. Both sessions report
`is_complete: false`; no EXP-0001 outcome, comparative mode claim, GIC/RQ-H2K claim,
or production-readiness claim follows. Historical pilot proposal
`PLAN-EXP0001-PILOT` contains two counterbalanced tasks and proposed caps, but remains
preserved and unauthorized. Exact DoD and review/gate evidence are in
`docs/harness/T08_SIRA_SMOKE_EVIDENCE_LEDGER.md`.

## T09 calibration-pilot lock

Assembly status: **V2 planning terminal `t09-pilot-blocked-material-risk`; no V2
pilot execution occurred**.

T09 preserves the original effect-oriented proposal and creates
`PLAN-EXP0001-PILOT-V2` because calibration-only scientific meaning, the exact
evaluator, and pair-equal enforced caps are material changes. It freezes the same two
FanOutQA rows and counterbalanced order; exact SiRA/model/runtime; four fresh attempt
identities; offline-validated evaluator behavior; per-attempt/pair/aggregate limits;
automatic Task-A continuation decision; reconstructable post-action/provider/scoring
evidence; structural redaction; cleanup/termination; and honest zero-GPU accounting.

The offline dataset, evaluator, pair, scoring, and evidence contracts are retained.
Execution remains materially blocked because the frozen T07 provider observer's
3,600-second wall cannot cover the four-attempt candidate and its bounded cleanup;
the proposed 14,400-second ceiling has no effective source-compatible enforcement
path. Public raw release remains separately blocked pending license/privacy review.
Project permissions, parent/child authorization, cloud mutation, provider calls,
browser use, and pilot execution remain false. See
`docs/harness/T09_SIRA_EXPLORATORY_PILOT_PLAN.md` and
`docs/harness/T09_SIRA_PILOT_PREAUTHORIZATION_PACKET.md`.

### T09 pragmatic campaign-wall execution — 2026-08-13

Assembly status: **`t09-pilot-blocked-material-risk`; stopped before empirical entry**.

The user's current-turn instruction superseded the V2 3,600-second provider-wall
restriction and authorized the narrow V3 repair plus one `gpu_1x_a10` launch and the
frozen four-attempt campaign. `PLAN-EXP0001-PILOT-V3` retains the exact V2 tasks,
evaluator, model, SiRA revision, counterbalance, scoring, evidence, budgets,
zero-retry rule, and calibration-only interpretation. The lifecycle now uses actual
elapsed time from the durable provider launch send-start, a 14,400-second hard campaign wall,
900-second cleanup reserve, and 13,500-second normal termination cutoff. An attempt
may start only when its full 3,600-second condition wall, 600-second evaluator/evidence
handoff, 60-second termination-dispatch margin, and cleanup reserve remain. The
provider boundary is a single-use adapter over the retained pragmatic mutation
shape and T07 observer GET transport; no persistent service or watchdog is introduced.

The reviewed package froze at
`9dc7363561ec96812072e2c7824141d75b028332`. Exactly one `gpu_1x_a10` host launched
in `us-east-1` with no persistent filesystem. Dynamic preflight installed exact Python
3.11.14, then failed closed because rebuilding the pinned runtime yielded container
`sha256:07875dc67336b90021df5ab920860a56268bbc9f3aada70accec23848d9905cf`
instead of frozen identity
`sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`.
The required frozen image was not retained as a loadable artifact, so no substitution
was permitted.

No model metadata request, task browser action, SiRA/FanOutQA condition, evaluator,
or empirical attempt ran; the first-pair checkpoint was not reached. Usage was zero
model calls, tokens, browser actions, and OpenAI cost. The exact host was terminated
after 1,155.528146 conservative provider seconds; terminal/absent, zero T09 instances,
and security restoration are verified. Estimated Lambda cost is USD
0.414064252316667. The public disposition is
`experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_PREFLIGHT_DISPOSITION.json`;
private raw evidence remains access-controlled. The consumed V3 authority is not
replayable. See `docs/harness/T09_PRAGMATIC_CALIBRATION_PILOT_EXECUTION_PLAN.md`.

### T09 pragmatic Retry 2 replacement-runtime execution — 2026-08-13

Assembly status: **`t09-pilot-blocked-material-risk`; single-use authority exhausted
after one valid scored attempt and before pair completion**.

Current-turn authority creates `PLAN-EXP0001-PILOT-V4` and fresh host, condition,
evaluator, and archive identities. It preserves every V3 scientific and calibration
lock, but supersedes cross-run equality with the unavailable T07 image. One
replacement is built from pinned reviewed inputs and accepted only after exact
package, patched-runner, browser, approved evaluator fixture, pair-diff, credential,
and one dated-model metadata GET gates pass. A source-derived mode-0600 O_EXCL
manifest freezes the actual image ID before empirical entry, and every later
condition/evaluator reloads that binding. V3 evidence and its USD
0.414064252316667 Lambda cost remain separate immutable provenance.

Clean pre-run package `9f02f733cd2cb57546aa262dac3e783e948504a4` passed
independent review. One replacement image,
`sha256:e2603f5aac97b8c48567b5de624e7d193dade0327a2f1040d2dd67d0cd86c2ba`,
passed qualification `QUAL-T09-PILOT-V4-IMAGE-0004`; exact manifest
`9071c152600a59e0001cd075e79abef08589d80d475b82fd0e5c15541026b09a`
froze it before empirical entry. Task A reactive ran once and exited zero. Its
retained raw prefix reconstructs as task completed, evaluator valid, score 0.0, with
52 model calls, 121,900 tokens, 13 browser actions, 199.196380 seconds, and USD
0.3626425 OpenAI cost.

The frozen host finalizer then exposed two control defects: it read `output_root`
from a nonexistent top-level command-manifest field, and its next invocation selected
the evaluator-only interpreter without the qualified control dependency closure. A
single network-disabled reconstruction using the same image, evaluator, dataset, and
retained prefix preserved the consumed attempt with zero additional model/browser
activity. Independent review accepted that evidence recovery for the consumed attempt
only; applying the corrected invocation to later attempts would change frozen
post-entry configuration. The campaign therefore stopped before Task A simulative.
No first-pair checkpoint or Task B attempt exists, and EXP-0001 remains unevaluated.

The direct attempt export and a privacy-safe maximal campaign prefix were copied and
rehash-verified. The aggregate stage failed closed on fixture-shaped and historical
source literals, so public raw release remains blocked. Temporary secret and owned
containers were removed; one termination request produced terminal/absent, zero T09
instances, and restored-security evidence. Lambda duration/cost were 1.359774964
A10-hours / USD 1.754109703373909; new campaign cost was USD 2.116752203373909 and
cumulative T09 cost was USD 2.5308164556905757. The public disposition is
`experiments/EXP-0001-sira-simulative-vs-reactive/T09_PRAGMATIC_RETRY2_DISPOSITION.json`.
V4 cannot be replayed; a future paired campaign requires both source repairs, fresh
identities, independent review, and new current-turn authority.

### T09 pragmatic Retry 3 raw-first execution — 2026-08-14

Assembly status: **`t09-pilot-blocked-material-risk`; stopped pre-empirically after
both authorized launches**.

`PLAN-EXP0001-PILOT-V5` repaired the two V4 finalizer primitives without changing the
tasks, evaluator, model, SiRA revision, counterbalance, budgets, zero-retry rule, or
calibration-only interpretation. Raw condition evidence is immutable and exported
before a pure network-disabled finalizer writes versioned derived output. The repaired
semantic projection ran twice over the exact V4 Task A reactive archive with identical
scientific/evaluator output, zero added model/browser activity, and retained receipt
SHA-256 `e19c7ccf…`. That regression is evidence about the finalizer, not a V5 attempt.

The first authorized V5 host built candidate image `sha256:abe8ed38…` once and
preserved its 1,207,128,576-byte loadable archive at SHA-256 `623e717c…`. Preflight
then stopped before the sole model-metadata GET and empirical entry because the
private V4 regression archive was supplied at the wrong host path. The exact zero-use
prefix was copied and verified; containers and temporary secret material were removed;
one termination request produced terminal/absent, zero-instance, and restored-security
evidence. Slot 1 used 3,883.231055 active Lambda seconds and USD 1.391491128.

A reviewed source-bound transition derived the one remaining launch capability only
after slot-1 closeout. The second launch passed the code-enforced pre-POST requirement
for at least one 3,600-second attempt plus the 900-second cleanup reserve. Provider
activation and source-bound entry observation then consumed the remaining positive
margin. At active entry the nonreset campaign could no longer admit the first attempt,
so the host was closed immediately—before host access, image import, dynamic
qualification, model metadata, browser use, or condition execution. Slot 2 used
332.407120 active Lambda seconds and USD 0.119112551; one termination request again
proved terminal/absent, zero T09 instances, and restored security.

Retry3 usage is zero metadata requests, task model calls, tokens, browser actions,
evaluator attempts, condition attempts, and OpenAI cost. Its two hosts used
4,215.638175 active seconds / 1.171010604 A10-hours / USD 1.5106036795496942; cumulative
T09 cost is USD 4.04142013524027, below every cap. The private two-launch archive
contains 224 files with 2,792,322 payload bytes and manifest SHA-256 `e8af18d0…`; the
large image archive remains separately retained. No V5 frozen run manifest, pair,
checkpoint, comparison, or EXP-0001 result exists. The two-launch capability and
campaign clock are exhausted. A future calibration requires fresh identities, a new
campaign clock, independent review, and new current-turn authority.

The exact smoke/V5 profile and V5 execution-contract files remain byte-frozen as
historical package evidence, so their embedded pre-run readiness strings are not a
current authority surface. The registry and project state instead bind
`T09_PRAGMATIC_RETRY3_TERMINAL_CONTROL.json`; runtime policy validates its terminal
disposition and frozen-file hashes and rejects both consumed plan IDs as
nonreplayable. That historical state is superseded by the fresh V7 registration below.

### T09 pragmatic Retry 4 archive/clock execution — 2026-08-14

Assembly status: **`t09-pilot-blocked-material-risk`; stopped after one consumed
infrastructure-invalid unscored attempt**.

`PLAN-EXP0001-PILOT-V6` repaired content-addressed private archive staging and split
cumulative active-provider, per-launch preflight, and post-freeze empirical clocks
without changing tasks, model, evaluator, SiRA revision, order, treatment, scoring,
budgets, zero retry, or calibration-only interpretation. Clean package `2b40b8a8…`
received independent prelaunch PASS. On its second and final host, the exact retained
image `sha256:abe8ed38…` imported without another build and passed package, evaluator,
real-evidence, browser, pair, credential, and one-metadata-GET gates. Frozen manifest
`c633c835…` was published before the fresh empirical clock.

Task A reactive entered once. It retained 20 task calls, 38,779 tokens, five requested
browser actions, four post-action results, and USD 0.1175275 OpenAI cost. A
234,479,616-byte core file pushed the raw attempt tree past the 67,108,864-byte cap.
The host stopped the container with exit 143, then the raw-complete seal failed
closed. Task completion, answer, evaluator validity, and score are unavailable. The
no-retry and raw-export-acknowledgement gates prohibited Task A simulative and both
Task B attempts, so no pair, checkpoint, comparison, or EXP-0001 outcome exists.

Both Retry 4 hosts are terminal or absent; zero T09 instances, restored security,
secret/container/image cleanup, 4,419.078072 active Lambda seconds / USD
1.5835029759 Lambda, and USD 5.7424506112 cumulative T09 cost are verified. The V6
terminal control supersedes the frozen smoke/V6 readiness strings and names no
successor. Public raw release remains blocked, and the aggregate evidence requires
one additive post-termination authority-member overlay plus a separate empirical-
clock reconciliation. That repair is now complete: the 597,140-byte sidecar member
rehashes at `18f6c7d6…`, overlay manifest `1eedf1d9…` reloads frozen runtime
`c633c835…`, and clock receipt `989d5625…` reconciles active/preflight/empirical time.
All original archive and provider-receipt bytes remain unchanged; neither repair
changes the scientific record.

### T09 pragmatic Retry 5 core-suppression execution — 2026-08-15

Assembly status: **`t09-pilot-blocked-material-risk`; stopped pre-empirically after
the second and final authorized launch**.

`PLAN-EXP0001-PILOT-V7` preserved every scientific field and excluded the consumed V6
attempt under fresh identities. The reviewed repair enforces Docker and process-tree
core limits of zero, adds bounded filename/ELF detection and destruction, and adds an
independently capped 16 MiB privacy-safe essential-failure authority. Static package
`6776cffeb49c498e0d932e6f47178d6a74514dfb`, all four generated commands, and both
pair diffs passed independent review; the broader local suite passed 1,467 tests.

Launch slot 1 stopped before image import or empirical activity on a historical versus
current finalizer binding defect. After its focused repair, slot 2 rehashed the exact
1,207,128,576-byte retained archive at `623e717c…`, then stopped at the first dynamic
gate: the provider entry bound the nested preempirical source manifest while the host
projected the outer normalized authority-tree manifest under the same field name. No
image, metadata request, model call, browser, evaluator, condition container, dynamic
run manifest, attempt, score, or pair was realized. Cleanup then exposed a separate
pre-state defect because `pilot-state.json` had not yet been initialized. Provider
termination took priority; both source-bound closeouts prove terminal/absent, zero T09
instances, restored security, and no wall exception. Retry 5 used USD 1.0706881238
Lambda and USD 0 OpenAI, bringing cumulative T09 cost to USD 6.8131387350.

The post-run terminal overlay consumes smoke, V6, and V7 as nonreplayable and names no
successor. Any later attempt requires an unambiguous typed nested-authority binding,
durable cleanup state before artifact-root mutation, fresh identities, clean review,
and new current-turn authorization. This no-run infrastructure disposition supports no
condition comparison or EXP-0001 outcome.

### Pragmatic execution reset — 2026-08-12

The current user contract supersedes the historical high-assurance infrastructure
gates on branch `phase-1/sira-smoke-pragmatic`. It authorizes autonomous repair and
execution of exactly one reactive/simulative smoke pair, in that order, with the
pinned SiRA commit, immutable model snapshot, task, one browser step per condition,
zero condition retries, USD 10 aggregate OpenAI ceiling, USD 5 aggregate Lambda
ceiling, at most two two-hour Lambda launches, zero persistent filesystems, retained
evidence, provider termination, and no scientific interpretation. Historical gate
evidence remains preserved and is not reused as execution authority.

| ID | Pragmatic T07 obligation | Status | Evidence |
|---|---|---|---|
| T07-P-01 | Verify the exact branch/baseline, no unresolved instance, usable pinned SiRA/model, safe credentials, viable termination, capacity, price, and storage. | met | Branch `phase-1/sira-smoke-pragmatic` at `29433a72d7452dae95fffdcba009bd33a4d46e15`; zero live instances; model metadata HTTP 200; A10 offered in two regions at USD 1.29/hour; exact SSH key match; external APFS volume revalidated. |
| T07-P-02 | Implement the smallest reusable secret filter and remote setup/paired-run/cleanup path, then pass focused validation. | met | `containers/sira-smoke/pragmatic/`; local Ruff, strict mypy, repository validation, and 109 focused SiRA/pragmatic tests pass. Remote setup attempt 06 verified the exact SiRA commit/tree, immutable routing, frozen dependency image, local-static-page Chromium lifecycle, exact model metadata, one A10, Docker 29.2.1, and zero residual setup containers. Earlier Python 3.10, wheel-filename, Docker mount/PID, and browser-interpreter failures are preserved as infrastructure evidence. |
| T07-P-03 | Before reactive begins, commit all infrastructure, render exact paired commands, write the concise run manifest, and freeze code/configuration. | met | Frozen pre-run commit `b2b347759b0cf94d054d0d45ce49766c7dd11c18`; run manifest 6,897 bytes, SHA-256 `c2095b4904d3803a66982e30601be6346cd3ab589ad5f5fd57be6c921c0d0da8`; exact reactive/simulative command-array hashes `9bda77c672c7210b745214fda20f42f7b5bf0e8184640638762ed2c0fa480ffd` / `81e064aabb93bf320a5a379ee8b043311ea2a801ad8c99e54c7098395fd34362`. |
| T07-P-04 | Execute reactive once, then simulative once, preserving each terminal outcome and accounting without interpretation. | blocked | Reactive started exactly once and failed before model/browser use because the frozen Python 3.10 image could not import `datetime.UTC` through `giclab.harness.artifacts`; this is a common-infrastructure failure. The reset contract therefore prohibited repair/retry and required simulative not to start. No scientific result was established. |
| T07-P-05 | Retrieve reconstructable evidence, destroy temporary credentials/runtime state, terminate the exact instance, restore firewall state, and verify no T07 instance remains. | met | Remote evidence archive 45,685 bytes, SHA-256 `03a200c31c0510c03b73828af300c51f18cc78f513957eb0e0d4f50b73213fec`, validated against all 115 manifest entries. Remote secret destroyed; owned containers absent; exact instance absent; account running-instance count zero; four-rule global-firewall baseline restored; no regional ruleset created. The APFS/UTDM bundle was atomically finalized with `FINAL_SHA256SUMS` SHA-256 `a8795a75a8b181126a7f869e05241beaf77597ca29c280c767e85dd64b0c5a77`. |

The terminal disposition is `common_infrastructure_failure`, not an EXP-0001
outcome. The pair was not obtained, no condition generation call or condition browser
action occurred, and T08/pilot progression remains blocked. A future attempt must
first repair and locally regress the Python 3.10 compatibility boundary, then use a
fresh frozen commit, run identities, and authorization.

The current reset explicitly waives a new authorization packet, schema suite,
independent review, and full repository gate before the smoke. Focused validation is
the required pre-execution gate; provider termination must not wait on later tests or
documentation.

Post-run closeout validation: `make validate`, `git diff --check`, and all 13
pragmatic-runner tests pass. After provider termination, the stale pre-execution test
that coupled the closed Phase 0 zero summary to exactly one all-time compute-ledger
entry was repaired to assert the Phase 0 record by identity while permitting typed
Phase 1 allocation records.

### Pragmatic Retry 2 — 2026-08-12

Assembly status: **complete** under the current-turn Retry 2 authorization.

Source contract:
`T07 Pragmatic Retry 2 — Repair Python 3.10 Compatibility and Obtain the SiRA
Smoke Pair`. The prior `RUN-T07-PRAGMATIC-HOST-0001` disposition and archive remain
immutable. Fresh identities are `RUN-T07-PRAGMATIC-HOST-0002`,
`RUN-T07-PRAGMATIC-SIRA-REACTIVE-0002`, and
`RUN-T07-PRAGMATIC-SIRA-SIMULATIVE-0002`.

| ID | Retry 2 obligation | Status | Evidence |
|---|---|---|---|
| T07-R2-01 | Verify the exact branch/start commit, prior disposition identity, clean tree, and fresh local/remote/external identities. | met | Clean `phase-1/sira-smoke-pragmatic-r2` at `866c8f376583486bf989de44b06fb15e0b6010a3`; prior disposition SHA-256 `8d4b081b4dd5995e2f021b5defb211d147461b134043d92cef17db3eb332d2fd`; all `0002` roots absent. |
| T07-R2-02 | Repair the actual Python runtime compatibility boundary without changing scientific fields. | met | `pyproject.toml` and `uv.lock` require Python `>=3.11`; the immutable upstream SiRA `pyproject.toml` at `93fb8d72…` (965 bytes, SHA-256 `63887052447a78cd5cd3fab980db7f4ef4f630f47dc2ad40fc89f80830d13f32`) permits `>=3.10,<3.13`. Reachable repository harness modules use Python-3.11-only `datetime.UTC` and `enum.StrEnum`. The final image therefore creates one exact Python 3.11.14 environment for both conditions and invokes every container child through that environment. No scientific field changed. |
| T07-R2-03 | Add exact interpreter import, timestamp, evidence, budget, command-rendering, browser, and cleanup regressions; pass focused local gates. | met | Ruff and strict mypy pass; 121 focused pragmatic/Gate-A/container tests pass; exact Python 3.10.20 `compileall` over all shipped runtime sources plus five-module host-side import/UTC smoke passes; exact Python 3.11.14 runtime preflight locally exercises all repository pre-empirical harness imports, a hash-bound controlled load of pinned `run_web_agent.py` and its dependency graph, UTC serialization, artifact writing, budget-ledger persistence, both exact condition-command renderings, and owned cleanup. A failed upstream load prevents setup completion. Repository validation and `git diff --check` pass. The remote container must repeat this evidence before empirical entry. |
| T07-R2-04 | Obtain clean independent spec-conformance review and pass post-review focused gates. | met | Independent rereview found no remaining P0/P1 issue after the hash-bound no-network runner-import repair and the narrowly classified, removed, and revalidated pinned-SiRA empty-log side effect. Post-review Ruff, strict mypy, 121 focused tests, exact Python 3.10 compile/import smoke, repository validation, and diff check passed. |
| T07-R2-05 | Launch within the authorized budget and pass the full exact-container pre-empirical runtime preflight. | met | One `gpu_1x_a10` launch in `us-east-1`, zero persistent filesystems. Setup attempts 01 and 02 stopped pre-empirically and retained their diagnostics. Attempt 03 passed exact Python 3.11.14, the frozen dependency/import sweep, patched runner SHA-256 `b06793ad1b366a934b798f9f3272fc80a7104a220cb3304ab3bda2eb2a78b331`, UTC/evidence/budget/command probes, one no-network local-page Chromium action, immutable-model HTTP 200, cleanup, and zero container residue. |
| T07-R2-06 | Commit/freeze the clean runtime, render and machine-diff exact commands/configurations, and hash the immutable run manifest. | met | Frozen clean commit `5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23`; exact image ID `sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`; run-manifest SHA-256 `877c26d16e242733e4f86afc54a058b868ca79ee27b826abc5e1e92ae0427ccd`. Machine diffs passed with only the six approved command identity/treatment fields and four approved configuration fields. |
| T07-R2-07 | Execute reactive then simulative with at most one consumed empirical attempt each and preserve accounting without interpretation. | met | Reactive executed once: exit 0, 4 model calls, 4,886 tokens, one browser action, 18.019 seconds, USD 0.014165. Simulative then executed once: exit 0, 5 model calls, 6,702 tokens, one browser action, 21.378 seconds, USD 0.0261675. Every response reconciled to `gpt-4o-2024-11-20` and `service_tier="default"`; no retry occurred. The one-step sessions did not claim task completion and support no scientific interpretation. |
| T07-R2-08 | Retain and hash evidence, destroy secrets/runtime residue, terminate provider compute, restore firewall state, and reconcile compute/accounting. | met | Remote archive 65,829 bytes, SHA-256 `4deebc0477581377e2bbb71a8f075bf8b3712188865f0e1faa5c0e7f62dc0450`, validated against 138 payload entries. Remote secret removed; zero owned containers/rulesets/instances; global firewall exactly unchanged. Lambda upper-bound duration/cost: 1,581.905 seconds / USD 0.566849. External bundle `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/RUN-T07-PRAGMATIC-HOST-0002` was atomically finalized with 148 payload files and `FINAL_SHA256SUMS` SHA-256 `9fb9ee63c1703e9701e8d5168284a1f757181baadd68a1508095eeac5fc7a167`; local source retained. Sanitized tracked summary `docs/harness/evidence/T07_PRAGMATIC_RETRY2_POSTRUN.json` has SHA-256 `ec1e2fb0a8e04997b4a87f9f2a898f597b70440b1df4f8a9dfba1da67ef5321c`. |

The Retry 2 empirical boundary is the first condition OpenAI request or condition
browser action. Common-infrastructure failures before both signals remain repairable
under fresh infrastructure-attempt identities. After either signal, that condition's
single attempt is consumed and code/configuration remain frozen.

Retry 2 terminal disposition: `matched_pair_executed_cleanup_verified`. The pair is
sufficiently matched as an artifact-execution smoke only. EXP-0001 remains
uninterpreted, the pilot and T08 were not started, and the next scientific decision
must be made from a separately reviewed evidence summary rather than inferred from
these two one-step trajectories.

### Bounded smoke definition of done

Source contracts: `T07_BOUNDED_SMOKE_FORK_AND_PLAN_FROM_397A391.md` and
`T07_BOUNDED_SMOKE_GOVERNANCE_PROFILE.md`. Fork:
`397a391b736528dd1049023d629100193e823c49`.

The exact active DoD mapping and validation record are maintained in
`docs/harness/T07_BOUNDED_SMOKE_V3_IMPLEMENTATION_LEDGER.md`. The child preserves the
scientific plan byte-for-byte while replacing the frozen high-assurance execution path
with one manually supervised Lambda/Jupyter session under the Occam admission rule.
V1 and V2 stopped before their first account request and are blocked historical
evidence. The fresh unauthorized execution plan is
`PLAN-T07-BOUNDED-SIRA-SMOKE-V3`, host run `RUN-T07-BOUNDED-HOST-0003`, at
`containers/sira-smoke/bounded/bounded-smoke-plan-v3.json`, 51,401 bytes, SHA-256
`30e83897c476dbd403a55d9d128636443f9df8a787ef903665ece083e3e41a53`.

The design binds one exact host, one launch click, zero persistent filesystem, an
immutable amd64 source/image/model path, an external single-run authorization overlay,
a durable 13-GET observer, verified firewall state before launch, a no-network browser
cleanup preflight, one reactive then one simulative attempt, hard
API/cloud/time/output/disk/call limits, strictly filtered automatic one-run secret
injection from `OPENAI_API_KEY` without a second user-managed file, tmpfs-only
condition writes with immutable-ID copy-out, success/failure evidence,
container/provider cleanup, and held-descriptor hash-verified archival. It does not
authorize an account request, mutation, paid compute, model call, browser, container,
SiRA, interpretation, pilot, or successor task.

### Gate B1.5 definition of done

Source contract: the user's 2026-08-09 Gate B1.5 storage-topology instruction.
Baseline: `b8752765594de0b3486edfd9fad84d144b78b7b7`.

| ID | Obligation | Status | Evidence |
|---|---|---|---|
| T07-B15-01 | Preserve branch/baseline and all prohibitions. | met | Starting checks; no execution or scientific change. |
| T07-B15-02 | Classify exposure as block mount, network filesystem, remote mechanism, or separate host. | met | MacBook Pro storage is exported by Thunderbolt Target Disk Mode as UTDM `/dev/disk6`, synthesized as APFS `/dev/disk7s5`, and mounted locally by the Mac mini; no SMB/NFS/FUSE mount. |
| T07-B15-03 | Record every requested identity, capacity, durability, permission, escape, and suitability field. | met | `docs/harness/T07_GATE_B1_5_STORAGE_TOPOLOGY_DECISION.md`. |
| T07-B15-04 | Default to sealed-retention-only unless stronger suitability is positively established. | met | Active/Docker suitability remains unapproved. |
| T07-B15-05 | Encode the network-backed copy/seal branch even though it is not the observed topology. | met | Storage policy and decision contract. |
| T07-B15-06 | If fully suitable locally, issue exact roots and regenerated plans/hashes; otherwise stop. | blocked | Docker VM-disk and reconnect suitability cannot be proven without a selected topology and later authorized runtime-specific evidence. No new plan/hash issued. |
| T07-B15-07 | Present alternatives a/b/c without selecting one. | met | Decision and both blocked packets. |
| T07-B15-08 | Update B1.5, B2a, and B2b documents and keep old Gate B2 hash superseded. | met | Three target documents under `docs/harness/`; no replacement plan/hash issued. |
| T07-B15-09 | Pass validation, independent spec review, repairs, and post-review smoke. | met | `make validate` and `git diff --check` passed; independent rereview was clean after topology/identity/governance repairs; post-review validation passed. |

Gate B1.5 maps T07-B15-02 through T07-B15-07 to the topology decision;
T07-B15-04 through T07-B15-06 to `docs/STORAGE_POLICY.md` and
`docs/DECISIONS.md`; T07-B15-06 through T07-B15-08 to the Gate B2a/B2b packets;
and T07-B15-01 through T07-B15-09 to this active plan.

### Gate B1.6 definition of done

Source contract: the user's 2026-08-09 Docker-storage qualification instruction,
SHA-256 `52d05ce39998f1a0ff81c7bbc23d936d1a61e1d709c0adafdfd07b7fb0279e60`.
Baseline: `e224e781e752869041c78a3e93687aaa5d8c6430`.

The detailed 22-item DoD, mappings, test evidence, blockers, and closeout are maintained
in `docs/harness/T07_GATE_B1_6_IMPLEMENTATION_LEDGER.md`. Gate B1.6 implements the
two-volume storage control plane, exact path roles, UUID/physical-store/APFS/UTDM
guards, reconnect state, minimized placement evidence, and one-way seal/copy
lifecycle. It does not live-qualify Docker or the topology.

Gate B1.6 is intentionally blocked on two facts that cannot be manufactured locally:
fresh official Docker metadata and a numeric source-grounded Mac mini operational
floor. Version-specific first-start internal allocation, settings/default paths,
update control, and reconnect semantics also require current official evidence. A
hashed blocked-design B2a plan may record the proposed sequence but cannot confer
installation authority while those terms remain unknown. B2b remains a
requirements-only stub.

### Gate B1.7 terminal runtime decision

Source contract: the user's 2026-08-09 final local-runtime selection instruction.
Baseline: `87d0a759dce2cfb6a6be964b2cf462ae43a1d9c9`.

The detailed DoD, mappings, source locks, repairs, validation, and terminal blockers
are maintained in `docs/harness/T07_GATE_B1_7_IMPLEMENTATION_LEDGER.md`. Gate B1.7
supersedes Gate B1.6's proposed Docker next-work path without deleting its evidence.
Docker Desktop remains blocked provenance. The evaluated Colima v0.10.3/Lima v2.2.0
candidate is `runtime-candidate-rejected`: required external `LIMA_HOME` would contain
Lima's private SSH identity on an ownership-disabled volume, the supported image does
not provide a current immutable pre-start Docker runtime, and required numeric caps
remain unresolved. No replacement plan ID, path, hash, argv array, or authorization
block exists. The sealed-artifact retention decision remains in force.

This was the final local-runtime selection gate. It does not create another B1.x turn,
authorize installation or a runtime probe, or alter the EXP-0001 treatment contrast.

### Gate L0 Lambda host pivot

Source contract basename: `T07_GATE_L0_LAMBDA_LINUX_HOST_PIVOT.md`,
SHA-256 `d630b569864a3a1125cd62fb92ad67b023faa2195bdc529829aafcb8dfa12efd`.
Baseline: `0ce094778f979e303794bbfe01acc93829a7ff1d` on parent
`phase-1/sira-smoke`; implementation branch `phase-1/sira-smoke-lambda`.

The detailed DoD, implementation mapping, source locks, tests, independent review,
and final gate evidence are maintained in
`docs/harness/T07_GATE_L0_IMPLEMENTATION_LEDGER.md`. Gate L0 selects a short-lived
x86_64 Lambda On-Demand Cloud host as T07's planned substrate, with no persistent
Lambda filesystem and provider-API termination as the authoritative billing boundary.
It created the now-historical eight-GET L1 inventory plan, an unauthorized
non-account-bound L2 host-qualification packet, an L3 requirements-only x86_64 B2b
successor, and an unauthorized L4 live-pair boundary.
L1 success includes a held-descriptor, hash-verified one-way copy to the approved
MacBook archive; L2 cannot consume a Mac-mini-only inventory. L2 also remains blocked
on an authenticated first-contact SSH server-host-key bootstrap.

The plan remains `lambda-host-selected-design-only`. Current capacity, exact
type/region/image/price, existing key/ruleset, and running-instance facts are
intentionally unknown until L1; an account/workspace LRN is not required. No account
API, cloud mutation, paid
compute, SSH, runtime/container/browser/model/SiRA action, secret access, or scientific
field change occurred. Docker Desktop and Colima/Lima remain terminal rejected
alternatives, not active blockers to L1.

### Gate L1.1 request-ledger repair

Source contract: the user's 2026-08-09 Gate L1.1 request-ledger observability repair
instruction. Baseline: `f9a80332da409789fefc435583aa0f1a10d3eb11` on
`phase-1/sira-smoke-lambda`; frozen implementation commit:
`0b900213801315f4312105297774b8ea5a6d9f04`.

The detailed DoD, implementation mapping, exact caps, test evidence, and independent
review record are maintained in
`docs/harness/T07_GATE_L1_1_IMPLEMENTATION_LEDGER.md`. The repair adds an
exclusive-create, append-only, flush-and-fsync request ledger; commits request intent
and send-started evidence before entering the future transport; records only closed,
secret-safe response/failure categories; fails closed on ledger unavailability; and
requires a complete validated ledger before an inventory can become eligible for
Gate L2. Fake transports and a public dummy canary are the only request/credential
surfaces exercised by the repair tests.

The immutable historical V1 plan remains byte-identical at SHA-256
`c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69`.
Both prior V1 authorizations are blocked historical attempts, and
`RUN-T07-L1-LAMBDA-INVENTORY-0001` may never be replayed. The fresh, still
unauthorized contract is plan `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2`, run
`RUN-T07-L1-LAMBDA-INVENTORY-0002`, at
`containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json`, SHA-256
`02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e`.
No account request, real-secret access, cloud mutation, paid compute, SSH, runtime,
browser, model, SiRA, or scientific execution occurred in Gate L1.1.

### Gate L1.2 audit-schema adjudication and minimal plan repair

Source contract: the user's 2026-08-10 Gate L1.2 instruction. Baseline:
`258ccc3c524e96e0fadc3afc23a43fa40f6a7d7a`; frozen implementation commit:
`718c75c694b3033fa7ef2ed5e7c4696fd8c389f3`.

The detailed DoD, historical evidence classification, source identity, tests, and
independent privacy/spec review are maintained in
`docs/harness/T07_GATE_L1_2_IMPLEMENTATION_LEDGER.md`. The authorized V2 run 0002
durably recorded one audit GET with HTTP 200, 18,058 response bytes, and a parser
`schema_drift` stop; no later request ran. Its raw body was not retained, so the exact
live mismatch is `unadjudicated_raw_body_absent` and cannot be reconstructed or blamed
on the provider, credential, endpoint, network, or transport. The original V2 ledger
remains byte-identical and run 0002 is permanently nonreplayable.

Under D-022, the fresh V3 plan removes audit history and account-LRN retrieval because
neither is required for Gate L2. It binds exactly seven GETs, endpoint-specific public-
contract schemas, compatible-addition structural reporting without unknown values,
hard pagination stops, strict redaction, exact implementation/execution ancestry, and
complete ledger/archive cross-validation. The unauthorized plan is
`PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3`, run
`RUN-T07-L1-LAMBDA-INVENTORY-0003`, at
`containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json`, SHA-256
`b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331`.
Gate L1.2 made no authenticated account/model request, accessed no real secret, and
performed no cloud mutation, paid compute, SSH, runtime, browser, SiRA, or scientific
execution.

### Gate L1.3 resource identity and Gate L2 security design

Source contract: the user's 2026-08-10 Gate L1.3 instruction. Baseline:
`42f74481e5a500cacb4973c6b29da4c3470679fe`.

Authorized V3 run `RUN-T07-L1-LAMBDA-INVENTORY-0003` completed all seven GETs with
HTTP 200/schema-valid outcomes, zero pagination, and zero running instances. Its
59,653-byte inventory, 32,287-byte/44-event request ledger, external seal, and copy
record remain byte-bound and source/archive-equal.

Offline adjudication classified the duplicate-image failure as `verifier_key_bug`:
259 regional availability rows represent 124 official `Image.id` identities. Fifteen
identities appear in ten regions with identical intrinsic metadata; there are no
same-ID/same-region duplicates and no conflicting metadata. A sealed ignored alias
map now supports a 124-alias public projection. The fixed Gate L0 policy yields six
unselected `gpu_1x_a10` tuples at the observed USD 1.29/hour price.

The current global firewall has one SSH and three non-SSH rules, so it is not strict.
Temporary global replacement is the preferred future design only after a dependency
attestation, exact approved public IPv4 `/32`, and fresh proof of zero running
instances account-wide. The original rules require a durable exact seal; the same
immutable qualification instance must be provider-terminal before verified
restoration, or the state is a high-severity incident. No regional/per-instance
ruleset exists, so a future gate must separately authorize its strict same-region
create/attach/delete lifecycle or explicitly supersede D-020's regional-ruleset
requirement. Host-key trust remains an independent console/Jupyter fingerprint
decision.

Gate L2 cannot progress to human choices because run 0003 retained account SSH-key
names but not account public-key material. Local/account fingerprint matching is
therefore `evidence_unavailable`. Resolving that fact requires independently verified
account fingerprints or a fresh reviewed and separately authorized minimal read-only
evidence plan. L1.3 created no executable plan and performed no account/model request,
real-secret access, cloud mutation, paid compute, SSH, runtime, browser, SiRA, or
scientific execution.

### Gate L1.4 SSH-key fingerprint design

Source contract: the user's 2026-08-10 Gate L1.4 instruction. Baseline:
`ae0ec40cb2da067a66f1a8d3d0e5aca857fd9491`.

Gate L1.4 pins the first-party OpenAPI 1.10.0 `GET /api/v1/ssh-keys` response and
creates fresh unauthorized plan `PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1`,
run `RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001`, at
`containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json`, 12,448
bytes, SHA-256
`23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`.
It is exactly one no-query/no-redirect/no-pagination/no-retry in-process GET after a
future current-turn authorization; broad inventory and prior run identities are not
reused.

The implementation parses OpenSSH, RFC4716, PKCS8/SPKI, and PEM RSA public-key forms
in process and computes standard SHA-256 fingerprints over canonical SSH wire blobs.
The plan-bound shell-free supervisor resolves the current UID's passwd home and opens
only held no-follow `.ssh/*.pub` files, treats same-stem private objects as
metadata-only, and separates ignored sealed raw/private evidence from a schema-bound
sanitized match report. Its two-phase driver stages evidence before sealing the
terminal request ledger, then requires a separate append-only finalization disposition
after atomic archive publication and post-copy verification. The request ledger alone
and every partial or failed disposition remain ineligible. A unique match remains
`unique-match-awaiting-user-approval`; no result selects or uses a key.

The fresh run root and 49,152-byte ledger are exclusive and nonreplayable. Evidence
uses finite byte/event/process/wall/file caps and the existing held-descriptor,
external-UUID, no-internal-fallback, one-way copy, source/destination hash, fsync, and
atomic-finalization contract. Gate L1A is unauthorized and unexecuted; Gate L2 remains
`inventory-evidence-insufficient`. No account/model request, real-secret access,
cloud mutation, paid compute, SSH, private-key read, runtime, browser, SiRA, or
scientific execution occurred.

### T09 V10 stopped Category 3 disposition and V11 repair — 2026-08-28

The exact reviewed V10 merge `1c6b093699288f37aa23526fe1e1672e50280093`
launched one plan-bound A10 Lambda instance and completed substantial qualification,
then stopped before its single model-metadata GET and before any task model request,
task browser action, evaluator entry, or scientific condition. Docker had created the
exact owned cidfile as a safe regular zero-byte file; the runner treated that transient
publication state as permanently unsafe. Later inspection of the same path found the
expected complete 64-lowercase-hex daemon-published ID. This is
`transient-zero-length-docker-cidfile-publication-race`, an implementation defect, not
a consumed scientific condition or an EXP-0001 outcome.

The V10 host identity and private single-use authorization are consumed. Retained
closeout evidence records one launch and one termination request, exact instance
terminal-or-absent state, zero running T09 instances, container and temporary-secret
cleanup, and restored firewall/security state. V10 used USD 1.7273232755184174 Lambda
and USD 0 OpenAI. Its operational evidence, plan bytes, and output roots are immutable
and cannot supply authority or pairing evidence to a successor.

Category 1 V11 changes only the owned-cidfile publication boundary: one no-follow
descriptor supplies metadata and content, a safely validated zero-byte file is
pending, nonzero malformed content remains terminal, and cleanup authority still
begins only with the exact daemon-published ID. The existing bounded process deadline,
durable early-cleanup journal, changed-ID rejection, and no-name-based-cleanup rules
remain intact. `PLAN-EXP0001-PILOT-V11` uses fresh `AUTONOMOUS-0004` host/condition
identities and preserves every V10 scientific, evaluator, order, retry, timing,
evidence, and nominal cost field. Its effective new-work ceiling is additionally
bounded by the unchanged USD 90 cumulative T09 cap.

The tracked V11 proposal is 14,754 bytes with SHA-256
`34a405d06521bd3fb55379721dff9c5795954fcb099d641587e2169b37575411`.
It remains statically unauthorized and unexecuted. A later Category 3 transaction
must make exactly one authenticated metadata GET for `gpt-4o-2024-11-20` before
Lambda launch or paid mutation and must stop with zero new Lambda cost if the snapshot
is unavailable. Category 1 performed no credential access, provider request, cloud
mutation, live Docker/browser/SiRA/FanOutQA/evaluator action, or paid compute.

### T09 V12 model-metadata receipt handoff repair — 2026-08-29

Assembly status: **Category 1R timing repair implementation complete; final source/spec rereview,
exact-head gates, and merge required; V12 remains unauthorized and unexecuted**.

V11's stopped transaction is preserved as immutable operational evidence. Its
root cause was duplicated ownership of the frozen single authenticated metadata
GET: the external local pre-Lambda control plane sent the request, while the
host runtime would send a second request during qualification. V12 repairs the
ownership boundary without changing the scientific contract. The local gate
seals the sole canonical receipt; provider launch validates its freshness at
the actual launch-send boundary and retains its semantic SHA-256 before any
Lambda POST; and the host validates the exact source-bound receipt copy offline
with zero metadata network calls and no current-time expiry.

The fresh V12 package is `PLAN-EXP0001-PILOT-V12`, with host and attempt
identities recorded in `docs/harness/T09_V12_ACTIVE_PHASE1_STATE.md`. Provider
freshness is 1,800 seconds and host current-time freshness is false; prelaunch
timestamp ordering remains mandatory. All V12
authorization, execution, cloud-mutation, paid-compute, live-qualification,
pilot, and run-root flags remain false. The tracked proposal keeps the future
merged-commit placeholder; a fresh Category 3 overlay must bind the exact
reviewed merge and plan hash. Category 1 made no provider, OpenAI, Lambda,
browser, SiRA, evaluator, Docker, or scientific request or mutation. See
`docs/harness/T09_V12_IMPLEMENTATION_LEDGER.md` and
`docs/harness/T09_V12_PREAUTHORIZATION_PACKET.md`.

## Authorization and mutation boundary

Current project state keeps reusable paid-compute, prototype, benchmark, training, and
cloud permissions false. T07 and every T09 authority through V11 are exhausted. V12
is the sole current registered T09 successor, is executable by design, and has no
execution, cloud-mutation, or paid-compute authority. It requires exact-head review,
a separate merge-only turn, and then a fresh Category 3 authorization against the
reviewed merged commit and exact V12 plan digest. T12 and T14 separately require their exact cloud
mutation, hardware, data, cost/time, artifact-transfer, and termination authority.
Read-only inspection or preflight never supplies mutation authority.

The Gate L1/L1A account inspections and Gate L2M firewall capture are consumed,
nonreplayable historical evidence. The high-assurance Gate L2M/L3/L4 path is frozen
and cannot receive fresh authority on this branch. A bounded-smoke child must define
new plan/run identities, exact resource and spend caps, cleanup/evidence contracts,
review, and current-turn authority; no earlier gate grants any part of that authority.

## Planned evidence

- One Assembly ledger per T07–T15 task with DoD mappings and exact evidence.
- Schema-valid immutable plans, commands, events, artifacts, summaries, and compute
  records linked to pinned source/model/dataset/environment revisions.
- Focused deterministic tests plus independent spec-conformance review and post-review
  `make check` for each work item.
- Real CUDA/cloud evidence only for the separately authorized SR²AM execution tasks;
  local/API SiRA evidence is never presented as CUDA evidence.
- Public notebook updates that separate infrastructure, exploratory evidence,
  reproduction level, and unsupported claims.

## Progress log

- 2026-08-08: T06 created the Phase 1 control plane after integrating and reviewing
  Phase 0.75. At that time `PLAN-EXP0001-SMOKE` was the only profile eligible for a
  later human authorization; the pilot and all SR²AM execution remained blocked.
- 2026-08-08: All project execution and compute permissions opened as false. No model,
  API, browser, benchmark, training, cloud, or paid-compute action occurred during the
  transition.
- 2026-08-08: Parent-profile eligibility became a typed authorization gate: condition
  plans bind the exact profile plan ID and SHA-256; project state fully validates and
  binds the same profile and its canonical declared-child fingerprints before
  execution; and blocked or undeclared plans cannot materialize authorization.
- 2026-08-08: T07 Gate A implemented immutable all-role routing, durable finite
  provider accounting, owned attempt/log/environment evidence, exact output capping,
  external installation contracts, smoke-only authorization materialization, and a
  machine condition diff. Independent review proved polling cannot guarantee cleanup
  for a fast reparented child, so the command now fails preflight until kernel-enforced
  containment exists. No SiRA dependency/browser installation or live action occurred.
- 2026-08-09: T07 Gate B1 implemented and independently reviewed a private-PID,
  cgroup-backed OCI containment control plane without installing or launching a
  runtime. A later storage rule superseded its internal-disk Gate B2 plan.
- 2026-08-09: Gate B1.5 observed the MacBook Pro exporting storage through
  Thunderbolt Target Disk Mode to a locally mounted APFS block device on the Mac mini,
  then positively tested sparse files, same-volume rename, file/full/directory sync,
  and mode bits. Owners are disabled, symlink escape is possible, Target Disk Mode
  reconnect/unlock behavior is untested, and Docker disk-image suitability is unknown.
  It is therefore approved for sealed retention only.
- 2026-08-09: Independent Gate B1.5 review corrected the initial direct-disk
  classification to UTDM, separated volume/container/partition/transport identities,
  reconciled D-017 across historical packets, scoped volume checks to sealed-copy
  actions, and made positive active/runtime suitability mandatory before B2a plan
  issuance. Post-repair rereview was clean and post-review validation passed.
- 2026-08-09: The user selected the Mac mini plus MacBook Target Disk Mode topology
  for Gate B1.6 qualification. The local control plane now separates external Docker,
  staging, and sealed-artifact roles from the bounded Mac mini attempt root; rejects
  fallback and stale storage guards; and implements deterministic reconnect and
  one-way sealed-copy contracts. No Docker or network action occurred. Installation
  remains blocked because current metadata and an evidence-based internal floor are
  unresolved.
- 2026-08-09: Gate B1.7 audited pinned Colima/Lima/Docker release and source metadata,
  rejected the replacement topology under the binary decision rule, and created no
  executable B2a plan. Independent review hardened exact-path lease transfer,
  positive writer-closure evidence, issuer-bound rollback ownership, and authoritative
  control-plane alignment. No runtime payload, VM, container, browser, API, secret, or
  SiRA condition was installed, launched, accessed, or executed.
- 2026-08-09: Gate L0 selected the D-019 Linux-host alternative as a design-only
  x86_64 Lambda On-Demand Cloud topology. It source-bound Lambda OpenAPI 1.10.0 and a
  minimal immutable amd64 BusyBox qualification image, implemented strict redacted
  inventory/selection/no-filesystem/termination contracts, and separated L1 through
  L4 authority. No Lambda account API, secret, cloud mutation, payload, SSH, runtime,
  browser, model, or SiRA action occurred.
- 2026-08-09: Gate L1.1 repaired the V1 request-evidence defect with a bounded,
  durable request ledger and a fresh immutable V2/0002 plan. Both V1 attempts and
  run 0001 remain blocked historical evidence. Local fake-transport tests covered
  success, reviewed transport and validation failures, ledger I/O failure,
  outcome-unknown recovery, archive eligibility, run reuse, and secret-canary
  exclusion. The new plan remains unauthorized; no account request or real-secret
  access occurred.
- 2026-08-10: Gate L1.2 preserved and adjudicated stopped V2 run 0002 without a
  retained raw body, removed unnecessary audit-history/account-LRN retrieval, and
  created a fresh unauthorized seven-GET V3/0003 plan. Endpoint-specific schemas,
  compatible-extension reporting, strict sensitive-field redaction, commit ancestry,
  and Gate-L2 evidence cross-binding passed local fake-transport and independent
  privacy/spec review. No account request or real-secret access occurred in L1.2.
- 2026-08-10: Authorized Gate L1 V4 completed the seven-GET V3 inventory and sealed
  its ledger/inventory to the approved external archive. Gate L1.3 then repaired the
  regional image-identity verifier offline, derived six unselected candidates, and
  designed strict firewall/host-key decisions. Because account public-key material
  was intentionally not retained, SSH fingerprint matching remains evidence-
  insufficient and no Gate L2 plan or authorization exists.
- 2026-08-10: Gate L1.4 created a fresh unauthorized one-GET Gate L1A plan for the
  missing account SSH public-key evidence. New in-process format/fingerprint parsing,
  no-follow local `.pub` matching, a fresh durable ledger, and private/public evidence
  schemas passed local fake-only design tests. The request and fresh run remain
  unexecuted; no key is selected and Gate L2 stays blocked.
- 2026-08-10: Gate L1A completed with a unique sealed local/account match for
  `fractal-lambda-codex`. Gate L2.0 then validated the user's private candidate,
  firewall, `/32`, agent, no-filesystem, and Jupyter-host-key choices; resolved raw
  provider values only into nonce-protected ignored parameters; copied the sealed
  bundle one-way to the approved external archive; and entered
  `blocked-human-or-source-decision`. Independent review found no source-backed safe
  identification/termination of an accepted launch after an unknown response and no
  authoritative end-to-end supervisor/evidence path. No executable plan or
  authorization block exists. No account/model request, secret, cloud mutation,
  paid compute, SSH, container, browser, SiRA, or scientific execution occurred.
- 2026-08-10: Gate L2.1 pinned Lambda OpenAPI 1.10.0, designed a private random
  ownership conjunction, and fake-tested transaction, watchdog, cap, privacy, and
  descriptor-held archive primitives. Independent review found no authoritative live
  composition: effecting mutations and cleanup are not phase-exact, supervisor and
  watchdog do not share enforced cross-process budgets/lease, the watchdog has no
  concrete independently supervised cleanup entrypoint, and success/terminal evidence
  remains assertion-capable. The automated path therefore ended at
  `manual-console-launch-required`; no V2 plan or authorization block was created.
  No account/model request, secret access, cloud mutation, paid compute, SSH,
  container, browser, SiRA, or scientific execution occurred.
- 2026-08-10: Gate L2.2 pinned the manual console, Lambda Stack/GPU Base, Cloud IDE,
  firewall, termination, billing, read-only API, and BusyBox metadata contracts. The
  sealed inventory contains four x86-64 Lambda Stack 22.04 regional candidates;
  `img-0032` / `22.4.5-2141` ranks first. Static sources do not prove type-specific
  launch-wizard offeredness, so a future transaction must fail closed before Launch
  if the approved alias is not offered. The existing private selection remains GPU Base, which
  has no documented JupyterLab guarantee, so the terminal state is
  `blocked-human-image-selection`. Offline checkpoint/observer schemas and a
  deterministic Jupyter qualification bundle were added, but no executable plan or
  authorization block exists and no account, mutation, paid-compute, SSH, Jupyter,
  container, browser, model, SiRA, or scientific action occurred.
- 2026-08-11: Gate L2.3 validated the new private image/manual-action decision,
  resolved private image/key/firewall/IP and ownership bindings only into ignored
  sealed evidence, verified a one-way APFS archive copy, and rendered plan
  `PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3` / run
  `RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003`. The 21,641-byte plan has
  SHA-256 `1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654`,
  23 ordered actor steps, 13 user checkpoint templates, zero automated mutations and
  an expiry-before-credential guard. It remains unauthorized; no account/model
  request, secret access, cloud mutation, paid compute, SSH, Jupyter, pull, container,
  browser, SiRA or scientific action occurred.
- 2026-08-11: The one-GET firewall capture completed HTTP transport and retained the
  exact 660-byte response, then stopped at its original `schema_drift` disposition.
  Offline adjudication found one compatible additive data-level metadata key, accepted
  it by name/type without publishing its value, preserved strict rule semantics, and
  produced a description-aware private baseline and PATCH restoration payload. The
  baseline was hash-verified and copied to the approved external archive without any
  provider request or mutation during closeout.
- 2026-08-11: Freeze the high-assurance T07 infrastructure track at
  `high-assurance-infrastructure-frozen`. Preserve its controls and terminal negative
  results, create no replacement execution plan, and hand future bounded-smoke design
  to `phase-1/sira-smoke-bounded` under a new plan, review and authorization.
- 2026-08-27: Preserve V9 and its raw artifacts as immutable historical evidence.
  Register `PLAN-EXP0001-PILOT-V10` only as an unauthorized successor proposal with
  fresh `AUTONOMOUS-0003` identities. Its Category 1 repair is tracked in
  `docs/harness/T09_V10_IMPLEMENTATION_LEDGER.md`; no live qualification, provider or
  model request, browser action, condition, or pilot execution is part of that work.
- 2026-08-28: Preserve the stopped V10 Category 3 host as immutable operational
  evidence with no empirical condition consumed and verified cleanup. Register
  `PLAN-EXP0001-PILOT-V11` only as an unauthorized successor proposal with fresh
  `AUTONOMOUS-0004` identities and model-metadata verification ordered before Lambda
  launch. Its Category 1 repair is tracked in
  `docs/harness/T09_V11_IMPLEMENTATION_LEDGER.md`; it performs no credential,
  provider, live-runtime, or scientific action.

## Decision log

- 2026-08-08: Keep authorization eligibility distinct from live readiness. T07 owns
  deterministic command/environment/budget/log/cleanup materialization after exact
  authorization and must stop before execution if any requirement fails.
- 2026-08-08: Treat all RQ-H2K trace-sufficiency outputs as infrastructure evidence;
  they neither block EXP-0001 on optional-field absence nor support an internalization
  claim.
- 2026-08-09: Approve the MacBook Pro Target Disk Mode destination only for sealed,
  hash-verified artifact retention. Do not infer active-attempt or Docker-disk
  suitability from its block interface or capacity.
- 2026-08-09: Evaluate, without yet approving, the user-selected external Docker VM
  disk topology under a new `/Volumes/Macintosh HD - Data/GIC-Lab` root. Preserve the
  MacBook volume's sealed-retention approval while requiring a later authorized B2a
  reconnect probe before runtime-storage qualification.
- 2026-08-09: Terminate the current local-runtime selection under D-019. Preserve the
  sealed-retention root, retain Docker artifacts only as blocked provenance, reject
  the reviewed Colima/Lima topology, and require a new user topology choice before any
  installation or qualification authority can be proposed.
- 2026-08-09: Under D-020, select a short-lived x86_64 Lambda On-Demand Cloud host as
  T07's planned substrate. Keep L1 GET-only inventory, L2 host qualification, L3 B2b
  qualification, and L4 live execution as four separate authorization boundaries;
  attach no Lambda persistent filesystem and terminate by exact provider instance ID.
- 2026-08-09: Under D-021, preserve both V1 Gate L1 attempts, retire run 0001, and
  require the fresh V2/0002 path to seal a complete durable request ledger before its
  inventory can bind Gate L2. The V1 observability gap establishes no provider,
  secret, endpoint, network, or transport fault.
- 2026-08-10: Under D-022, preserve run 0002 and its original schema-drift ledger,
  classify its exact mismatch as unadjudicated because the raw body is absent, and
  replace its future execution path with a fresh seven-GET V3 plan that omits broad
  audit history and requires no account LRN.
- 2026-08-10: Under D-023, preserve successful sealed run 0003, repair image identity
  as one alias per official image ID plus regional availability, and stop Gate L2 at
  `inventory-evidence-insufficient` until matchable account SSH public-key evidence
  and the required firewall/host-key human decisions exist.
- 2026-08-10: Under D-024, minimize the next evidence read to one separately
  authorized `GET /api/v1/ssh-keys`, with a fresh run/ledger and ignored raw evidence;
  do not repeat inventory, expose key material publicly, select a key, or imply Gate
  L2 authority.
- 2026-08-10: Under D-025, accept the user's sealed Gate L2 choices and unique Gate
  L1A key match, bind the current same-version-drifted OpenAPI bytes, but stop at
  `blocked-human-or-source-decision`. The source contract cannot guarantee discovery
  and exact-ID termination after an unknown launch response, and independent review
  found the draft controls do not form one enforceable supervisor/evidence path. No
  executable plan or authorization block is issued.
- 2026-08-10: Under D-026, remove local SSH fingerprints and paths from the current
  public run-0003 adjudication while preserving the original Git object and leaving
  sealed evidence untouched.
- 2026-08-10: Under D-027, terminate the automated Lambda API-launch design at
  `manual-console-launch-required`. Retain the Gate L2.1 marker/journal/watchdog/cap
  code as non-authoritative offline evidence, reject the unmaterialized V2 identities,
  and require any future Gate L2 proposal to use a newly reviewed human-operated
  console launch/observation/cleanup topology with fresh authority.
- 2026-08-10: Under D-028, retain D-027 and stop the manual-console/Jupyter design at
  `blocked-human-image-selection`. Recommend but do not select `img-0032` /
  Lambda Stack 22.04 / `22.4.5-2141`; create no executable plan until the user makes
  a new private image and manual-action decision.
- 2026-08-11: Under D-029, accept the separately supplied private Gate L2M decision,
  publish only aliases/hashes, and render one exact executable-but-unauthorized
  manual-console transaction. Keep user console mutations separate from the GET-only
  observer, restrict incident termination to ruleset-bound private IDs, require exact
  restoration/sealing, and expire the plan rather than using stale public metadata.
- 2026-08-11: Under D-030, preserve V3/run 0003 as a safe pre-mutation failure. Its
  observation projected all current firewall fields but did not retain raw bytes or
  unknown key structure, so it is not lossless restoration authority. Supersede the
  V3 manual packet, require the fresh one-GET baseline-capture plan, and prohibit a
  V4 manual plan until that response is completely retained, validated and sealed.
- 2026-08-11: Under D-031, preserve the capture's original `schema_drift` while
  adjudicating its additive metadata as compatible, seal the exact baseline and
  restoration semantics, and freeze rather than delete the high-assurance track. A
  separately governed bounded child may reuse validated controls but must apply the
  Occam admission rule and obtain fresh execution authority.
- 2026-08-27: Keep V9 scientifically frozen and ineligible for future pairing. Repair
  the provider reservation primitive, canonical offline refinalization receipt, and
  early cleanup authority in V10 without changing any scientific field or granting
  execution authority.
- 2026-08-28: Classify V10's safe zero-byte owned Docker cidfile as a transient
  publication race, preserve its stopped/cleaned host and consumed authorization, and
  advance only a descriptor-safe V11 reader plus fresh unauthorized identities. Keep
  unsafe metadata, malformed nonzero content, exact-ID cleanup authority, deadlines,
  scientific fields, and zero condition retries unchanged.
- 2026-08-28: Preserve V11's stopped one-request model-metadata conflict and advance
  only the fresh unauthorized V12 receipt-handoff repair. The local control plane owns
  the sole metadata GET; provider launch validates its sealed receipt before mutation,
  and the host validates it offline with zero additional metadata requests. Category 1
  performs no live provider, cloud, browser, SiRA, evaluator, or scientific action.
- 2026-08-29: Complete the V12 source-bound receipt handoff repair. Require the
  provider to retain the canonical receipt in the entry-source bundle, require the
  host to resolve that exact copy before offline validation, and reject arbitrary
  receipt substitution or a network fallback. Preserve the exact scientific
  contract and keep every V12 authorization/execution flag false.
- 2026-08-29: Repair the V12 timing boundary identified in PR #5 review. Provider
  launch now owns the 1,800-second freshness admission at the actual launch-send
  boundary; host validation is durable and offline, keeps prelaunch timestamp
  ordering, and does not re-expire the receipt against its current clock. The
  total remains one local metadata GET, with provider and host counts zero.
- 2026-08-29: The independent timing/ownership rereview was CLEAN. GitHub Actions
  run `33254982807` (job `99106994521`) tested source head
  `4a0bf0d98206554277f163f2c2c83a54358e2462` and passed exact-base parity with no
  newly failing or missing base-collected nodes. A documentation-only closure
  commit remains subject to its own exact-head CI run.

## Blockers and user actions

T09 V12 is blocked from execution, not from local review. Required user-facing gates
are exact-head PR review, user approval of the reviewed SHA, a separate Category 2
merge-only turn, and a fresh Category 3 Luna authorization. Historical V11 Lambda,
firewall, credential, container, image, browser, condition, and attempt identities are
not reusable. No V12 run root may be materialized before that future authorization.

## Next permitted work

The next permitted T09 work is exact-head review of the draft V12 receipt-handoff PR,
followed only by the separately authorized Category 2 merge. Category 3 remains
unavailable until a fresh Luna authorization binds the reviewed merged commit and
exact V12 plan SHA-256. Absent that authorization, no live account, cloud, model,
browser, container, evaluator, FanOutQA, or SiRA action is permitted.
