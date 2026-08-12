# T08 SiRA smoke evidence adjudication

Status: **smoke evidence validated; pilot planning eligible; pilot execution unauthorized**

Terminal state: `smoke_evidence_validated_pilot_planning_eligible`

This is an offline adjudication of retained T07 evidence. It is not a new run and it
does not interpret the reactive/simulative pair scientifically. The authoritative
machine record is
`experiments/EXP-0001-sira-simulative-vs-reactive/T08_SMOKE_ADJUDICATION.json`.

## Disposition

| Contract | Reactive | Simulative |
|---|---|---|
| Artifact execution | `passed` | `passed` |
| Task completion | `not_observed` | `not_observed` |
| Session `is_complete` | `false` | `false` |

The pair is `matched_pair_valid_with_documented_evidence_gaps`. Evidence is complete
enough to adjudicate the one-step smoke, cleanup is
`cleanup_verified_with_nonmaterial_gap`, scientific interpretation is prohibited,
and preparation of an exploratory pilot protocol is eligible. None of those findings
authorizes pilot execution.

## Immutable identity verification

Every value below was recovered from retained evidence or the versioned compute
record; no absent identity was filled from the request summary.

| Identity | Verified value or disposition |
|---|---|
| T08 start | Branch `phase-1/sira-smoke-t08-evidence`, clean start commit `27f66e6a82edffa57e497516bf3969a199675f06` |
| Frozen GIC Lab run commit | `5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23` |
| SiRA commit / tree | `93fb8d72de71f9a4a13419670adeb34d93cf7acd` / `6a6d9068b94d7632d3533a3d6f013d4de6ff76e8` |
| Host / conditions | `RUN-T07-PRAGMATIC-HOST-0002`; reactive and simulative `0002` identities |
| Run manifest | 8,196 bytes; SHA-256 `877c26d16e242733e4f86afc54a058b868ca79ee27b826abc5e1e92ae0427ccd` |
| Container image | `sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c` |
| Python | 3.11.14; executable SHA-256 `6ff97f602038740073dca96714310a30e303332326268e0f1bb2767edc820944` |
| Dependencies | UV lock `138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e`; 96-package installed manifest `4ff2603fa5e0f7033ba773decdcb86abf648dcce22e469d26bc48214e390e104` |
| Browser | Playwright 1.39.0; Chromium revision 1084; executable SHA-256 `0498f208c25339f386413ada7b3c35293b0b6250e67d85446ba9541d7fd636f7` |
| Model snapshot | `gpt-4o-2024-11-20` for every SiRA role; routing SHA-256 `8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619` |
| Condition statuses | Reactive `bcacad4492d42035dc4c2c661e0eff6c3fdadc20e9ce1f63810140771968cced`; simulative `2f03756fb582c32d1f7b1fc27f6843d6b2eac0d9e4198eafdd1a02f9cd330bc5` |
| Remote evidence | Archive 65,829 bytes, SHA-256 `4deebc0477581377e2bbb71a8f075bf8b3712188865f0e1faa5c0e7f62dc0450`; all 138 manifest payloads rehashed |
| Local retained manifest | 147 entries, 22,869,287 bytes; SHA-256 `b2576a030ffa56c1b2e3b0b111e9dce71b999cb12acba8add6a78483974b4652` |
| External sealed manifest | 148 entries, 22,893,061 bytes; SHA-256 `9fb9ee63c1703e9701e8d5168284a1f757181baadd68a1508095eeac5fc7a167`; source/destination hashes equal |
| Tracked T07 summary | SHA-256 `ec1e2fb0a8e04997b4a87f9f2a898f597b70440b1df4f8a9dfba1da67ef5321c` |

The run bundle contains the authorization reference through `CMP-0003`, but not the
full authorization payload. That absence is classified `missing-nonblocking`; the
reference is not treated as a substitute for the absent payload.

## Condition reconstructions

The machine record wraps every requested reconstruction field in a value,
`observed`/`derived`/`inferred`/`unavailable` provenance, evidence references, and an
optional caveat. Exact 79-element Docker argument arrays are retained in that record.

### Reactive

- Observed assignment: `SIRA-REACTIVE`, query `go to google flights`, maximum one
  browser step, working directory `/opt/sira`, immutable model snapshot for all roles,
  and service tier requested/returned as `default` at the aggregate response level.
- Source-resolved configuration: `web_reactive`, policy planner, temperature 0.0,
  top-p 0.5. This source configuration is `derived`, not re-labeled observed.
- Observed interval: `2026-08-12T21:47:35.259191Z` through
  `2026-08-12T21:47:53.322547Z`; container and process exit codes were zero.
- Model-call sequence: four calls, derived from distinct retained state/intent,
  action, and memory evidence. Per-call provider receipts, usage, latency, and cost
  are unavailable.
- Browser evidence: one requested `goto('https://www.google.com/flights')` action.
  The runtime ledger count is derived from session history, which records the request
  before `env.step`. The retained 1280x720 JPEG is the pre-action `about:blank`
  observation; no structured post-action result was retained. Actual action
  performance is therefore inferred from normal exit, not observed directly.
