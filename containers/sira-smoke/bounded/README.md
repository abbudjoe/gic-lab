# T07 bounded SiRA smoke bundle

This directory is the repository-owned, x86_64 Lambda/Jupyter bootstrap surface for
the separately authorized one-pair bounded smoke. It is inert until a future exact
authorization is bound to the committed plan and the user manually invokes the
bootstrap from the selected Lambda instance.

The local `local_supervisor_bootstrap.py` verifies the exact contract and supervisor
module hashes before loading either one. The supervisor materializes the external
single-run authorization/private-resource binding, writes the fsync-backed 13-GET
observer ledger, verifies security before launch and termination before firewall
teardown, and performs the held-descriptor external archive copy. It never implements
a Lambda mutation; those remain explicit user-console actions.

`Containerfile.amd64` builds from the immutable Playwright 1.39.0 multi-platform
index and requires the reviewed linux/amd64 manifest. The future staging step supplies
only a clean archive of SiRA commit `93fb8d72de71f9a4a13419670adeb34d93cf7acd`,
the hash-locked uv wheel, the repository routing patch, the minimal GIC Lab runtime
package, entrypoint, and local preflight fixtures. No secret belongs in the build
context. Runtime outputs use a 64 MiB tmpfs inside each owned container and are copied
out by immutable container ID before removal; there is no writable host evidence bind.
Both successful and failed post-root bootstraps produce bounded, secret-scanned
evidence archives for manual download before provider termination.

The committed plan is unauthorized. Do not run a build, container, browser, model
metadata request, or SiRA condition from this directory without the fresh
authorization block in `docs/harness/T07_BOUNDED_SMOKE_AUTHORIZATION_PACKET.md`.
