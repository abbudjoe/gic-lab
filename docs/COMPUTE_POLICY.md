# Compute Policy

## Phase 0 budget

Authorized paid compute: **USD 0**. Authorized GPU hours: **0**. Phase 0 uses CPU-safe local validation and documentation builds only.

## Mutation boundary

Inspecting public metadata or existing cloud status/logs is read-only. Launching, stopping, deleting, resizing, restarting, or otherwise mutating cloud jobs or paid compute requires explicit authorization for that specific action in the current user turn. Repository plans and historical budget discussions are not authorization.

## Required preflight for later compute

Before a paid run, its protocol and compute record must declare provider, hardware, region, expected wall time/GPU hours, spend cap, storage/network assumptions, data locations, checkpoints, stop conditions, evidence capture, and cleanup. Hardware must match the runner. Credentials must remain outside Git and logs.

## Accounting

Every allocation and run is recorded in `manifests/compute.yaml`, including aborted or idle allocations. Report both accelerator-hours and wall-clock time; GPU-hours from different hardware are not assumed fungible. External API cost is tracked separately from GPU compute.

## Historical estimate boundary

The attached conversation discussed a provisional 200–400 H100-equivalent GPU-hour and roughly USD 2,500 first-phase envelope, with about USD 4,000 in Lambda credits available. These are planning estimates, not verified prices, approved protocol budgets, or spending authorization.
