# T07 Gate B1 containment implementation ledger

## Contract

- Governing task contract: T07 v1.2 and the current Gate B1 contract dated
  2026-08-08.
- Governing readiness contract: `docs/readiness/PHASE_1_SMOKE_READINESS.md`.
- Gate B1 baseline: `38e27ef20637471325ec15be216b4274bed5be49`.
- Working branch: `phase-1/sira-smoke`.
- Scope: containment control-plane implementation, mock/fake validation, and an exact
  Gate B2 install/build/probe authorization packet.
- Out of scope: runtime installation/update, image pull/build, dependency/browser
  installation, any container/browser launch, model/provider API access, either SiRA
  condition, scientific-field changes, authorization materialization, and the pilot.

## Definition of done

| ID | Obligation | Evidence target | Status |
|---|---|---|---|
| T07-GB1-DOD-01 | Preserve the named-branch baseline, locked scientific files, and false authorization fields. | Starting checks, hashes, and final diff. | met |
| T07-GB1-DOD-02 | Inventory an installed runtime without mutation and fail closed when none is present. | Exact product/client/server/architecture inventory. | met: none present |
| T07-GB1-DOD-03 | Compare native arm64 and emulated amd64 with immutable image, dependency, size, memory, and risk evidence. | Source-grounded matrix and one target. | met: `linux/arm64` chosen |
| T07-GB1-DOD-04 | Make a fresh private-PID OCI container ID the authoritative descendant boundary. | Typed executor/policy; no host-process fallback. | met in control plane; empirical proof is Gate B2 |
| T07-GB1-DOD-05 | Render exact create/start/inspect/top/wait/logs/stop/kill/remove and residual-resource arrays. | Shell-free renderer and tests. | met |
| T07-GB1-DOD-06 | Reject privileged/host PID or network/socket mounts, unsafe capabilities/mounts, floating images, restart drift, and absent limits. | Adversarial policy tests. | met |
| T07-GB1-DOD-07 | Record container/image/platform/resource/lifecycle identities under authoritative schemas. | Typed documents, schemas, and relational validation. | met |
| T07-GB1-DOD-08 | Supply descendant-escape and local browser-only fixtures without running them. | Repository fixtures and exact future commands. | met; not run |
| T07-GB1-DOD-09 | Require capture-before-removal, stop/kill, terminal/removal proof, no owned leftovers, and sealed cleanup. | Lifecycle verifier and fake state-machine tests. | met in control plane; empirical proof is Gate B2 |
| T07-GB1-DOD-10 | Enforce fresh attempt-root ownership and one bounded writable attempt bind. | Ownership/mount validation and regressions. | met |
| T07-GB1-DOD-11 | Keep upstream clean and stage a separately hashed routing patch in a versioned build context. | Build contract, Containerfile, patch, and hashes. | met; build not run |
| T07-GB1-DOD-12 | Produce complete post-build image provenance, including explicit local repo-digest absence. | Provenance assembler/schema and tests. | met; observed values deferred to Gate B2 |
| T07-GB1-DOD-13 | Pass only `SIRA_API_KEY` by file to the child, reject `OPENAI_API_KEY`, and prove dummy-canary non-leakage. | Entrypoint, scanner, policy, and fake tests. | met; real secret untouched |
| T07-GB1-DOD-14 | Preserve every Gate A control and regression. | Focused Gate A suite and full checks. | met |
| T07-GB1-DOD-15 | Produce the decision, updated preauthorization packet, and exact 17-field Gate B2 packet. | Required documentation paths. | met |
| T07-GB1-DOD-16 | Pass focused tests, validation, full checks, independent review, repairs/rereview, and final full check. | Validation/review log. | met |
| T07-GB1-DOD-17 | Commit the reviewed implementation and final packet on the named branch with a clean tree. | Exact commits and final status. | met: implementation `4be81e4a13fd06b77e36db21c4ad57165f7c115f`; packet-only descendant pending this ledger commit |

## Implementation mapping

| DoD | Repository evidence |
|---|---|
| 04–06, 09–10 | `src/giclab/harness/sira_container.py`, `tests/test_sira_container.py` |
| 07, 12 | `schemas/container-attempt.schema.json`, `schemas/container-image-provenance.schema.json`, `schemas/container-platform-decision.schema.json`, `schemas/container-materialization-plan.schema.json`, `src/giclab/validation.py`, schema tests |
| 08 | `containers/sira-smoke/fixtures/adversarial_containment.py`, `browser_preflight.py`, `secret_probe.py`, `static.html` |
| 11–12 | `containers/sira-smoke/Containerfile`, `.dockerignore`, `sira-immutable-model-routing.patch`, build/image identity and provenance code |
| 13 | `containers/sira-smoke/container_entrypoint.py`, secret policy/scanner tests |
| 14 | Existing Gate A harness plus its 133-test focused regression suite |
| 03, 15 | `containers/sira-smoke/materialization-plan.json`, `docs/harness/T07_GATE_B1_CONTAINMENT_DECISION.md`, `T07_GATE_B1_INSTALL_AUTHORIZATION_PACKET.md`, `T07_PREAUTHORIZATION_PACKET.md` |

## Validation and review log

- Starting branch: `phase-1/sira-smoke`.
- Starting HEAD: `38e27ef20637471325ec15be216b4274bed5be49`.
- Starting worktree: clean; baseline ancestry confirmed.
- Locked protocol/config/profile/condition hashes remained unchanged and all execution
  authorization/project permission fields remained false.
- Pre-edit Gate A focused suite: 133 passed.
- Runtime inventory: no Docker, Podman, Colima, Lima, Rancher Desktop, OrbStack,
  Finch, nerdctl, or compatible client/server was installed or running.
- Initial Gate B1 focused suite, repository validation, and pre-review full check:
  passed; the full suite had 359 tests and used the already available temporary Quarto
  1.9.38 binary.
- First independent spec-conformance review: failed with eleven prioritized findings.
  Repairs removed invalid `--pid private`, added explicit private cgroup-namespace
  validation, moved wall accounting before create, bounded payload/log/evidence output,
  rejected mount/secret expansion, made host UID:GID ownership explicit, strengthened
  lifecycle schemas, added complete provenance assembly, and corrected the packet
  control plane.
- Final Gate B1/schema suite: 84 passed. Combined Gate A + Gate B1 focused collection:
  217 tests. Ruff, mypy, repository validation, `git diff --check`, and a dry-run
  patch against the exact pinned upstream source passed.
- Successive rereview repairs added an exact repository-file mount allowlist,
  non-rounded deadlines, truthful endpoint limits, browser/image evidence binding,
  executable and fail-closed digest checks, and one hashed 51-action materialization
  supervisor with monotonic wall, streamed output, no-retry, staged-context, and exact
  reviewed-tree controls.
- Final independent spec-conformance rereview: clean. The post-repair full check
  passed 389 tests plus the real Quarto render and site validation.
- Reviewed implementation commit:
  `4be81e4a13fd06b77e36db21c4ad57165f7c115f`.
- Bound Gate B2 materialization-plan SHA-256:
  `10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`.

## Gate result

Assembly status: **Gate B1 complete**. Gate B2 and live T07 remain unauthorized.
