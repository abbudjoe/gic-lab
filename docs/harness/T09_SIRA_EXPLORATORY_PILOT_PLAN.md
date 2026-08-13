# T09 SiRA two-task pragmatic calibration pilot plan

Status: **V3 lifecycle repair implemented; current-turn execution authorized only
through a clean-commit private overlay**

Plan ID: `PLAN-EXP0001-PILOT-V3`

Planning terminal state: `ready-for-t09-pilot-authorization`

The tracked plan remains `authorized: false`; repository bytes are not a reusable
cloud capability. The user's 2026-08-13 instruction authorizes one single-use private
overlay after the focused gates, independent review, clean freeze, and exact dynamic
preflight pass.

## Scope and interpretation

This is a two-task, four-attempt calibration pilot. It may report whether each task
completed, whether the exact evaluator produced a valid score, pair matching,
task-level calls/tokens/browser actions/wall/cost, gross floor or ceiling behavior,
and whether a larger exploratory pilot is operationally justified. It cannot estimate
an effect or variance, test significance, claim condition superiority, accept or
reject EXP-0001, or support a GIC/H2K architectural conclusion. A Task-A checkpoint
stop is an operational calibration decision, not an unbiased scientific sample.

## Gap ledger

| Class | Gap | V3 disposition |
|---|---|---|
| Execution blocker | The V2 provider lifecycle fixed the whole campaign to 3,600 seconds while the four-attempt plan allowed 14,400 seconds. | Resolved by the user-authorized, plan-driven 14,400-second actual-time campaign, 13,500-second normal termination cutoff, and 900-second cleanup reserve. |
| Execution blocker | Admission reserved all future theoretical attempt maxima at campaign start. | Resolved. Each attempt is admitted independently only when its 3,600-second hard wall, 600-second evaluator/evidence handoff, 60-second termination-dispatch margin, and 900-second cleanup reserve remain. Setup and every later phase consume the same billable clock. |
| Execution blocker | Provider entry/condition execution were hard-disabled at the V2 risk boundary. | Resolved by parameterizing the existing observer timing primitive and retaining source-derived, structurally redacted projections for the one-shot T07-pragmatic Lambda operations. No persistent cloud service or watchdog was added. |
| Analysis blocker | Upstream evaluator normalization is task-specific. | Resolved by freezing exact upstream scoring and reporting task-level scores only. The ordinary Task B fixture score of 0.5 is not a proven ceiling; a retained edge fixture scores 1.0. |
| Publication-only blocker | Dataset rows, traces, answers, and screenshots require attribution/share-alike, privacy, and third-party-content review. | Private access-controlled execution is permitted; public raw release remains blocked. |
| Nonblocking optional gap | Unsupported H2K causal/mechanism fields are absent. | Retain explicit `unavailable` values; never infer them. |
| Nonblocking optional gap | Pilot processes are not expected to use the A10 GPU. | Record visibility/utilization metadata and make no acceleration claim. |

## Frozen science and data

