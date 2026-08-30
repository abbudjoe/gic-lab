# T09 V14 cleanup-repair runtime profile

Every V14 identity consumer resolves exactly one retained provider contract by
`provider_contract("V14")` or
`provider_contract_for_plan_id("PLAN-EXP0001-PILOT-V14")`. There is no
active/current/latest/default selector. Qualifier, provider, host, evaluator, cleanup,
staging, and evidence paths preserve that exact selection and reject cross-version
mixtures. Both task-pair command manifests include the equal explicit selector
`--provider-contract V14`.

Cleanup export reconciliation is evidence-derived, not caller-selected:

- `prefreeze-zero-attempt` requires an exact supported contract and plan, a terminal
  early-cleanup journal with no empirical entry, no published manifest or publication
  receipt, no condition reservation or intent, no attempt state or archive, no
  post-freeze receipt, and empty retained export chronology. Cleanup does not load a
  manifest, requires zero acknowledgements, and emits one terminal handoff receipt.
- `postfreeze-zero-attempt` requires a valid published manifest and matching
  publication/post-freeze evidence, while requiring zero attempt acknowledgements.
- `empirical-prefix` requires the valid frozen manifest plus every exact contiguous
  export acknowledgement for the consumed prefix.

Contradictory identity, publication, manifest, attempt, or chronology evidence fails
closed. A missing, malformed, partial, replaced, symlink, or nonregular mandatory
manifest is never suppressed. Repeated cleanup validates and reuses the existing exact
terminal receipt and journal binding; it does not rewrite immutable evidence or repeat
resource mutations after the terminal projection.

V14 preserves one local metadata GET, zero provider GETs, zero host GETs, final
transport-boundary freshness through 1,800.0 seconds, no host current-time expiry,
mixed-dotenv selection, zero retries, delayed cidfile handling, process-wide core
suppression, exact provider accounting, durable early cleanup, exact-resource cleanup,
and offline host receipt validation. This Category 1 task performs no live operation.
