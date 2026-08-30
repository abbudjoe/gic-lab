# T09 V14 active Phase 1 state

V13 stopped before empirical entry after one preflight host. No dynamic frozen
manifest was published, no condition entered, and no raw or completed attempt exists.
Its authorization, metadata allowance, overlay, host, image qualification, local
finalizer qualification, frozen-manifest identity, and condition identities are
consumed. Provider termination, zero running T09 instances, and restored security are
verified. The sanitized immutable record is
`experiments/EXP-0001-sira-simulative-vs-reactive/T09_V13_STOPPED_DISPOSITION.json`.

The defect was lifecycle-specific: pre-freeze zero-attempt cleanup was incorrectly
sent through post-freeze empirical export reconciliation. V14 derives one typed phase
from durable evidence: `prefreeze-zero-attempt`, `postfreeze-zero-attempt`, or
`empirical-prefix`. Only the exact all-zero pre-freeze state admits an absent manifest;
published freeze and empirical prefixes retain strict manifest, chronology, and export
acknowledgement checks. The terminal export handoff validates and reuses an existing
exact receipt on resume.

V14 is the sole fresh successor proposal and preserves the explicit provider-contract
architecture:

- Plan: `PLAN-EXP0001-PILOT-V14`
- Host: `RUN-T09-PILOT-HOST-AUTONOMOUS-0007`
- Image qualification: `QUAL-T09-PILOT-V14-IMAGE-AUTONOMOUS-0007`
- Local finalizer qualification:
  `QUAL-T09-PILOT-V14-LOCAL-FINALIZER-AUTONOMOUS-0007`
- Frozen manifest: `RUN-MANIFEST-EXP0001-PILOT-V14-AUTONOMOUS-0007`
- Authorization prefix: `AUTH-T09-V14-`

All V14 flags are false: `authorized`, `execution_allowed`,
`cloud_mutation_allowed`, `paid_compute_allowed`, `live_qualification_performed`,
`pilot_executed`, and `empirical_run_roots_materialized`. No V14 run root exists.
Science is unchanged. Category 3 is unauthorized; exact-head PR review, merge, and a
fresh later authorization remain separate.
