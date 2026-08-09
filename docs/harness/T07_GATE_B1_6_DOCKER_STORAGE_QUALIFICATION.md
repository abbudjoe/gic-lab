# T07 Gate B1.6 Docker storage qualification

Status: **control plane implemented; selected topology not yet live-qualified; Gate
B2a installation blocked**

Observed: `2026-08-09T15:59:33Z`

## Decision

The selected topology remains exactly the user-selected topology: the M4 Mac mini is
the execution/control host, Docker Desktop.app and minimal first-party host support
would remain internal, one Docker Linux VM disk would be placed on the MacBook Pro
Data volume exported over Thunderbolt Target Disk Mode, live attempt evidence would
remain on the Mac mini, and only sealed nonsecret artifacts would be copied one-way
to the MacBook volume. No other host or storage topology was selected.

This turn qualifies the deterministic control plane, not the live topology. Docker is
absent and was not downloaded, installed, started, or probed. Multiple blockers
prevent installation authorization, including unavailable current artifact
reverification, an unresolved Mac mini operational floor, version-specific Docker
placement/reconnect evidence, mount-identity freshness, typed rollback, and the
authorized seal driver.

## Exact paths

| Role | Exact path | Volume/use |
|---|---|---|
| Dedicated external root | `/Volumes/Macintosh HD - Data/GIC-Lab` | New direct child of the approved mount. |
| Docker Linux disk-image directory | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-desktop/disk-image` | Candidate external Docker VM/image/layer/container/build-cache placement. |
| Docker/build staging | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-build-staging` | Future external build staging only; no build is part of B2a. |
| Sealed artifacts | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts` | Immutable, hash-verified, nonsecret copies only. |
| Active attempts | `/Users/joseph/.local/share/gic-lab/t07-gate-b2a/attempts` | Mac mini only; 67,108,864-byte aggregate cap. |
| B2a local work/evidence | `/Users/joseph/.local/share/gic-lab/t07-gate-b2a` | Mac mini; retained until independently verified. |

The three external roles are distinct. The MacBook volume is not a live attempt root,
and no live bidirectional synchronization is permitted. The external directories do
not exist yet; creation would be a future authorized B2a action after all guards pass.

## Two-volume floor policy

### External project/runtime volume

The APFS container capacity is 1,000,240,963,584 bytes. Its exact retained-free floor
is:

```text
max(150 * 1024^3, ceil(1,000,240,963,584 / 5))
= max(161,061,273,600, 200,048,192,717)
= 200,048,192,717 bytes
```

The proposed B2a external-growth ceiling is 12,884,901,888 bytes. Before an external
storage-producing action, the guard therefore requires 212,933,094,605 free bytes;
after it, and after every later disk creation, pull, build, probe, or archive copy, it
requires at least 200,048,192,717 free bytes and checks the applicable observed delta.
The latest read-only observation was 854,038,691,840 free bytes, which clears the raw
floor. It does not qualify Docker behavior.

### Mac mini system volume

An exact numeric floor is **not approved**. The exact required equation is:

```text
H_os + D_download_peak + A_app + S_support + U_update_rollback
     + E_active + F_failure + I_first_start_internal
```

Known terms are `D_download_peak = 573,592,444` bytes and the inherited bounded Gate
B1 evidence cap `E_active = 67,108,864` bytes. `H_os`, `A_app`, `S_support`,
`U_update_rollback`, `F_failure`, and `I_first_start_internal` have no retained
version-specific source or observation. The historical 12,884,901,888-byte combined
materialization cap included app, VM, images, build, and evidence across an obsolete
internal topology; it is not a measured host footprint and is not recycled as the
system floor.

Retained internal-free observations ranged from 9,522,626,560 to 12,029,374,464
bytes, and the read-only observation at `2026-08-09T15:59:33Z` was 29,444,337,664
bytes. That volatility reinforces the need for a source-backed headroom term; none of
those values clears an unresolved equation. B2a fails closed before download or start
until every term is exact and the current free-space observation meets the resulting
floor.

## Guard and placement contract

The storage module structurally matches the exact Data volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151` into `diskutil apfs list -plist`, requires its
unique container to have physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, and uses `CapacityFree` rather than the
misleading per-volume `FreeSpace=0`. It also requires the exact mount, writable and
unlocked APFS, `Internal=false`, `OSInternalMedia=false`, Thunderbolt/UTDM evidence,
and a device distinct from the Mac mini system volume. Reconnect-unstable `/dev/disk*`
numbers are evidence only.

Every exact path is lexically role-bound and traversed component-by-component with
descriptor-relative `O_NOFOLLOW`; missing roots, renamed mounts, symlinks, path
traversal, device mismatch, and internal fallback stop. Missing lock-state evidence
also stops. A fresh, typed, single-use, five-second guard capability must be consumed
immediately before every future Docker start/restart or materialization action. The
hashed plan places 24 guards directly before all 24 sensitive actions. The present
guard rechecks exact path/device roles but reuses its issuance-time volume
observation; it does not bind diskutil identity to a held mount descriptor and
freshly re-observe it at consumption. That TOCTOU gap blocks execution.

