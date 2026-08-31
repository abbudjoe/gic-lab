# Compute Policy

## Phase 0 budget

Authorized paid compute: **USD 0**. Authorized GPU hours: **0**. Phase 0 uses CPU-safe local validation and documentation builds only.

## Mutation boundary

Inspecting public metadata or existing cloud status/logs is read-only. Launching, stopping, deleting, resizing, restarting, or otherwise mutating cloud jobs or paid compute requires explicit authorization for that specific action in the current user turn. Repository plans and historical budget discussions are not authorization.

## Required preflight for later compute

Before a paid run, its protocol and compute record must declare provider, hardware, region, expected wall time/GPU hours, spend cap, storage/network assumptions, data locations, checkpoints, stop conditions, evidence capture, and cleanup. Hardware must match the runner. Credentials must remain outside Git and logs.

Before a qualified dotenv read, authenticated metadata request, provider mutation,
or paid compute, the exact package must have valid registry-completeness,
offline-composition, state-capsule, and required Category 3 shadow receipts. The
future authorization overlay and frozen run manifest must both bind the receipt set
defined by `schemas/t09-control-receipt-bindings.schema.json`. Those receipts prove
preparation only and never grant current-turn authority.

A deterministic blocker discovered after authenticated metadata access is a control
failure and must become an incident with an offline composition or shadow regression.
It must not be converted into scientific evidence or silently retried.

## Accounting

Every allocation and run is recorded in `manifests/compute.yaml`, including aborted or idle allocations. Report both accelerator-hours and wall-clock time; GPU-hours from different hardware are not assumed fungible. External API cost is tracked separately from GPU compute.

## Bounded T07 external authorization overlay

The bounded T07 plan remains unauthorized in Git: the project permission booleans stay
false, its plan identity says `authorized: false`, and `CMP-0001` is only `planned`.
A future current-turn user authorization may be converted by the reviewed local
supervisor into one fresh, mode-0600, Git-ignored authorization overlay. That overlay
must bind the exact clean execution commit, plan SHA-256, limits SHA-256, private
resource-binding SHA-256, run identities, price table, allowed actions, and one exact
3,600-second supervised window. The overlay is a single-run capability, not a change
to repository authority. A missing, expired, reused, or mismatched overlay leaves all
repository permissions false and stops before a provider request or execution action.

For this profile, cloud mutations are manual user-console actions only. The local
observer is limited to the plan's 13 GET requests. The remote bootstrap cannot mutate
Lambda resources. On completion or failure, the user must terminate the exact bound
instance; read-only terminal evidence is required before regional-rule deletion, and
read-only security evidence is required after restoring the global baseline.

Every bounded-smoke remote archive must contain a machine-readable `compute-use.json`
derived from the supervised wall timestamps and retained provider-usage receipts. It
records accelerator and wall time, the list-price upper bound, observed API cost,
whether those values remain within the bound caps, and an explicit `null` actual
provider invoice until billing is reconciled. After the archive is locally verified,
the planned `CMP-0001` entry in `manifests/compute.yaml` must be reconciled in a
separate repository closeout commit before any interpretation or successor execution.
The runtime record supplements that repository ledger; it does not authorize compute
or silently convert a planned allocation to an actual one.

## Historical estimate boundary

The attached conversation discussed a provisional 200–400 H100-equivalent GPU-hour and roughly USD 2,500 first-phase envelope, with about USD 4,000 in Lambda credits available. These are planning estimates, not verified prices, approved protocol budgets, or spending authorization.
