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