The stateful B2a supervisor refuses the current unauthorized/null-cap plan. For a
future resolved plan it enforces exact action order and call count, per-action and
aggregate monotonic deadlines, expected repository stdout, output/download/disk-delta
caps, both free-space floors, active-evidence bytes, adjacent guard consumption, zero
retry, and complete action accounting. It mints an in-memory, single-use
writer-closure capability only at the seal boundary. The standalone seal/copy CLI is
disabled; an authorized in-process driver and exact writer probe remain required.

Machine placement proof must combine a version-verified single setting-key extract,
a cropped location-only GUI image, exact VM-file device/inode/logical/allocated stat,
bounded directory usage, exact-file-filtered open-file evidence, selected Docker
version/info/context fields, the absence and inactivity of the version-verified
default internal VM path, and the same evidence across stop/restart/reconnect. Whole
preference files, Docker credentials, `~/.docker/config.json`, proxies, file-sharing
lists, account state, broad diagnostics, and the mutable VM-disk hash are excluded.

The locally suggested settings store and default `Docker.raw` paths are only
**candidates**, not authorization identities. Current official/version-specific
evidence must establish the real setting key/source and default path first.

## Reconnect and archival contract

The reconnect design requires clean stop, user eject/disconnect/reconnect,
machine requalification of both UUIDs and paths, engine restart only after the guard,
same external disk identity, same engine identity, healthy reopen, final clean stop,
and sealed evidence. Skips, replay, stale evidence, identity drift, or active default
internal storage block B2b. Current state-order tests do not yet prove stopped/open
file state, refresh the restart guard, or semantically bind version-specific Docker
outputs; those requirements remain blocked.

Attempt sealing rejects unsafe IDs, symlinks/special files, and byte overflow;
requires a supervisor-minted, single-use close capability with zero observed writers;
fsyncs files and directories; writes a deterministic size/SHA-256 manifest; removes
source write permissions; and applies filesystem user-immutable flags. Archival
requires a fresh typed, single-use placement proof for the exact
Mac mini source root and external sealed root, distinct devices, both stable volume
identities, floors, and no-symlink paths. It then uses a fresh external staging
identity, exclusive no-follow writes, destination size/hash verification, directory
fsync, same-volume atomic rename, final read-only modes, seal-hash comparison, and a
separate copy record written through held no-follow directory descriptors. Every
source payload and directory must remain immutable through the copy. The local source
is retained automatically; neither success nor failure deletes it. These are bounded
local-fixture results, not a live cross-volume qualification.

## `noowners` residual risk

The mount still has ownership disabled. One opaque Docker VM disk keeps guest Linux
ownership inside that disk, and nonsecret sealed artifacts derive integrity from the
manifest rather than host ownership. That makes the topology eligible for a bounded
nonsecret qualification probe, subject to successful B2a evidence. It does not make
the host mount a confidentiality or exclusive-ownership boundary. No real secret,
live attempt root, or mutable secret-bearing cache is approved there, and ownership
settings were not changed.

## Blockers

1. Current official metadata for Docker Desktop 4.85.0 build 235549 is not freshly
   verified; only the retained 2026-08-09 official observation exists.
2. Six required Mac mini system-floor terms remain unknown, so no numeric system floor
   or internal disk-growth authorization can be issued.
3. No retained official source proves a pre-first-start external disk binding. The GUI
   sequence may create a default internal VM disk before relocation; its behavior and
   maximum allocation are unknown.
4. Version-specific disk-location setting/key, default internal path, clean stop,
   automatic-update control, and reconnect semantics are not locally sourced.
5. The current blocked plan cannot be converted in place: all null system limits and
   the `unresolved` guard value require a freshly hashed, current-turn-authorized
   replacement wired through the supervisor.
6. The mount-identity race, version-specific placement/reconnect/stop semantic wiring,
   typed rollback executor, and authorized writer-probe/seal driver remain unresolved
   implementation blockers.

These blockers are represented in blocked-design plan
`PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1` at
`containers/sira-smoke/gate-b2a-install-storage-binding-plan.json`, SHA-256
`7ccd43e413ec8c4a21a4af043bef2477ede14b5bd40885c979cdeb7e48081eb1`.
The plan binds implementation commit
`321136b2a23158a7618e1489a4d2005d7f7ba1cd`, carries `authorized=false`, and must be
replaced rather than executed.

The historical combined materialization loader/executor and the Docker image/fixture
CLI paths reject stale B2/B2b execution authority. Their historical documents remain
provenance only.

No Docker, image, container, browser, provider, API, secret, SiRA, scientific, cloud,
or user-file cleanup action occurred.
