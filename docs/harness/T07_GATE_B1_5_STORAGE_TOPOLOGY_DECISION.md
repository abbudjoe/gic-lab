# T07 Gate B1.5 storage topology decision

Status: **blocked-user-action; sealed artifact retention approved, active runtime
storage unapproved**

Observed: `2026-08-09T11:43:56Z`

Baseline: `b8752765594de0b3486edfd9fad84d144b78b7b7` on
`phase-1/sira-smoke`.

## Decision

The MacBook Pro exports its storage to the Mac mini through **Thunderbolt Target Disk
Mode** (`service_target_disk_mode`, media name `Thunderbolt UTDM`). macOS presents
that remote-host block service as `/dev/disk6`, synthesizes APFS container
`/dev/disk7`, and locally mounts data volume `/dev/disk7s5`. It is therefore remote
MacBook Pro storage exposed as a locally mounted block device—not SMB, NFS, FUSE, or
another mounted network filesystem. Execution remains on the Mac mini; the MacBook
Pro is currently a storage-export host, not an approved execution host.

The volume is approved now only as the preferred destination for **sealed, immutable,
hashed artifact retention**. It is not approved as a live attempt root, build root,
Docker build-cache root, or Docker Desktop Linux disk-image location. Capacity alone
does not clear those uses.

## Exact topology and capability record

| Field | Observation | Decision |
|---|---|---|
| Mount path | `/Volumes/Macintosh HD - Data` | Current observation only; the artifact-retention root is `/Volumes/Macintosh HD - Data/Users/joseph/.local/share/gic-lab`. |
| Filesystem/mount type | APFS; mount flags `local,nodev,nosuid,journaled,noowners,nobrowse` | Local block filesystem, not a network share. |
| Device identity | current APFS volume `/dev/disk7s5`; synthesized APFS container `/dev/disk7`; current physical-store partition `/dev/disk6s2`; exported UTDM media `/dev/disk6` | Device numbers are reconnect-unstable observations, not authorization identities. `diskutil` reports UTDM media `VirtualOrPhysical: Unknown`; it must not be called a directly attached physical disk. |
| Stable storage identity | APFS data-volume UUID/group ID `8478609D-FA37-4ED5-875D-47AE912B9151`; physical-store partition UUID `7904A6F1-F483-4ED7-9E34-BFECAB31C63E`; APFS container UUID `CC7F87A9-2A2A-4431-AE90-9490FE3EA49F` | Record these separately. The data-volume and physical-store UUIDs are expected storage identities, but reconnect behavior was not tested. |
| Observed Target Disk Mode identity | target device name `Macintosh`; target domain UUID `BF7BE6D5-5B0B-335B-A606-92BB6ABF9D59`; service UUID `202358AC-4F4A-8E3D-DE75-B08FD85586F6`; connected host-bus domain UUID `C4C468F6-D5B4-4679-BD40-90FE051BA055` | Transport/session observations only. None is proven reconnect-stable or sufficient alone for authorization. |
| Read/write state | `Media Read-Only: No`, `Volume Read-Only: No`; read and write access succeeded | Suitable for bounded sealed-copy writes. |
| Capacity | APFS container total 1,000,240,963,584 bytes; free 854,038,691,840 bytes at the observation instant | Approximately 795.5 GiB free. Capacity is shared by the APFS container rather than reserved to this volume; it is sufficient for retention but does not prove runtime suitability. |
| Reconnect/remount stability | Storage UUIDs exist; `/etc/fstab` is absent; FileVault is enabled and currently unlocked; no Target Disk Mode disconnect, cable interruption, remote-Mac restart/sleep, unlock, or remount was performed | **Not positively established.** Availability depends on the separate MacBook Pro and UTDM session; the name-derived mount path can change or require unlock. Future code must resolve and verify storage UUIDs, UTDM service, mount path, device, and read/write state each time. |
| Unix permissions | A probe file accepted mode `000` and a same-user read failed with `EACCES`; reported UID:GID was `501:20`. The mount nevertheless reports `noowners` and `Owners: Disabled`. | Mode bits work in the observed session, but durable Unix ownership semantics are unavailable and cannot satisfy the existing strict attempt-root ownership contract without redesign. Permissions are not an adequate sealed-artifact confidentiality boundary. |
| Sparse files | 1,073,741,824 logical bytes used 16,384 allocated bytes | Sparse-file support positively observed. |
| Atomic rename | Same-directory `os.replace` removed the source, preserved the inode, and produced exact destination bytes | Ordinary same-volume rename behavior positively observed; concurrent-reader and crash/power-loss atomicity were not empirically tested. |
| `fsync`/durability | File `fsync`, macOS `F_FULLFSYNC`, and directory `fsync` all succeeded; the 31-byte probe SHA-256 was `7c5d0d80006b0b50c9e6f798fbf80406fcb1b8419f546e576442c80649577845` | Required primitives exist. SMART status is unavailable and no power-loss test was authorized, so durability still requires seal, full sync, destination re-read, SHA-256 verification, and a retained copy ledger. |
| Symlinks/path escape | Symlinks are supported; a probe link inside the volume resolved to `/private/tmp` outside it | Positive escape risk. Future writers must reject symlink components, resolve canonically, and recheck the resolved device/UUID before opening or finalizing files. |
| Active attempt writes | Direct host writes work, but the remote Mac/UTDM availability dependency, reconnect stability, ownership semantics, path-escape enforcement, Docker bind behavior, and the harness's volume-identity check are incomplete | **Unapproved.** Treat as sealed-retention-only. |
| Docker Desktop Linux disk image | Docker Desktop and every other inspected OCI/VM runtime are absent; no install, launch, disk relocation, or runtime probe was performed. The apparent local block path still depends on a separate MacBook Pro and UTDM session. | **Unknown and unapproved.** No Docker disk-image, build-cache, or image-store root is issued. |
| Sealed artifact retention | APFS locally mounted over UTDM, read/write access, sparse files, rename, `fsync`, `F_FULLFSYNC`, directory `fsync`, FileVault, stable storage UUIDs, and user approval are present | **Approved conditionally** for immutable bundles under the sealing contract below. |

