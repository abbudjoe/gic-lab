# Risk Register

This is the repository-native risk record. Gate ownership names the task that must
enforce or explicitly reassign each mitigation; a risk entry is not execution
authorization.

| Risk | Consequence | Mitigation | Gate owner |
|---|---|---|---|
| Phase drift | Work runs under the wrong authority. | Project-state validation and one authoritative plan. | T00/T06 |
| Successful plans remain active | Authority becomes ambiguous. | Completed-plan placement and lifecycle/path validation. | T00 |
| Upstream commit drift | Artifact evidence is not reproducible. | Pin commits and verify checkout identity. | T01/T02 |
| Provider/model alias drift | Treatment changes over time. | Pin an immutable provider revision or declare the limitation/substitution. | T01/T05 |
| Reactive/simulative commands differ elsewhere | The causal comparison is invalid. | Machine-compare resolved configurations and commands. | T04/T05 |
| Trace normalization invents GIC state | The project records false mechanism evidence. | Field-level provenance, raw retention, and explicit schema gaps. | T04/T04.5 |
| Smoke result interpreted scientifically | Infrastructure output becomes a false result claim. | Enforce `interpretation_allowed: false` and explicit analysis boundaries. | T03/T07 |
| API or cloud cost leak | Unplanned spend or resource exposure. | Hard budgets, typed counters, stop conditions, and verified provider cleanup. | T05/T07/T09/T12/T14 |
| Raw artifact loss or overwrite | Results cannot be audited. | Fresh attempt identities, append-only events, hashes, durable copy, and validation before cleanup. | All execution tasks |
| Secrets enter commands, paths, or logs | Security incident. | Named credential injection, allowlists, exact-value scrubbing, and refusal tests. | T03/T06 |
| RQ-H2K contaminates EXP-0001 | The primary experiment silently changes question, treatment, control, or estimand. | Keep RQ-H2K planned/deferred with no active experiment; T05/T06 must verify EXP-0001 separately. | T04.5/T05/T06 |
| Fixed external assignment is labeled learned regulation | The record falsely supports an internalization claim. | Required typed `source_kind`; SiRA is always `experiment_assignment` for the paired condition. | T04.5/T06/T10 |
| Plausible prose is treated as a configurator | A latent mechanism is invented after observing outcomes. | Normalize only explicit structured source fields; preserve prose raw and mark the decision unavailable. | T04.5/T11/T13 |
| Event schema breaks T03 evidence | Historical streams become unreadable or silently reinterpreted. | Emit v0.2, retain strict v0.1 read support, forbid mixed streams, and test a committed legacy fixture. | T04.5/T06 |
| Future-track fields become EXP-0001 validity requirements | A deferred option blocks the primary experiment. | Keep trace sufficiency separate from EXP-0001 scientific validity and execution authorization. | T05/T06/T08 |
| Trace instrumentation changes condition behavior | Capture confounds the reactive/simulative comparison. | Read-only capture, resolved-pair comparison, timing/deviation recording, and no source-prose rewriting. | T04.5/T07/T09 |
| Raw prompts or traces expose private/licensed data | Security, privacy, or licensing incident. | Artifact allowlists, credential refusal/redaction, source-license review, and publication gating. | T04.5/T06/execution tasks |
| Evidence becomes a premature training corpus | Phase 1 data is repurposed without consent or split discipline. | No training export, fine-tuning path, or learned-kernel work in this package. | T04.5/T15 |
| Regulation schema overfits SiRA | Later SR²AM or explicit-model output cannot be represented neutrally. | Source-neutral event/source vocabulary plus distinct source-grounded mapping addenda. | T04.5/T11 |
| Trace-sufficiency report is overinterpreted | Infrastructure readiness is published as scientific support. | Restrict interpretation to completeness, lineage, source class, and future feasibility. | T08/T10/T13/T15 |
| T04.5 ancestry is incomplete | T02 or T04 evidence requirements are missed. | Branch only from combined integration after both accepted workstreams and a full gate. | T04.5 |
