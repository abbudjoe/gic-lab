# T09 V12 active Phase 1 state

V12 is the sole fresh T09 successor proposal. It is implemented for local
review but remains unauthorized, unmerged, unexecuted, and outside Category 3.

- Plan: `PLAN-EXP0001-PILOT-V12`
- Host: `RUN-T09-PILOT-HOST-AUTONOMOUS-0005`
- Attempts, in frozen order:
  `RUN-T09-TASK-A-REACTIVE-AUTONOMOUS-0005`,
  `RUN-T09-TASK-A-SIMULATIVE-AUTONOMOUS-0005`,
  `RUN-T09-TASK-B-SIMULATIVE-AUTONOMOUS-0005`, and
  `RUN-T09-TASK-B-REACTIVE-AUTONOMOUS-0005`
- Image qualification: `QUAL-T09-PILOT-V12-IMAGE-AUTONOMOUS-0005`
- Frozen manifest: `RUN-MANIFEST-EXP0001-PILOT-V12-AUTONOMOUS-0005`

All state flags are false: `authorized`, `execution_allowed`,
`cloud_mutation_allowed`, `paid_compute_allowed`,
`live_qualification_performed`, `pilot_executed`, and
`empirical_run_roots_materialized`. No V12 run root exists.

The exact metadata contract is one local control-plane GET before Lambda
launch, zero provider and host metadata requests, a required nonreplayable
receipt, a 1,800-second inclusive provider-final-transport freshness window,
durable host ordering validation without current freshness, and
`stop-before-lambda-launch-zero-lambda-cost` when the immutable model is
unavailable.

The next permitted action is exact-head ChatGPT review of the draft V12 PR.
Only a separately authorized Category 2 turn may merge it. Category 3, live
metadata, Lambda launch, Docker/browser/SiRA/FanOutQA/evaluator work, pilot
execution, and scientific interpretation remain prohibited.
