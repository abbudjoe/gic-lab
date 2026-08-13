# T09 SiRA two-task calibration pilot plan

Status: **ready for a fresh exact authorization; execution remains unauthorized**

Plan ID: `PLAN-EXP0001-PILOT-V2`

Terminal planning state: `ready-for-t09-pilot-authorization`

This is an offline execution package. It did not launch or contact Lambda, OpenAI, a
browser, SiRA, or FanOutQA. `execution.authorized` remains `false` in the parent and
all four child plans. A later user instruction must bind the final clean commit and
the exact packet before any dynamic preflight or execution.

## Scope and interpretation boundary

The pilot asks whether two frozen FanOutQA tasks can complete under both externally
assigned SiRA conditions, produce valid exact-upstream evaluator outputs, remain
matched and reconstructable, and yield realistic task-level completion and cost data
for deciding whether a larger exploratory pilot is feasible.

Report the four attempts and two task pairs descriptively. The two pairs may expose
pipeline failures, valid scoring, gross floor or ceiling behavior, treatment drift,
and task-level call, token, browser-step, wall-time, and cost behavior. They do not
support an effect-size or variance estimate, a significance test, condition
superiority, acceptance or rejection of EXP-0001, an H2K conclusion, or a GIC
architectural conclusion. Stopping after Task A is a calibration decision and does
not create an unbiased scientific sample.

## Proposal audit and gap ledger

The starting `PLAN-EXP0001-PILOT` proposal encoded an effect-oriented question,
condition-dependent model-call ceilings, unmaterialized evaluator and task contracts,
and typed caps without a complete runtime enforcement path. Changing those elements
to a calibration-only question, an exact evaluator, pair-equal limits, and enforceable
contracts changes scientific meaning. The original proposal is therefore preserved
at `run-plans/proposals/PLAN-EXP0001-PILOT.json`; T09 creates V2 rather than silently
rewriting its identity.

| Class | Gap | T09 disposition |
|---|---|---|
| Execution blocker | Exact evaluator, model asset, package closure, and behavior were unbound. | Resolved by the pinned evaluator contract, exact file hashes, locked dependency group, and offline fixture suite. |
| Execution blocker | Task records lacked complete release, row, text/reference/record hash, selection, license, and retention bindings. | Resolved by the dataset contract; the existing two rows are retained without outcome-based replacement. |
| Execution blocker | Post-action results, per-call lineage/usage, aggregate accounting, cleanup receipt, and hard-cap enforcement were incomplete. | Resolved by the small T09 overlay on the T07 pragmatic runtime and fail-closed tests. |
| Execution blocker | Condition-owned plans had unequal model-call limits and no exact rendered-command binding. | Resolved with one pair-equal 1,155-call attempt cap, four fresh attempts, and machine-rendered pair diffs. |
| Execution blocker | The final clean commit, immutable packet hashes, fresh authorization, and dynamic preflight do not yet exist together. | The package supplies the static bindings. Fresh authorization is the only remaining execution blocker; the authorized turn must run the exact preflight before empirical entry. |
| Analysis blocker | The upstream evaluator has task-specific normalization behavior, including a 0.5 effective correct-fixture ceiling on Task B. | Resolved for calibration analysis by freezing and reporting the exact behavior at task level; no repair, renormalization, or cross-task effect estimate is allowed. |
| Publication-only blocker | Raw tasks/references are CC-BY-SA-4.0 and traces/screenshots may contain third-party or private material. | Private access-controlled research use is permitted; public raw release remains blocked pending attribution, share-alike, third-party-content, privacy, and redaction review. |
| Nonblocking optional evidence gap | Unsupported H2K mechanism fields and causal lineage unavailable from upstream remain absent. | Record `unavailable` with reason; never infer them. |
| Nonblocking optional evidence gap | SiRA/evaluator are expected not to use the visible A10. | Record CUDA identity and practical utilization samples; zero use is valid and no acceleration claim is made. |
| Nonblocking optional evidence gap | The runtime is manually supervised and not production infrastructure. | Documented limitation; it does not affect pairing, scoring, credentials, spend, cleanup, or reconstruction. |

