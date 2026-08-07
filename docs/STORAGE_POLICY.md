# Storage Policy

## Phase 0

Git stores source, protocols, small summaries, plots, manifests, and hashes. It does not store model weights, optimizer states, bulk datasets, full traces, screenshots, videos, or browser archives. Ignored paths are defined in `.gitignore` and enforced by repository validation.

## Artifact contract

Every external artifact record includes identity, experiment, format, byte size, SHA-256, version/revision/commit, license, provenance, storage URI, public-access flag, creator commit, and verification status. A missing artifact or hash stays unknown; a filename is not provenance.

## Local retention

The historical plan estimates about 750 GB of available local project storage. Treat that as an unverified capacity assumption. Keep active models, at most the latest and previous resumable checkpoint, best/final model-only exports, adapters, and recent traces. Maintain at least 150 GB or 20% free space, whichever is greater.

## Upgrade triggers

Reassess storage before regular full-parameter 8B training, a separate trainable world model, any 30B checkpoint, more than two resumable branches, or when cleanup begins influencing experimental choices. Cloud scratch is not a durable backup.

## Backup

Verify remote copies by checksum before deleting local evidence. Backup capacity does not count as working capacity, and live bidirectional syncing of mutable experiment databases is prohibited without a separate consistency design.