The temporary capability directory was fresh, confined beneath
`/Volumes/Macintosh HD - Data/Users/joseph/.local`, and automatically removed. A
post-probe search found no matching probe directory.

## Sealed-retention contract

1. Resolve data-volume UUID `8478609D-FA37-4ED5-875D-47AE912B9151` and physical-store
   partition UUID `7904A6F1-F483-4ED7-9E34-BFECAB31C63E`; prove the expected UTDM
   service exposes them as the mounted, read-write volume at the expected mount point.
2. Reject every symlink or non-directory component in the destination ancestry and
   prove the resolved destination remains on the verified volume.
3. Write only a fresh staging bundle; never mutate a previously sealed bundle.
4. Include artifact identity, source attempt, byte size, SHA-256, provenance, and an
   explicit completeness manifest.
5. Sync files and directories, atomically rename the staging bundle to its immutable
   final name on the same volume, re-read the destination, and verify every SHA-256.
6. Retain a copy/verification record containing source and destination identities,
   sizes, hashes, timestamps, and verification outcome.
7. Treat Unix ownership as non-authoritative on this `noowners` mount. Do not retain a
   secret merely because mode bits appear restrictive.
8. Never use live bidirectional synchronization for mutable attempt state.

If the storage is later network-backed, active attempts must remain on the selected
execution host; only sealed evidence may be copied here, with destination SHA-256
verification and retained copy records. Docker's VM disk must not be placed on a
network filesystem.

## Runtime-storage result

No suitable Docker runtime volume is positively established on the Mac mini. The
internal startup disk has only 9,522,626,560 free bytes at the current inspection and
is not an allowed fallback. Although Target Disk Mode exposes the MacBook Pro storage
through a local block-device interface with adequate raw capacity, runtime availability
would depend on the separate Mac, cable, UTDM session, and unlock state. Docker-specific
relocation, persistence, sparse-disk behavior, sharing, cleanup, and post-reconnect
identity have not been proven, and Docker is not installed.

Therefore no exact Docker disk-image, build-staging, live-attempt, or active archive
root is proposed, and no Gate B2a/B2b executable plan or SHA-256 is issued.

## Unselected alternatives

The following are presented without preference or automatic selection:

a. Execute Docker and T07 on the MacBook Pro under a newly reviewed host topology.
b. Use a locally attached external SSD on the Mac mini.
c. Move the contained execution to a separately approved Linux host.

Each alternative requires a new current-turn decision and a topology-specific review.
Only after one is selected may the control plane implement stable storage identity,
prohibit internal-disk fallback, propose exact roots, and regenerate Gate B2a and B2b
plans and hashes.

## Superseded authority

Historical plan `PLAN-T07-GATE-B2-MATERIALIZATION`, SHA-256
`10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`, and its Gate B2
authorization block remain superseded and must not be executed. Gate B2a, Gate B2b,
and live T07 remain unauthorized.

No download, install, pull, build, runtime/container launch, browser activity, API
request, SiRA condition, or scientific-field mutation occurred during Gate B1.5.
