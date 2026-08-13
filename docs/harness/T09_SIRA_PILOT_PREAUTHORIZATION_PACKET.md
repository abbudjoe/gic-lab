# T09 SiRA pilot preauthorization refusal packet

Status: **`t09-pilot-blocked-material-risk`; unauthorized**

Plan: `PLAN-EXP0001-PILOT-V2`

Plan path:
`experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/pilot.yaml`

Plan bytes: `4,854`; SHA-256:
`95f73429c449486198c8283b8ca93cf8a0bdeb2f7da43cf717d868f6487b4958`.

This is not an authorization packet and contains no executable authorization command
or ready-to-copy permission text. `authorized: false` remains exact in the parent
plan, execution contract, and all four condition plans. Provider preflight and
empirical entry fail closed.

## Static package retained

- Experiment: `EXP-0001`; calibration only.
- SiRA: `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Model: `gpt-4o-2024-11-20`, service tier `default`, every role.
- Runtime candidate: Python 3.11.14 and container
  `sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`.
- Dataset: November 2023 FanOutQA development snapshot, official source commit
  `989f4c40d9deea1ecb0897d7a17a9c0fe20d5c33`, SHA-256
  `359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`.
- Tasks: `7dcbbbdc7f1120cd` and `2120afba8009bad3`.
- Order: Task A reactive then simulative; Task B simulative then reactive.
- Browser actions: 18 expected and 30 maximum per attempt; 30-second action timeout.
- Retries after empirical entry: zero.
- Interpretation: descriptive task-level calibration only; no effect, variance,
  significance, superiority, EXP-0001 decision, or H2K/GIC claim.

The exact evaluator, dataset rows, hashes, command manifests, pair diffs, local budget
primitives, completion semantics, and evidence schemas remain useful offline planning
evidence. They do not authorize execution or prove provider-lifecycle closure.

## Material execution blocker

The inherited frozen T07 GET-only observer has:

- a 1,800-second normal termination target;
- a 3,600-second hard provider wall;
- up to three 300-second cleanup checkpoints;
- additional bounded terminal polling and evidence sealing; and
- a requirement to stage and verify a reconstructable private failure prefix before
  the exact manual termination.

The requested candidate pilot has four full-task attempts. T07 one-step walls imply a
linear 18-action planning total of about 1,418.31 seconds for the four conditions
before evaluator, archive, and transfer work. The retained successful T07 host used
1,581.905 seconds launch-to-terminal while its two condition processes used only
39.397 seconds. Worst-case cleanup checkpoints alone consume 900 seconds, before
polling, sealing, and transfer.

Consequently the four-attempt scientific envelope and a defensible cleanup reserve
cannot both fit the frozen 3,600-second hard wall. The T08 14,400-second/4-A10-hour/
USD 5.16 Lambda figures are candidate maxima, but no source-compatible T07 lifecycle
can enforce them. Declaring those values without an enforcement path would violate
the T09 contract and could leave a billable resource unresolved.

T09 may not solve this by creating automated launch/termination, an independent
watchdog, or another cloud control plane. The exploratory adapter draft and stale
provider receipt schemas were removed.

## Budgets that are not authorized

Expected planning values remain:

| Quantity | Reactive attempt | Simulative attempt | Pair | Pilot |
|---|---:|---:|---:|---:|
| Model calls | 72 | 90 | 162 | 324 |
| Tokens | 87,948 | 120,636 | 208,584 | 417,168 |
| Browser actions | 18 | 18 | 36 | 72 |
| OpenAI USD | 0.254970 | 0.471015 | 0.725985 | 1.451970 |
| Lambda USD | 0.258000 | 0.258000 | 0.516000 | 1.032000 |
| Total USD | 0.512970 | 0.729015 | 1.241985 | 2.483970 |

Candidate hard maxima remain USD 40 OpenAI plus USD 5.16 Lambda, USD 45.16 total,
4,620 calls, 4,000,000 tokens, and 120 browser actions. They are explicitly
**unenforceable under the frozen provider lifecycle** and therefore cannot be copied
into an authorization.

## Analysis and publication boundaries

The exact offline evaluator suite covers clearly correct, clearly incorrect, partial,
malformed, missing, exception, duplicate, and normalization-edge fixtures. Task A's
ordinary correct fixture scores 0.9 and its normalization edge 1.0. Task B's ordinary
correct fixture scores 0.5; another normalization-edge form scores 1.0, so 0.5 is not
a ceiling. These are evaluator properties, not pilot outcomes.

Public raw release remains independently blocked pending CC-BY-SA attribution/
share-alike, third-party-content, privacy, and structural-redaction review. This is a
publication-only blocker and is not the reason execution is blocked.

## Required successor boundary

A future plan may become authorization-eligible only after it provides, without
reopening the prohibited infrastructure work:

1. one source-compatible provider wall and cleanup reserve covering the exact task
   count and staging envelope;
2. a read-only, source-grounded entry and closeout evidence path with maximal failure
   prefixes;
3. fresh plan/run/archive identities and immutable byte bindings;
4. focused cap, evidence, privacy, and failure tests; and
5. clean independent spec-conformance review.

Until then: do not call Lambda or OpenAI, launch or terminate an instance, mutate a
firewall, start a browser, run SiRA/FanOutQA, access a real key, or begin the pilot.