No publication-only or optional gap blocks private pilot execution. Dynamic model
availability, price, capacity, firewall, credential-channel, and zero-instance checks
are exact preflight conditions, not reasons to mutate infrastructure in this planning
turn.

## Frozen scientific and task contract

- Experiment: `EXP-0001`.
- SiRA commit: `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Model for every role: `gpt-4o-2024-11-20`; service tier `default`; no fallback.
- Dataset: archived November 2023 FanOutQA development snapshot, official FanOutQA
  repository commit `989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33`, byte-identical pinned SiRA Git blob
  `76ad1feb689b754bfe4e5e24d3ea371b647efa67`, SHA-256
  `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`.
- Selection rule: preserve the two preregistered first rows without condition-outcome
  knowledge. Neither row ran during T07/T08; no outcome-adaptive replacement exists.
- Seed: `42`, used only for frozen dataset order; it does not make provider or live-web
  behavior deterministic.

| Assignment | Task ID | Text SHA-256 | Reference SHA-256 | Record SHA-256 | Pair and order |
|---|---|---|---|---|---|
| Task A | `7dcbbbdc7f1120cd` | `153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b` | `fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de` | `cc5c3fdeea2c1f58b6160175bd3104dbea40c290ea8b390d29413e6410d97e15` | `PAIR-EXP0001-PILOT-V2-TASK-A`: reactive, simulative |
| Task B | `2120afba8009bad3` | `9b2b443898959b28c7408ed1ff56ebd332c9e7f2142657c11c7d09aa507ba66e` | `2ee9d892e24441d5f5bbf31b7616c1ade5977af26d22e4020f92a162fa23becb` | `5f5a8ad5353b839def2ffc968c36c4314bb830f11f10268f410faa37690bc129` | `PAIR-EXP0001-PILOT-V2-TASK-B`: simulative, reactive |

Rows are valid under the pinned SiRA FanOut runner, contain no required private data,
and are structurally distinct sports/list and film/currency aggregation tasks. Both
are attempted under the predeclared finite 30-action ceiling; inability to finish is
a calibration outcome, not a post hoc exclusion. Dataset details and private/public
retention rules are in `T09_SIRA_PILOT_DATASET_CONTRACT.md` and the matching JSON
contract.

## Exact evaluator

The evaluator is the pinned SiRA FanOutQA implementation at the SiRA commit above,
with file hashes and the complete environment lock in
`T09_SIRA_PILOT_EVALUATOR_CONTRACT.md`. It uses no judge model, prompt, or provider
request. Primary task score is exact upstream `acc_loose`; `acc_strict` and ROUGE
values are retained as provenance fields, not substituted metrics.

The wrapper verifies every upstream evaluator file and exact single-task cardinality,
runs the evaluator unchanged, and retains input and output. All required offline cases
pass: clearly correct, clearly incorrect, partial, malformed, missing answer,
evaluator exception, duplicate evidence, normalization edge, and Task B. Task A's
ordinary correct fixture scores 0.9 while its capitalization/punctuation edge scores
1.0 because of context-sensitive lemmatization. Task B's correct six-film fixture
scores 0.5 because the exact word-boundary expression cannot match normalized
references beginning with `$`. These are frozen evaluator properties, not observed
pilot results.

## Orthogonal attempt and score states

The runtime records these fields independently:

- `process_exit`: operating-system exit code and signal only.
- `artifact_execution`: true only when the pinned runner entered its empirical path
  and retained source-grounded provider/action evidence; exit zero is insufficient.
- `task_completion`: true only when the retained session ends in one syntactically
  valid upstream `send_msg_to_user(...)` answer action and upstream completion state.
- `answer_production`: whether that final action yields a parseable retained answer.
- `evaluator_validity`: exact evaluator identity/cardinality/load/run/schema success.
- `task_score`: exact upstream normalized `acc_loose` when evaluator validity is true,
  otherwise `null`.

A `completed task` meets the exact completion rule. An `incomplete task` reaches the
step/wall/condition stop or source failure without it. A `valid scored attempt` has a
contract-valid artifact attempt, required evidence, exact evaluator output, and no
infrastructure invalidity; an incomplete attempt may receive the exact evaluator's
score only when one valid retained session is available. An `invalid infrastructure
attempt` has authorization, identity, matching, budget, evidence, credential, or
cleanup failure. A `condition failure` is a validly executed but incomplete condition
attempt, never a score imputed for infrastructure failure. Missing evidence and an
evaluator exception are explicit codes; evaluator failure yields a null score.

## Browser, wall, and cost calibration

The T07 one-step smoke established initialization cost but could not complete FanOutQA.
The pinned upstream runner accepts a finite `max_steps`; T09 predeclares 18 expected
and 30 hard browser actions for both conditions. Action timeout is 30 seconds,
condition wall is 3,600 seconds, pair wall is 7,200 seconds, and total attempt wall is
14,400 seconds across the pilot. The runtime stops before the next provider call or task browser action,
terminates the condition process, retains partial evidence, performs cleanup, and
never retries after empirical entry.

Expected values scale T07's observed condition-specific calls, tokens, and API cost
over 18 actions and use a 720-second expected attempt duration at the retained Lambda
rate. OpenAI's official GPT-4o model page supplied USD 2.50/M input, USD 1.25/M cached
input, and USD 10/M output; Lambda's official GPU Cloud page supplied USD 1.29 per
A10-hour, both rechecked 2026-08-13. They are planning estimates, not scientific
observations, and the future preflight rejects a higher current rate.

| Quantity | Reactive attempt | Simulative attempt | Pair | Four attempts |
|---|---:|---:|---:|---:|
| Expected calls | 72 | 90 | 162 | 324 |
| Expected tokens | 87,948 | 120,636 | 208,584 | 417,168 |
| Expected browser actions | 18 | 18 | 36 | 72 |
| Expected OpenAI USD | 0.254970 | 0.471015 | 0.725985 | 1.451970 |
| Expected Lambda USD | 0.258000 | 0.258000 | 0.516000 | 1.032000 |
| Expected total USD | 0.512970 | 0.729015 | 1.241985 | 2.483970 |

Hard per-attempt limits are identical within and across pairs: 1,155 model-call
attempts, 1,000,000 total tokens, USD 10 OpenAI cost, 30 browser actions, 3,600 wall
seconds, 2 GiB output, and 1 A10-hour/USD 1.29 Lambda allocation. Aggregate limits are
4 attempts, 4,620 model-call attempts, 4,000,000 tokens, 120 actions, 14,400 attempt
wall seconds, USD 40 OpenAI, 4 A10-hours/USD 5.16 Lambda, USD 45.16 combined, and 12
GiB pilot disk. Pair wall is 7,200 seconds; Lambda duration is at most 14,400 seconds.

## First-pair calibration checkpoint

After both Task A attempts, one automatic, persisted checkpoint permits Task B only
when all conditions below are true:

1. Both Task A attempts have contract-valid, reconstructable evidence.
2. Both exact evaluator executions succeed.
3. Machine pair matching remains valid.
4. No credential-handling or cleanup issue occurred.
5. Actual first-pair use is strictly below 2,310 calls, 2,000,000 tokens, 60 browser
   actions, 7,200 wall seconds, USD 20 OpenAI, USD 2.58 Lambda, and USD 22.58 combined.
6. Projected four-attempt total remains at or below USD 45.16.
7. No severe floor or ceiling failure makes Task B incapable of adding calibration
   value.

Any failed criterion produces `stop-before-task-b`; Task A evidence is retained and
Task B is not entered. Passing produces `continue-to-task-b` without another user
authorization because the later authorization explicitly binds this rule.

## Runtime, enforcement, and freeze

The package reuses the T07 pragmatic runtime: Python 3.11.14, x86_64 Linux,
Playwright 1.39.0, Chromium revision 1084, container
`sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`,
OpenAI `gpt-4o-2024-11-20`, service tier `default`. A small repository overlay adds
only the required T09 evidence and budget controls.

Before a later launch, one preflight must verify runtime imports; evidence and
fsync/readback; condition/aggregate budget ledgers; all four rendered commands;
browser startup, screenshot, cleanup without a task action; evaluator hashes/import
and model load without provider use; task/hash loading; model/service-tier metadata
without a model request; credential-channel permissions/presence without reading or
retaining the value; and a GET-only zero-Lambda-instance check. Current price,
capacity, image, and firewall identity are checked there. A preflight failure may be
repaired only before the first task model request or task browser action. That first
event is the empirical boundary; code, tasks, order, evaluator, budgets,
instrumentation, and scientific configuration then freeze across all four attempts.

Persistent, fsync-backed counters reserve each provider call and browser action before
it is sent, reconcile provider usage receipts after return, and carry aggregate use
across attempts. The resource guard checks condition/pair/total/Lambda wall, output,
disk, and Lambda-cost ceilings before empirical operations and at finalization. State
enforces four exact attempts in order, the Task-A checkpoint, and zero retry.
Unreconciled provider attempts fail closed. Declared caps and their runtime paths are
tested directly.

## Evidence, redaction, cleanup, and GPU accounting

Each attempt retains exact task/pair/order identity; command/config and all frozen
commits; Python/container/condition/timestamps; provider request/response receipts,
role/lineage, requested and returned tier, provider IDs and usage when available;
pre-counted actions and serialized post-action observation/result/info/screenshots;
session JSON, answer, stdout/stderr, normalized causal events, regulation-decision
assignment, evaluator input/output/score, orthogonal completion states, artifact
hashes/sizes, and cleanup receipt. Unsupported H2K fields are `unavailable`, never
inferred.

Structural redaction removes Jupyter tokens/URLs, cloud/API credentials, private
IP/CIDR values, and unrelated account/provider identifiers before evidence becomes
eligible for an archive. Exact owned provider termination and a final GET-only
zero-instance receipt are mandatory closeout conditions in an authorized run.

The host exposes an A10 because it is the previously qualified convenient T07 runtime,
not because GPU computation is a treatment or expected accelerator path. Pilot,
browser-preflight, and evaluator containers request no GPU device and set
`CUDA_VISIBLE_DEVICES` empty; the host retains identifier-free `nvidia-smi` snapshots
when available. CUDA identity is therefore not applicable inside pilot processes.
Make no GPU acceleration claim.

## Matching and immutable identities

Fresh identities are `RUN-EXP0001-PILOT-V2-HOST-0001`, four ordered
`RUN-EXP0001-PILOT-V2-TASK-*` attempts, four evaluator runs, and
`ARCHIVE-EXP0001-PILOT-V2-0001`. No T07 identity is reused.

The command manifest compares condition-owned task records and plan hashes plus the
shared exact execution, evaluator, dataset, runtime, model, tool, step, timeout,
instrumentation, evidence, and budget fields. Pair equality is required for all of
them. Only source-declared `reactive`/`web_reactive` versus
`simulative`/`web_simulative`, run/order identity, condition-owned paths, and realized
events may differ. Counterbalancing changes order, not treatment configuration.

## Authorization boundary

The ready-to-copy packet is in `T09_SIRA_PILOT_PREAUTHORIZATION_PACKET.md`. A later
authorization must name its exact final commit, reviewed implementation ancestor,
plan bytes/hash, execution and command hashes, tasks/order, runtime/model, hard and
expected budgets, checkpoint, evidence/private-release boundary, cleanup, exact
provider termination, and zero-instance verification. Until then every permission
and authorization field remains false, and no preflight or pilot may begin.
