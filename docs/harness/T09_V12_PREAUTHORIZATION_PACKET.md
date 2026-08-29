# T09 V12 preauthorization packet

This packet is a Category 1 implementation handoff. It is not a Category 3
authorization and does not permit cloud or scientific execution.

```text
implementation complete
local tests complete
PR review required
merge required
live metadata request not performed in Category 1
Lambda not launched
pilot not executed
authorization false
```

V12 is deliberately unauthorized:

- `PLAN-EXP0001-PILOT-V12`
- host `RUN-T09-PILOT-HOST-AUTONOMOUS-0005`
- four fresh attempt IDs ending in `AUTONOMOUS-0005`
- image qualification `QUAL-T09-PILOT-V12-IMAGE-AUTONOMOUS-0005`
- frozen manifest `RUN-MANIFEST-EXP0001-PILOT-V12-AUTONOMOUS-0005`

The package retains the scientific model, evaluator, dataset, task hashes,
pair order, retry count, and descriptive-calibration interpretation. A future
Category 3 authorization must bind the exact reviewed merged commit and final
plan hash before any request or mutation.

Receipt timing ownership is explicit: provider launch enforces the 1,800-second
prelaunch freshness window at the launch-send boundary; host validation is
durable and offline, disables current-time receipt expiry, and still requires
response completion and receipt creation before provider launch. The contract
therefore remains one total metadata GET, provider request count zero, and host
request count zero. This packet is not Category 3 approval.
