# Storage Policy

## Phase 0

Git stores source, protocols, small summaries, plots, manifests, and hashes. It does not store model weights, optimizer states, bulk datasets, full traces, screenshots, videos, or browser archives. Ignored paths are defined in `.gitignore` and enforced by repository validation.

## Artifact contract

Every external artifact record includes identity, experiment, format, byte size, SHA-256, version/revision/commit, license, provenance, storage URI, public-access flag, creator commit, and verification status. A missing artifact or hash stays unknown; a filename is not provenance.

## Preferred durable artifact volume

All new sealed, durable non-Git T07 artifacts must be retained beneath the attached
MacBook Pro data volume at
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts`. This is a new dedicated
top-level project hierarchy; the B1.5 historical candidate beneath
`/Volumes/Macintosh HD - Data/Users/joseph/.local/share/gic-lab` is superseded before
any artifact write. This approval covers
immutable, hashed artifact bundles and their copy/verification records. It does not by
itself approve the volume for mutable attempt roots, build staging, Docker VM/image
data, or build cache.

The authoritative retention identity is APFS volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`. Before any sealed-copy or retention action
targeting this root, the control plane must prove that this exact exported volume is
mounted read-write at the expected mount point and that the resolved retention root
remains on it. A missing, renamed, read-only, or identity-mismatched destination stops
the copy/retention action. A path string or symlink alone is not proof of storage
placement. Future active-use preflights are topology-specific and are not supplied by
this retention contract.

Gate B1.5 classifies the current exposure as the MacBook Pro's storage exported over
Thunderbolt Target Disk Mode and mounted by the Mac mini as an APFS block device. It
is not SMB/NFS, but it depends on a separate Mac, cable, Target Disk Mode session, and
FileVault unlock. Active-attempt and Docker-disk suitability remain unproven. Until a
reviewed plan positively establishes stronger suitability, the volume is approved for
sealed artifact retention only. Mutable attempt state must not be placed there by
default, and no Docker VM disk location is approved. There is no automatic fallback
to the internal startup disk or another volume.

Gate B1.6 evaluates, but does not yet approve, Docker runtime storage at
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-desktop/disk-image` and build staging
at `/Volumes/Macintosh HD - Data/GIC-Lab/t07/docker-build-staging`. A later authorized
qualification must prove version-specific placement, default-internal inactivity,
clean stop, disconnect/reconnect, same-disk healthy reopen, and final stop. Missing or
mismatched storage stops; it never redirects to the internal startup disk.

Gate B1.7 terminates local-runtime selection by rejecting Colima/Lima state beneath
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home`. Lima necessarily creates a
private SSH identity under `LIMA_HOME/_config/user`; the reviewed external mount has
ownership disabled and is not approved for mutable secret-bearing state. The Colima
VM/runtime and build roots remain unapproved and must not be created. The exact
candidate paths are provenance, not storage authority. A next topology requires the
user to select a directly attached Mac mini SSD, a separately approved Linux host, or
a deliberately weaker governance contract; there is no internal-disk fallback.

D-020 selects a separately gated ephemeral Lambda host at design level. Lambda
persistent filesystems remain forbidden. Mutable qualification/workload state stays
on the minted provider instance and is destroyed with that instance; Docker images,
layers, and runtime state are never copied to the Mac mini or retained volume. The Mac
mini may hold only a per-run, Git-ignored active evidence root capped at 67,108,864
bytes. Its prewrite floor is 8,725,200,896 bytes: 8 GiB of explicit host-operational
headroom plus a 135,266,304-byte peak increment consisting of one 64 MiB active copy,
one 64 MiB seal/verification copy, and 1 MiB of bounded metadata. After sealing, at
least 8,589,934,592 bytes must remain free. A fresh preflight and post-seal check are
mandatory; there is no fallback location.

The sealed bundle is copied one-way to the preferred MacBook Pro archive only after a
fresh identity/held-descriptor guard. For the freshly observed APFS container
capacity, the retained-free floor is recalculated as
`max(150 GiB, ceil(container_capacity_bytes / 5))`; the pre-copy requirement adds the
67,108,864-byte maximum archive copy. Destination SHA-256, fsync, atomic finalization,
and a post-copy retained-floor check are mandatory. The Mac mini source remains until
independent archive verification.

Gate L1 V2 inventory uses a smaller dedicated retention contract. Before any account
GET, the Mac mini must retain at least 8,591,048,704 bytes free: 8 GiB operational
headroom plus a conservative 1,114,112-byte local write/finalization increment. That
increment covers the 851,968-byte successful local evidence set (524,288-byte
redacted artifact, 262,144-byte durable request ledger, and 65,536-byte verification
record) plus a 262,144-byte transient ledger-capacity reservation. At least
8,589,934,592 bytes must remain after local sealing. A separate failed-preflight
disposition is capped at 16,384 bytes. The external four-file bundle is capped at
1,048,576 bytes, and aggregate retained evidence including the disposition is capped
at 1,916,928 bytes. The external pre-copy floor is freshly recomputed as
`max(150 GiB, ceil(container_capacity_bytes / 5)) + 1,048,576`; the post-copy floor
removes only that increment. Success requires held-descriptor identity, no internal
fallback, source/destination hash equality, fsync, atomic finalization, source
retention, and a post-copy volume/floor check. A complete schema-valid ledger is one
of the four sealed files; an unarchived or incomplete-ledger Gate L1 inventory cannot
authorize or bind Gate L2. The earlier V1 two-local-file/three-file-bundle figures are
historical only and do not authorize another V1 attempt.

If the destination is later exposed through a network filesystem, attempts must be
written on the approved execution host, sealed and hashed there, copied to this
destination, verified by destination SHA-256, and recorded in a copy ledger. Live
bidirectional synchronization of mutable attempt state is prohibited.

Repository source, protocols, manifests, small summaries, and hashes remain in Git;
they are control-plane records rather than external artifacts.

## Local retention

At `2026-08-09T11:43:56Z`, the preferred 1,000,240,963,584-byte APFS container
reported 854,038,691,840 free bytes. This observation is not a durable capacity
guarantee and is shared across the APFS container rather than reserved to the data
volume. Keep active models, at most the latest and previous resumable checkpoint,
best/final model-only exports, adapters, and recent traces. Maintain at least 150 GiB
or 20% of the preferred container capacity free, whichever is greater, and
recompute the exact floor before each sealed copy. Any future active-use plan must
define and enforce its own topology-specific preflight and retained-free-space floor.

## Upgrade triggers

Reassess storage before regular full-parameter 8B training, a separate trainable world model, any 30B checkpoint, more than two resumable branches, or when cleanup begins influencing experimental choices. Cloud scratch is not a durable backup.

## Backup

Verify remote copies by checksum before deleting local evidence. Backup capacity does not count as working capacity, and live bidirectional syncing of mutable experiment databases is prohibited without a separate consistency design.
