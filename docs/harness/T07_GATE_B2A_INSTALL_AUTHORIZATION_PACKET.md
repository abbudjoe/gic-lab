# T07 Gate B2a install authorization packet

Status: **blocked; no installation authorization or executable plan issued**

Prepared: 2026-08-09

## Scope

Gate B2a would qualify one selected execution/runtime storage topology, install the
approved runtime if separately authorized, bind its VM/image/build storage, and
materialize an immutable image identity. This packet authorizes none of those actions.

## Gate B1.5 input

The MacBook Pro exports storage through Thunderbolt Target Disk Mode as UTDM media,
which the Mac mini presents as a locally mounted APFS block volume at
`/Volumes/Macintosh HD - Data`. The APFS data-volume UUID is
`8478609D-FA37-4ED5-875D-47AE912B9151`; the physical-store partition UUID is
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`. It is approved for sealed artifact retention
only. Docker VM/image, build-staging, and live-attempt suitability are unproven.

No Docker, Podman, Colima, Lima, nerdctl, Finch, Docker Desktop, Podman Desktop,
OrbStack, or Rancher Desktop runtime/application was found. No runtime was installed
or launched.

## Storage roots and identities

| Purpose | Gate B2a value |
|---|---|
| Preferred sealed-retention root | `/Volumes/Macintosh HD - Data/Users/joseph/.local/share/gic-lab` |
| Stable retention-volume identity | APFS UUID `8478609D-FA37-4ED5-875D-47AE912B9151` |
| Docker Linux disk-image root | not issued |
| Docker image/build-cache root | not issued |
| Build-staging root | not issued |
| Live attempt root | not issued |
| Active evidence root | not issued |

The internal startup disk is prohibited as an implicit fallback. A missing selected
runtime volume must stop rather than redirecting state under `/Users/joseph`,
`/Applications`, `/var`, or a runtime default data root. Installing an application in
`/Applications` would not authorize its VM/image data to remain internally.

## Plan identity

- Gate B2a plan ID: **not issued**.
- Gate B2a plan path: **not issued**.
- Gate B2a plan SHA-256: **not issued**.
- Installation command: **not rendered**.
- Download/pull/build commands: **not rendered**.

Historical plan `PLAN-T07-GATE-B2-MATERIALIZATION`, SHA-256
`10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`, remains
superseded and cannot satisfy Gate B2a.

## Required evidence before a replacement packet

1. The user selects exactly one execution/storage alternative.
2. The selected topology's active/runtime suitability is positively established for
   stable host and volume identities, read/write state, adequate space, reconnect
   behavior, permission semantics, sparse-file support, rename and sync behavior, and
   path-escape controls. Any applicable unknown, untested, or insufficient field blocks
   plan issuance; merely recording it does not satisfy this gate.
3. For Docker Desktop, a source-grounded, version-specific disk-image relocation
   procedure is rendered and a later authorized probe proves the VM disk and image
   data actually reside on the selected local disk-like volume after restart.
4. The control plane rejects absent/wrong volume identity, symlink ancestry,
   cross-device finalization, runtime-default internal storage, and internal-disk
   fallback before any download, pull, or build.
5. Exact Docker disk-image, build-staging, active-attempt, evidence, sealed-archive,
   download, and cleanup roots are rendered.
6. Exact immutable runtime installer, base image, dependencies, endpoints, transfer,
   disk, CPU, memory, PID, wall, call, and output caps are freshly verified.
7. A new plan and SHA-256 pass mock/fake tests, repository validation, full checks, and
   independent spec-conformance review.
8. A new current-turn authorization names that exact plan and its cleanup contract.

## Unselected alternatives

a. Execute Docker and T07 on the MacBook Pro under a newly reviewed host topology.
b. Use a locally attached external SSD on the Mac mini.
c. Move the contained execution to a separately approved Linux host.

No alternative is selected or preferred by this packet.

## Authorization decision

There is no ready-to-copy Gate B2a authorization block. Do not download, install,
pull, build, launch, browse, call an API, access a secret, or materialize execution
authorization. Stop for the user's topology selection.
