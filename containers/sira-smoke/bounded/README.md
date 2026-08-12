# T07 bounded SiRA smoke bundle

This directory is the repository-owned, x86_64 Lambda/Jupyter bootstrap surface for
the separately authorized one-pair bounded smoke. It is inert until a future exact
authorization is bound to the committed plan and the user manually invokes the
bootstrap from the selected Lambda instance.

The local `local_supervisor_bootstrap.py` verifies the exact contract and supervisor
module hashes before loading either one. The supervisor also proves that the execution
commit descends from the exact reviewed implementation commit, then materializes the
single-run authorization only after verifying the exact local private-binding seal and
its held-descriptor external bundle. The private locator is independently generated
and cannot be derived from the public alias or binding hash. It writes the
fsync-backed 13-GET observer ledger, verifies security before launch and termination
before firewall teardown, and performs the held-descriptor external archive copy. It
never implements a Lambda mutation; those remain explicit user-console actions. Exact local command
arrays use the repository's pinned `.venv/bin/python` rather than the macOS system
Python. Provider bodies are validated in memory and reduced to allowlisted,
secret-free receipts before anything is retained.

`prepare-bundle` produces one deterministic tracked-only USTAR archive with exactly
36 members: its manifest, the bounded plan, and the 34 plan-bound implementation
artifacts. The standalone bootstrap is transferred separately. Both identities are
bound into the single-use release and later retained in the sealed external archive;
untracked, ignored, private, environment, Git, artifact, or secret paths are rejected.
On the host, the standalone bootstrap verifies itself and the archive before importing
uploaded code, then exclusively claims and fsyncs
`/home/ubuntu/t07-bounded-output-0003` before authority, plan, contract, release, or
secret validation. Any terminal failure burns that canonical run root.

`Containerfile.amd64` builds from the immutable Playwright 1.39.0 multi-platform
index and requires the reviewed linux/amd64 manifest. The future staging step supplies
only a clean archive of SiRA commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`,
the hash-locked uv wheel, the repository routing patch, the minimal GIC Lab runtime
package, entrypoint, and local preflight fixtures. No secret belongs in the build
context. Runtime outputs use a 64 MiB tmpfs inside each owned container and are copied
out by immutable container ID before removal; there is no writable host evidence bind.
Both successful and failed post-root bootstraps produce bounded, secret-scanned
evidence archives for manual download before provider termination.

The local secret source is the single `OPENAI_API_KEY` assignment selected by a
strict no-shell, no-follow parser from the exact private plan-bound `.env`; the full
file is never uploaded. Before upload, the user must prove the fixed remote parent is
canonical, current-user-owned mode 0700 and the final target absent/non-symlink.
After upload, the user must prove an exact current-user-owned, regular, non-symlink
mode-0600 file. The metadata child receives native `OPENAI_API_KEY`; only an
immediate condition child receives the ephemeral `SIRA_API_KEY` alias. The bootstrap
and container entrypoint independently reject complete/multi-line or non-token secret
files before a provider child. The scan
covers direct, hex, Base64, and URL-safe Base64 representations before untrusted
bytes are hashed or retained; no credential hash is generated. Missing remote cleanup
proof remains unresolved until exact bound-instance termination proves destruction;
detected exposure, local cleanup failure, or destruction still unproven afterward
requires manual rotation. Missing workload/accounting evidence remains unresolved
even if termination proves destruction. Every Chat Completions request selects
service tier `default`; only a response reporting that tier can be reconciled as
standard-price execution.

The bounded plan opts each workload container into a deterministic entrypoint
readiness barrier; the shared entrypoint's other callers retain their existing
behavior.
The bootstrap must capture a live, nonempty process snapshot before releasing the
entrypoint, then wait for the immutable container ID, copy bounded output, and remove
the same ID. The downloaded ZIP is not trusted by filename alone: the local verifier
checks canonical stored members, manifest membership and hashes, pair identities,
normalized events, per-condition regulation decisions, compute-use closeout, and a
decoded secret scan before sealing `INBOUND_VERIFICATION.json`. Cleanup-only observer
phases remain usable after authorization expiry but can never launch or replay an
already attempted request ordinal.

The committed plan is unauthorized. Do not run a build, container, browser, model
metadata request, or SiRA condition from this directory without the fresh
authorization block in `docs/harness/T07_BOUNDED_SMOKE_V3_AUTHORIZATION_PACKET.md`.
