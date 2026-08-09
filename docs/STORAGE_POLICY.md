# Storage Policy

## Phase 0

Git stores source, protocols, small summaries, plots, manifests, and hashes. It does not store model weights, optimizer states, bulk datasets, full traces, screenshots, videos, or browser archives. Ignored paths are defined in `.gitignore` and enforced by repository validation.

## Artifact contract

Every external artifact record includes identity, experiment, format, byte size, SHA-256, version/revision/commit, license, provenance, storage URI, public-access flag, creator commit, and verification status. A missing artifact or hash stays unknown; a filename is not provenance.

## Authoritative local artifact volume

All non-Git project artifacts must be stored beneath the attached MacBook Pro data
volume at
`/Volumes/Macintosh HD - Data/Users/joseph/.local/share/gic-lab`. This includes
downloads, external source checkouts, dependency wheels, build contexts, Docker VM
and image data, build cache, attempt roots, logs, traces, screenshots, browser
archives, datasets, checkpoints, and generated evidence. There is no fallback to the
internal startup disk or another volume.

The authoritative storage identity is APFS volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`. Before any artifact-producing action, the
control plane must prove that this exact external volume is mounted read-write at the
expected mount point and that the resolved artifact root remains on it. A missing,
renamed, read-only, or identity-mismatched volume stops execution. A path string or
symlink alone is not proof of storage placement.

The Docker Desktop application may be installed in `/Applications`, but its Linux VM
disk, image layers, build cache, and every GIC Lab build/run artifact must reside on
the authoritative external volume. A future installation plan must bind and verify
Docker's disk-image location before any image pull or build.

Repository source, protocols, manifests, small summaries, and hashes remain in Git;
they are control-plane records rather than external artifacts.

## Local retention

At `2026-08-09T11:27:04Z`, the authoritative 1,000,240,963,584-byte APFS container
reported 854,038,687,744 free bytes. This observation is not a durable capacity
guarantee. Keep active models, at most the latest and previous resumable checkpoint,
best/final model-only exports, adapters, and recent traces. Maintain at least 150 GiB
or 20% of the authoritative container capacity free, whichever is greater, and
recompute the exact floor before each materialization or run.

## Upgrade triggers

Reassess storage before regular full-parameter 8B training, a separate trainable world model, any 30B checkpoint, more than two resumable branches, or when cleanup begins influencing experimental choices. Cloud scratch is not a durable backup.

## Backup

Verify remote copies by checksum before deleting local evidence. Backup capacity does not count as working capacity, and live bidirectional syncing of mutable experiment databases is prohibited without a separate consistency design.
