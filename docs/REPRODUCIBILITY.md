# Reproducibility Contract

## Unit of work

Every experiment has an immutable ID (`EXP-NNNN`), a protocol, a configuration, a registry entry, and a result summary. Changes after results are seen create a new protocol revision or experiment ID; they do not silently alter the original comparison.

## State model

Three fields are mandatory and independent:

- `lifecycle_status`: operational progress;
- `evidence_status`: strength/maturity of evidence;
- `outcome_status`: relationship between observed evidence and the registered hypothesis.

An invalid or interrupted run is not a negative scientific result. Deviations, exclusions, retries, and failed runs are logged before aggregate interpretation.

## Before execution

Record the question, falsifiable hypothesis, treatment and controls, fixed variables, data revision, metrics, estimand, sample/exclusion rules, random seeds, budget contract, stop criteria, environment/tool/model versions, and authorization. Label the analysis exploratory or confirmatory.

## During execution

Preserve raw observations, predicted transitions, decisions, actions, results, latency, tokens, tool calls, compute usage, software commit, model/dataset revisions, and artifact hashes. Do not overwrite raw evidence. Use UTC timestamps.

## After execution

Validate artifacts, produce a machine-readable result summary, report uncertainty and per-condition cost, reconcile deviations, and distinguish observed facts from interpretation. Publish negative or inconclusive results when the protocol remains valid.

## Reproduction levels

1. **Artifact execution:** released artifacts run under recorded versions.
2. **Directional reproduction:** the reported qualitative ordering appears under declared differences.
3. **Mechanism reproduction:** ablations and matched budgets attribute the effect to the proposed mechanism.
4. **Confirmatory replication:** preregistered comparison on held-out tasks survives declared statistical criteria.

Do not use “reproduced” without naming the level.

## Source and artifact identity

Primary sources are pinned in `manifests/sources.yaml`. Models, datasets, artifacts, and compute are recorded in their own manifests. Missing facts are explicit nulls, never inferred from filenames or prose.