- Experiment: `EXP-0001`.
- SiRA: `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Model for every role: `gpt-4o-2024-11-20`, service tier `default`, no fallback.
- Dataset: November 2023 FanOutQA development snapshot; official source commit
  `989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33`; pinned SiRA blob
  `76ad1feb689b754bfe4e5e24d3ea371b647efa67`; SHA-256
  `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`.
- Seed: `42`; tasks were preserved without outcome knowledge or substitution.

| Assignment | Task ID | Text SHA-256 | Reference SHA-256 | Record SHA-256 | Order |
|---|---|---|---|---|---|
| Task A | `7dcbbbdc7f1120cd` | `153a4f251fbeb29bee8e5ca4626e6db14426063728b0d5cfa7eed3a9a230992b` | `fc40734fa183e839b56a7c89b16faa5900865cbee7a4210fcb251a99176f98de` | `cc5c3fdeea2c1f58b6160175bd3104dbea40c290ea8b390d29413e6410d97e15` | reactive, simulative |
| Task B | `2120afba8009bad3` | `9b2b443898959b28c7408ed1ff56ebd332c9e7f2142657c11c7d09aa507ba66e` | `2ee9d892e24441d5f5bbf31b7616c1ade5977af26d22e4020f92a162fa23becb` | `5f5a8ad5353b839def2ffc968c36c4314bb830f11f10268f410faa37690bc129` | simulative, reactive |

The exact pinned SiRA FanOutQA evaluator uses no judge model or provider request.
Primary task score is upstream `acc_loose`; raw evaluator input/output and other
upstream fields are retained. Offline fixtures cover correct, incorrect, partial,
malformed, missing, exception, duplicate, normalization-edge, and both task rows.

## Orthogonal attempt states

`process_exit`, `artifact_execution`, `task_completion`, `answer_production`,
`evaluator_validity`, and `task_score` remain independent. Exit zero is never task
success. Artifact execution requires empirical entry plus at least one retained
source-grounded provider/action event. Completion requires the exact retained session
completion state and a valid terminal answer action. Infrastructure invalidity is
mutually exclusive with a validly executed condition failure. Evaluator failure or
missing required evidence yields a null score and explicit reason.

## Lifecycle and runtime enforcement

The campaign clock begins conservatively immediately before the sole launch request
crosses send-start. Setup,
runtime preflight, all attempts, evaluator work, evidence handling, and cleanup consume
that same actual clock. The hard provider/Lambda wall is 14,400 seconds. Normal
termination must begin by 13,500 seconds, preserving 900 seconds for cleanup. Only a
provider control-plane delay may cause best-effort termination evidence after the
absolute wall; it never authorizes more empirical work.

At every attempt boundary:

1. calculate actual time since the durable provider launch send-start;
2. require at least 5,160 seconds for the next condition, evaluator/evidence handoff,
   provider dispatch, and cleanup envelope;
3. do not reserve later attempts or setup maxima;
4. refuse entry, preserve completed evidence, and clean up if the rule fails.

Condition, pair, campaign, Lambda-duration/cost, output, disk, model-call, token,
OpenAI-cost, browser-step, attempt-count, and zero-retry caps are enforced in the host
and in-container paths. The empirical boundary is the first task model request or
task browser action. Before it, common infrastructure may be repaired; after it, the
attempt is consumed and code/science remain frozen for the campaign.

Runtime identity remains the successful T07 pragmatic environment: Python 3.11.14,
x86_64 Linux, Playwright 1.39.0, Chromium 1084, image
`sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`,
one Lambda `gpu_1x_a10` in `us-east-1`, no persistent filesystem, and no GPU device
request inside pilot/evaluator containers.

## Budgets

Planning values inherited from the reviewed calibration arithmetic are USD 0.512970
per reactive attempt, USD 0.729015 per simulative attempt, USD 1.241985 per pair, and
USD 2.483970 for four attempts. The four-hour Lambda maximum is USD 5.16; the user's
conservative expected aggregate envelope is approximately USD 7.643970.

Hard aggregate ceilings are USD 40 OpenAI, USD 5.16 Lambda, USD 45.16 combined,
4,620 model calls, 4,000,000 tokens, 120 browser actions, four attempts, and zero
condition retries. Per-attempt caps are 1,155 calls, 1,000,000 tokens, USD 10 OpenAI,
30 actions, 3,600 seconds, and 64 MiB output. Pair wall is 7,200 seconds; pilot disk
is 2 GiB. Each condition retains its full 3,600-second wall; a separate 600-second
evaluator/export handoff and 60-second provider-termination dispatch margin must also
fit before admission. Each finalized attempt is streamed, hash-verified locally, and
acknowledged back to the host before the next empirical entry, so the 900-second
provider cleanup reserve is never borrowed for terminal transfer. These are emergency
stops, not expected spend.

## First-pair checkpoint

After both Task A attempts, continue only when both have reconstructable evidence and
valid evaluator execution, pair matching remains valid, credential/container/browser
cleanup is clean, no hard cap was exceeded, actual/projected costs remain below the
hard ceilings, Task B can still add calibration value, and at least the next
3,600-second condition wall, 600-second evaluator/evidence handoff, 60-second
termination-dispatch margin, and 900-second cleanup reserve remain. Otherwise seal
`stop-before-task-b`, preserve Task A, and clean up. A passing checkpoint needs no
second authorization.

## Evidence, privacy, and cleanup

Per attempt retain task/pair/order, exact command/config/commits/runtime, model/tier,
timestamps, provider call lineage and usage, tokens, requested actions and post-action
results, session, answer, screenshots, stdout/stderr, normalized events, evaluator
input/output/score, orthogonal completion state, and cleanup receipt. Unsupported H2K
fields are explicit `unavailable` values.

Structurally exclude keys/tokens, Jupyter URLs, private IP/CIDR, and unrelated account
identifiers. Raw evidence stays private. On every success or failure: stop/remove
owned containers, close browser processes, destroy temporary credential material,
stage the available evidence when time permits, terminate the exact instance, prove
terminal/absent and zero T09 instances, and restore/delete only owned security state.
Termination takes priority over archive perfection, tests, or documentation.

## Fresh identities and matching

Fresh identities are `RUN-T09-PILOT-HOST-0001`, the four ordered
`RUN-T09-TASK-*-0001` attempts, four `RUN-T09-EVAL-*-0001` evaluator identities,
`PAIR-EXP0001-PILOT-V3-TASK-{A,B}`, and
`ARCHIVE-EXP0001-PILOT-V3-0001`. No T07 or blocked-T09 run identity is reused.

Both task pairs are machine-rendered and diffed. Equality is required for task,
model, runtime, tools, steps, timeouts, evaluator, instrumentation, evidence, and
budgets. Only the source-declared reactive/simulative treatment, identity/order,
condition-owned paths, and realized events may differ.

## Authorization boundary

Tracked authorization stays false. One private, mode-0600, single-use overlay must
bind the exact clean package commit, plan bytes/SHA-256, all identities, numeric caps,
allowed actions, artifact destination, and this current-turn authorization before the
first provider mutation. No second launch, condition retry, substitution, training,
pilot expansion, or scientific conclusion is authorized.
