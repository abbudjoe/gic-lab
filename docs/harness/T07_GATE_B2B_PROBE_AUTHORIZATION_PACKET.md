# T07 Gate B2b probe authorization packet

Status: **blocked on Gate B2a; no probe authorization or executable plan issued**

Prepared: 2026-08-09

## Scope

Gate B2b would run only the adversarial descendant-containment fixture, local
browser-only preflight, and dummy-secret non-leakage fixture against a verified Gate
B2a image/runtime boundary. It would not run either SiRA condition or make a model API
request. This packet authorizes no probe.

## Unsatisfied prerequisites

- No execution host/storage alternative has been selected.
- No Docker/OCI runtime is installed or verified.
- No Docker VM/image storage root is approved.
- No live attempt or active evidence root is approved.
- No immutable built image ID or complete image provenance exists.
- No Gate B2a cleanup evidence exists.
- The current containment code does not verify the newly required storage-volume
  identity for an active attempt root.

The MacBook Pro's Target Disk Mode APFS volume is currently approved only for sealed
artifact retention at
`/Volumes/Macintosh HD - Data/Users/joseph/.local/share/gic-lab`, data-volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151` and physical-store partition UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`. That approval does not make it a live attempt
root or Docker disk location.

## Plan and attempt identities

- Gate B2b plan ID: **not issued**.
- Gate B2b plan path: **not issued**.
- Gate B2b plan SHA-256: **not issued**.
- Container image ID: **unknown; not built**.
- Containment attempt identity: **not issued**.
- Browser-preflight attempt identity: **not issued**.
- Dummy-secret attempt identity: **not issued**.
- Probe commands: **not rendered**.

Historical plan `PLAN-T07-GATE-B2-MATERIALIZATION`, SHA-256
`10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`, and its three
historical UUIDs remain superseded and confer no authority.

## Evidence and retention contract for a future B2b

1. Attempts write only to a topology-specific active root on the selected execution
   host or positively qualified local disk-like volume.
2. Every attempt remains container-ID bounded under the existing private PID/cgroup
   lifecycle and exact resource limits, subject to fresh plan review.
3. Evidence is fully captured, hashed, and sealed before any archival copy.
4. Sealed bundles are copied to the preferred durable destination only after source
   sealing; every destination file is re-read and SHA-256 verified.
5. Copy records retain source/destination identities, byte sizes, hashes, timestamps,
   and verification outcome.
6. If the destination is network-backed in a future topology, Docker's VM disk and
   live attempt roots remain off it, and live bidirectional synchronization is
   prohibited.
7. Cleanup proves no attempt container or owned auxiliary resource remains before the
   sealed bundle is declared complete.

## Required evidence before a replacement packet

Gate B2a must complete under a newly selected and authorized topology. A replacement
Gate B2b plan must then bind exact runtime/image/storage identities, fresh attempt
UUIDs, commands, aggregate and per-probe limits, secret-canary handling, sealed-copy
verification, cleanup, and stop conditions. It must pass mock/fake tests, full
repository checks, and independent spec-conformance review before a new current-turn
authorization is requested.

## Authorization decision

There is no ready-to-copy Gate B2b authorization block. Gate B2b, both SiRA
conditions, the experimental browser workflow, and live T07 remain unauthorized. Do
not launch a runtime/container/browser, access a secret, or call any API.
