# RQ-H2K — Progressive Harness-to-Kernel Internalization

Status: **planned/deferred**

Active experiment: **none**

Current-package role: **trace and provenance preservation only**

Implementation authorized: **no**

Training authorized: **no**

## Research question

Which externally orchestrated reasoning-control functions could eventually be
represented inside a learned reasoning model while improving efficiency,
generalization, adaptation, or scaffold independence without unacceptable loss of
auditability, safety, or reversibility?

Planning regulation is the first candidate mechanism: react directly, plan, continue a
plan, replan, verify, or ask/abstain. This ordering preserves a future research option;
it does not approve a learned controller, kernel, training corpus, benchmark, or
experimental condition.

## Source classification

Every captured control decision must use one evidence-backed source kind:

| Source kind | Meaning |
|---|---|
| `experiment_assignment` | The experiment fixed the mode before execution. |
| `external_rule` | Deterministic or typed software selected the mode. |
| `external_prompted_model` | A separately invoked model/module selected the mode. |
| `model_explicit_output` | The primary reasoning model emitted an explicit control record. |
| `human_override` | A human changed or overrode the decision. |
| `unknown` | Retained evidence cannot establish the source. |

The vocabulary deliberately has no “internalized” boolean or latent-state category.
`model_explicit_output` records an explicit output; it does not prove that the output
faithfully reports a latent mechanism. Ordinary reasoning, planning prose, or XML-like
tags are not silently converted into a regulation decision.

## EXP-0001 boundary

EXP-0001 remains the planned SiRA reactive-versus-simulative artifact comparison. It
is not an internalization experiment, and this track is not its treatment, control,
estimand, metric, outcome, or interpretation. T04.5 neither registers EXP-0001 nor adds
another executable experiment.

## What Phase 1 may preserve

When directly supported by retained evidence, Phase 1 may capture:

- who or what selected a reasoning mode, which modes were available, and which was
  selected;
- policy identity/revision, confidence, override, fallback, and input references when
  explicitly available;
- resolved commands/configurations and raw artifacts supporting each normalized field;
- field-level observed/derived/inferred/unavailable provenance;
- explicit planning choices, structured futures, reasoning/action outputs, and model,
  prompt, generation, serving, tool, adapter, and parser identities when exposed.

The SiRA mapping is defined in
[`docs/harness/sira/H2K_REGULATION_DECISION_ADDENDUM.yaml`](harness/sira/H2K_REGULATION_DECISION_ADDENDUM.yaml).
The later SR²AM capture contract is
[`docs/audits/sr2am/H2K_TRACE_REQUIREMENTS_ADDENDUM.yaml`](audits/sr2am/H2K_TRACE_REQUIREMENTS_ADDENDUM.yaml).

## What Phase 1 may conclude

Phase 1 may report trace completeness, unavailable fields, reproducible raw-to-
normalized lineage, source classification, and whether a future matched comparison is
feasible, infeasible, or undetermined.

Phase 1 may not conclude that internalized regulation is superior, that an explicit
model output is causally faithful, that a learned kernel should be trained, that the
external harness can be removed, or that this deferred track is authorized for
execution.

## Roadmap boundary

This record adds no Phase 2 or other later phase. Any future implementation requires a
new approved package with an operational definition, matched controls, causal
interventions, data splits, safety/fallback rules, promotion and rollback ownership,
and explicit execution/training authority. The current package stops at evidence
preservation.
