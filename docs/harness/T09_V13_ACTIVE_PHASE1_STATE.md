# T09 V13 active Phase 1 state

V12 stopped before empirical entry after one Lambda launch. Its authorization,
metadata allowance, overlay, host, image-qualification, and run-manifest identities
are consumed; cleanup is verified. The sanitized stopped disposition is retained in
`experiments/EXP-0001-sira-simulative-vs-reactive/T09_V12_STOPPED_DISPOSITION.json`.

V13 is the sole fresh T09 successor proposal. The repair replaces implicit V11 pilot
constants in the shared active qualifier path with exact provider-version or plan-ID
selection. It does not change the scientific contract.

- Plan: `PLAN-EXP0001-PILOT-V13`
- Host: `RUN-T09-PILOT-HOST-AUTONOMOUS-0006`
- Image qualification: `QUAL-T09-PILOT-V13-IMAGE-AUTONOMOUS-0006`
- Local finalizer qualification:
  `QUAL-T09-PILOT-V13-LOCAL-FINALIZER-AUTONOMOUS-0006`
- Frozen manifest: `RUN-MANIFEST-EXP0001-PILOT-V13-AUTONOMOUS-0006`

All V13 state flags are false: `authorized`, `execution_allowed`,
`cloud_mutation_allowed`, `paid_compute_allowed`, `live_qualification_performed`,
`pilot_executed`, and `empirical_run_roots_materialized`. No V13 run root exists.

Category 3 is not authorized. Exact-head ChatGPT review and a separate merge-only
turn are required before any fresh Category 3 authorization can be considered.
