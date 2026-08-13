# T08 SiRA pilot readiness

Status: **historical T08 readiness record; superseded by the T09 lock package**

Plan: `PLAN-EXP0001-PILOT`

The T08 planning gates pass: the smoke pair contract is valid, retained evidence is
complete enough for its one-step artifact-execution purpose, and cleanup is verified
with only documented nonmaterial gaps. This permits preparation of T09 planning
documents. It does not make the pilot execution-eligible.

## Proposed smallest directional pilot

- Two frozen FanOutQA task pairs, four condition attempts total.
- Dataset revision `76ad1feb689b754bfe4e5e24d3ea371b647efa67`, SHA-256
  `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`.
- Task IDs `7dcbbbdc7f1120cd` and `2120afba8009bad3`.
- Counterbalanced order: reactive/simulative on task 0; simulative/reactive on task 1.
- Immutable proposed model snapshot `gpt-4o-2024-11-20`; directional reproduction
  under the already declared historical-model substitution.
- Task-level paired scoring only. Two pairs are enough to test scoring, completion,
  floor/ceiling behavior, variance plumbing, and cost capture, not effect size or
  confirmatory inference.

Proposed aggregate ceilings are 4,620 model calls, 4,000,000 model tokens, 120 browser
actions, 14,400 attempt-wall seconds, USD 40.00 OpenAI spend, 4.0 A10 hours, and USD
5.16 provider compute at the retained USD 1.29/hour rate, for USD 45.16 total. The
retained rate is only a planning basis and must be freshly reverified. The T07
one-step USD 0.0403325 cost is not a full-task cost estimate or pilot evidence.

## Remaining execution blockers

1. A new current-turn user authorization must bind the final clean commit, plan and
   child hashes, exact provider/model/substrate, all caps, stopping rules, evidence,
   and cleanup contract.
2. FanOut spaCy and `en_core_web_sm` evaluator versions, hashes, licenses, and
   deterministic behavior must be immutably pinned and smoke-tested offline.
3. Current Lambda price/capacity, exact image, firewall, zero-instance state, and
   immutable model availability need fresh read-only reverification.
4. Source, protocol, configuration, environment, image, browser, command, evaluator,
   and pair-diff identities must be materialized before empirical entry.
5. The locked experiment protocol still records zero GPU hours. A reviewed version
   must reconcile that operational cap before cloud authorization without changing
   treatment, tasks, scoring, or interpretation.
6. Model-call, token, browser-action, wall, API-spend, provider-spend, accelerator,
   output, and aggregate stops must be effective in the selected runtime.
7. Provider-response retention must structurally omit/redact ephemeral Jupyter access
   values while preserving safe lifecycle evidence.
8. Complete post-action browser results, normalized events, regulation-decision
   lineage, per-call receipts when available, artifact hashes, cleanup, transfer, and
   terminal provider evidence must be retained.
9. Dataset/evaluator public-release licensing and privacy remain unresolved; raw
   publication stays blocked.

Until every blocker is closed, `execution.authorized` stays false, project execution
permissions stay false, child command bindings stay null/unknown, and no T09 run may
begin.

## T09 supersession — 2026-08-13

T09 preserved this snapshot and resolved its offline evaluator, GPU-accounting,
identity, post-action evidence, structural-redaction, dataset/license, pair-diff, and
protocol contracts in `PLAN-EXP0001-PILOT-V2`. It then found a material provider-cap
incompatibility: the inherited T07 observer's 3,600-second hard wall cannot cover four
plausible full-task attempts plus bounded staging and worst-case cleanup, while the
14,400-second candidate ceiling has no source-compatible enforcement path. The T09
terminal state is therefore `t09-pilot-blocked-material-risk`; no execution is
authorized or has occurred, and provider preflight cannot begin. Public raw release
remains blocked separately.

## Pragmatic V3 supersession — 2026-08-13

The user's separately supplied current-turn execution contract supersedes only the
V2 provider-wall restriction. `PLAN-EXP0001-PILOT-V3` preserves the same two rows,
exact evaluator, model, SiRA revision, counterbalance, scoring, evidence, budgets,
zero retry, and calibration-only boundary. It replaces the 3,600-second campaign
wall with one plan-driven 14,400-second actual-time provider campaign, 900-second
cleanup reserve, and 13,500-second normal termination cutoff. Each attempt is admitted
only when its full condition wall, evaluator/evidence handoff, positive termination
margin, and cleanup reserve remain; future maxima are not summed at campaign start.
Execution still requires the exact clean freeze, private
single-use overlay, dynamic preflight, and one-launch cloud ledger. Public raw release
remains independently blocked.