- Session JSON and source logs were written; the session reports `is_complete: false`
  and an empty error string. Owned browser state closed, the container exited, and it
  was removed.

### Simulative

- Observed assignment: `SIRA-SIMULATIVE` on the same query, browser-step cap,
  working directory, immutable role routing, runtime, and aggregate `default` service
  tier contract.
- Source-resolved configuration: `web_simulative`, world-model planner, five candidate
  actions, depth one, 20 policy and 20 critic samples, with the retained log showing
  the one-cluster direct-selection branch. These source-mode fields are `derived`.
- Observed interval: `2026-08-12T21:48:41.268939Z` through
  `2026-08-12T21:49:02.688173Z`; container and process exit codes were zero.
- Five model-call attempts are observed in the budget ledger. State, 20-sample policy,
  action, and memory roles are reconstructable; the exact role of one intermediate
  planner call is `inferred` because same-second source logs overwrote detail and no
  per-call provider receipt was retained.
- The same one requested browser action, pre-action JPEG, missing structured
  post-action result, session `is_complete: false`, empty error, and successful owned
  browser/container cleanup apply.

T07 did not retain canonical normalized-event or standalone regulation-decision
files. T08 therefore derives, without modifying raw evidence, a six-event view per
condition: `regulation_decision`, `observation`, `belief_state`, `plan`,
`requested_action`, and `outcome`. The selected mode is classified as external
`experiment_assignment`; unavailable causal parents, confidence, override, fallback,
and realized outcome remain null/unavailable.

## Independent accounting reconciliation

The recomputation uses exact decimal arithmetic and the retained rate record: USD
2.50/M uncached input, USD 1.25/M cached input, and USD 10.00/M output. Raw JSON
binary-float strings are retained separately; displayed wall time rounds to three
decimal places.

| Measure | Reactive | Simulative | Aggregate |
|---|---:|---:|---:|
| Model calls | 4 | 5 | 9 |
| Input tokens | 4,626 | 5,447 | 10,073 |
| Cached-input tokens | 0 | 0 | 0 |
| Output tokens | 260 | 1,255 | 1,515 |
| Total tokens | 4,886 | 6,702 | 11,588 |
| Recomputed cost (USD) | 0.014165 | 0.0261675 | 0.0403325 |
| Recorded browser-action requests | 1 | 1 | 2 |
| Wall seconds | 18.019464842999923 | 21.37802647699982 | 39.397491319999743 |
| Unreconciled attempts | 0 | 0 | 0 |

No condition retry or transport retry occurred. A parser-retry count of zero is
`inferred`, because provider calls were not tagged by retry kind. Per-call token,
latency, and cost allocation is unavailable and is not fabricated from condition
totals. The run bundle did not bind the pricing-record hash, so the rate match is
derived from the frozen runtime and current versioned record rather than called an
observed run-manifest binding.

## Evidence completeness and H2K boundary

Evidence is `complete_for_smoke: true`. Missing but nonblocking items are the full
authorization payload, per-call receipts, original normalized events and regulation
record, post-action result/task completion, exact provider termination transition
timestamp, container locale/timezone identity, and one private-retention privacy gap.
None prevents identifying treatment, artifact execution, aggregate spending,
execution history, pair validity, or terminal cleanup.

H2K trace sufficiency is `partially_sufficient`. The pair preserves decision source,
assigned/available/selected mode, policy/config revision, condition-level model/tool
costs, and the downstream requested action. It lacks causal-parent sequences,
per-call costs, realized outcome, and source-supported override/fallback fields. This
supports schema and lineage work only—not learned regulation, internalization,
controller superiority, causal comparison, or a training-ready corpus.

## Cleanup adjudication

Cleanup is `cleanup_verified_with_nonmaterial_gap`: the exact instance identity and
launch time are retained; terminal absence was observed at
`2026-08-12T21:52:35.003136Z`; account running-instance count, owned containers, and
owned regional rulesets are zero; the global firewall is byte-identical before/after;
the temporary model secret was removed; and the external copy rehashes exactly.

The exact provider termination-transition timestamp is unavailable. In addition, 37
private raw provider-response/poll files retain inactive ephemeral Jupyter access
fields that were outside T07's historical API-key-value scan. T08 records only key
names and affected artifact aliases, never values. Provider instance termination
invalidated the ephemeral material, so no long-lived credential rotation is required.
Future evidence must structurally omit or redact those values.

## Interpretation and next boundary

The smoke supports artifact execution from observed runtime/model/session/exit/cleanup
records plus an explicitly inferred browser-action-performance component. It also
establishes retained evidence, pair-contract validity, cleanup, and readiness to
prepare an unauthorized pilot. It does not show either mode
is better; it does not pass or fail EXP-0001; it does not support or refute GIC or
RQ-H2K; and it is not production-readiness evidence.

No Lambda/OpenAI/provider request, cloud mutation, model call, browser action, SiRA
condition, training, pilot execution, or scientific interpretation occurred in T08.
