# T07 Gate L2M manual-console bundle

This directory contains the exact, executable-but-unauthorized Gate L2M host
qualification control plane. Nothing here authorizes a Lambda request, console
mutation, instance, Jupyter session, image pull, container or paid compute.

The V1 and V2 plans remain preserved as historical provenance. The active replacement is
`gate-l2m-host-qualification-plan-v3.json`, plan
`PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3`, run
`RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003`, 21,641 bytes, SHA-256
`1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654`.
It is bound to reviewed implementation commit
`af54784f02e4675e25cd21925fd3c5d62cd0ed68`, has 23 ordered actor steps and 13
single-use user checkpoint templates, and keeps all authority fields false. Its public
metadata permits a supervisor start no later than `2026-08-12T05:15:19.646016Z`;
expiry requires a new immutable bundle, plan, review and authorization.

`l23_supervisor_bootstrap.py` is the repository-relative `python -I` bootstrap. It
loads only exact source bytes from the clean checkout, validates the plan/hash,
required commit, implementation artifact hashes, ignored private seals, fresh run
roots, storage guard, budgets and authorization binding, and then invokes the
GET-only observer. It has no automated mutation method. The user alone performs the
console actions under a future exact authorization.

`checkpoints/` contains deliberately incomplete public templates. During an
authorized run, the observer creates a private challenge for each required user
action; the user fills the corresponding fresh mode-`0600` checkpoint only inside its
300-second window. Instance binding and terminal proof are observer receipts, not user
checkpoints. Never place raw resource IDs, the source IPv4, fingerprints, Jupyter
URLs/tokens, secrets or private paths in these templates.

The six-file qualification bundle is bound by `manifest.json`, 1,510 bytes,
SHA-256 `dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261`.
`qualification_driver.py` may run only through the plan's exact hash-first isolated
bootstrap array. It validates host/runtime identities and one digest-pinned BusyBox
containment fixture, produces a bounded evidence archive, and never installs,
updates, browses, calls a model or runs SiRA. It has not been uploaded or executed.

The human sequence and incident branches are authoritative in
`docs/harness/T07_GATE_L2M_USER_RUNBOOK.md`; the future authorization boundary is in
`docs/harness/T07_GATE_L2M_HOST_QUALIFICATION_AUTHORIZATION_PACKET.md`.
