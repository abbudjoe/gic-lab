# T07 Gate B1 install authorization packet

Status: **SUPERSEDED — Gate B2 authorization blocked pending external-volume
rebinding**

Prepared: 2026-08-08

Reserved authorization reference: `AUTH-T07-GATE-B2-2026-08-08`.

This packet authorizes nothing by itself. It contains no authorization for a model
request, SiRA condition, experimental browser task, scientific change, pilot, cloud
mutation, or paid compute.

Post-packet governance addendum, 2026-08-09: decision D-017 now requires every
non-Git artifact, including Docker VM/image data and build cache, beneath
`/Volumes/Macintosh HD - Data/Users/joseph/.local/share/gic-lab` on APFS volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`. The materialization plan bound below writes
downloads and artifacts to the internal startup disk and does not bind Docker's disk
image location. It is therefore non-authorizable and must not be executed. Its prior
hash and commands are retained only as historical Gate B1 evidence until a reviewed
external-volume plan replaces them.

## 1. Exact clean repository commit

- Gate B1 implementation commit: `4be81e4a13fd06b77e36db21c4ad57165f7c115f`.
- Branch: `phase-1/sira-smoke`.
- Gate B1 baseline: `38e27ef20637471325ec15be216b4274bed5be49`.
- The implementation commit was bound after review and the post-review full gate.
  This packet-only descendant does not change the bound implementation tree.

## 2. Runtime present or exact installation action

No supported runtime is installed or running. Docker/Podman/Colima/Lima/nerdctl/
Rancher Desktop/OrbStack/Finch clients, applications, and daemons were absent.
Client version, server version, and daemon architecture are therefore unavailable.

The proposed runtime is exactly Docker Desktop for Mac (Apple silicon) **4.85.0,
build 235549**, published 2026-08-03, minimum macOS 14:

```text
URL: https://desktop.docker.com/mac/main/arm64/235549/Docker.dmg
Content-Length: 573592444
SHA-256: 84b1224c93456fe261955ebc91f3cd88ce19778ffdb6d0a0d423ce37246f7c2b
ETag: 4f9b2b18fabbf15788279792b6ea69a8
S3 version ID: wsuDysIsQ5IOyQOhS5596yFr.2s94QxI
```

Official metadata:

- <https://desktop.docker.com/mac/main/arm64/appcast.xml>
- <https://desktop.docker.com/mac/main/arm64/235549/checksums.txt>
- <https://docs.docker.com/desktop/setup/install/mac-install/>

After storage preflight passes and the user confirms their Docker license/subscription
entitlement, the exact proposed installation actions are the ordered actions
`require-fresh-dmg-path` through `capture-docker-info` in
`containers/sira-smoke/materialization-plan.json`. The plan hash is
`10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`. Its exact shell-free arrays download the one
DMG, fail-close on its exact size and SHA-256, attach it, invoke the mounted
`install` binary through `/usr/bin/sudo`, detach it, verify the installed CLI,
launch Docker Desktop, wait exactly 30 seconds once, and capture version and server
information. They may run only inside the single bounded supervisor in section 5;
executing an action separately is not authorized.

Post-install evidence must record product, client/server versions, context, OS,
architecture, security options, cgroup version/driver, and Docker Root Dir. The server
must be Linux `arm64`. A different artifact, automatic update, missing daemon, or
unprovable private PID/cgroup support stops Gate B2. Codex may not accept the license
for the user.

## 3. Target platform

Chosen: exactly `linux/arm64` native execution. `linux/amd64` is an unapproved
fallback and may not be selected automatically. The source-grounded matrix is
`docs/harness/T07_GATE_B1_CONTAINMENT_DECISION.md`.

## 4. Base image and immutable digest

```text
mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c
```

- Index digest:
  `sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c`.
- Arm64 manifest:
  `sha256:f8fca31a4730afa691e73ed99b4a6ebf28b2a9bd65a7038bb6da4bd223bb237b`.
- Arm64 config:
  `sha256:c0e7e7394b4baa0a5b3f735ca11eef3630c6c18d423c3849ee88c104bd9f1d9d`.
- Compressed selected layers: 719,590,824 bytes.

The final locally built image ID is intentionally unknown before the prohibited
build. Gate B2 resolves the local tag once, verifies its build labels, records the
observed `sha256:` ID, and passes only that ID to `docker container create`.

## 5. Exact pulls and build steps

All materialization outputs are outside both Git checkouts; the hashed plan and
reviewed source inputs remain in this repository. No action has run. The sole proposed
entrypoint is the command below; the hashed JSON plan is the authoritative rendering
of all 51 exact argument arrays, expected-stdout checks, and per-action timeouts.

```text
PYTHONPATH=/Users/joseph/.codex/worktrees/84b1/gic-lab/src /opt/homebrew/Cellar/uv/0.11.7/bin/uv run --no-sync python -m giclab.harness.sira_container execute-materialization-plan --plan /Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/materialization-plan.json --plan-sha256 10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25 --ledger /Users/joseph/.local/share/gic-lab-t07-gate-b2-materialization-ledger.json
```

The supervisor starts one monotonic 3,600-second deadline before its first action,
allows exactly one call per action and no retry, gives every child
`min(per-action cap, aggregate remainder)`, streams stdout/stderr through a hard
16,777,216-byte aggregate limiter, and records only bounded sizes/hashes in a fresh
ledger. It stops on timeout, output exhaustion, nonzero status, or expected-stdout
drift.

Before any download the plan requires a clean worktree descended from
`4be81e4a13fd06b77e36db21c4ad57165f7c115f`; the exact implementation-to-HEAD tree delta
must contain only the materialization plan and three packet/ledger documents. It then
requires the storage floor. Before attach it
fail-closes on the DMG's exact size/SHA-256. Before build it requires the exact pinned
source HEAD and clean status, exact uv wheel size/SHA-256, an equality match between
the staged and pinned source trees, byte-for-byte mode-0444 repository build inputs,
the exact uv.lock, no extra build-context top-level entry, successful patch dry-run,
and this context-evidence digest:
`747575a0c4c1dc9c0e52a839dc28eea1807e898495ee2c58c7b25ae8ab4ba77b`.
It checks the 150-GiB floor after install, pull, source/wheel staging, and build, then
captures the label-verified immutable image identity.

Pre-build hashes must match this packet. Post-build image identity must validate before
any fixture container is created.

## 6. Dependency and browser downloads

- uv wheel: 23,609,640 bytes, SHA-256
  `5985a15a92bd9a170fc1947abb1fbc3e9828c5a430ad85b5bed8356c20b67a71`.
- SiRA lock SHA-256:
  `138585129c7f369887591d30d9727f8dd466639fa78fb00adc5a04f1e9b2d76e`.
- Dependency action: exactly `uv sync --frozen --extra eval --python 3.10`.
- Dependency transport: `UV_HTTP_RETRIES=0` and `UV_PYTHON_DOWNLOADS=never`; no
  dependency retry or managed-Python download is allowed.
- Conservative locked-artifact transfer estimate: 313,827,106 bytes.
- Additional browser-download command: **none**. The immutable Playwright 1.39.0
  image already contains browser artifacts. `playwright install` and any host browser
  installer are forbidden.
- Required browser identity: Playwright 1.39.0 and Chromium revision 1084. Its
  executable SHA-256 is an observed Gate B2 value, never a guessed field.

## 7. Expected network endpoints

Only HTTPS/443 is expected:

| Phase | Endpoints |
|---|---|
| Docker Desktop artifact | `desktop.docker.com` |
| Base image | `mcr.microsoft.com` |
| Pinned source | `github.com`, `codeload.github.com` |
| Python lock artifacts | `pypi.org`, `files.pythonhosted.org` |

No `api.openai.com`, provider model endpoint, Playwright CDN/browser downloader,
arbitrary website, cloud compute API, image push, or other registry is allowed. An
endpoint outside the table is not expected or approved. Docker Desktop/buildx does
not expose an endpoint allowlist or complete egress telemetry through the proposed
commands, so this expectation is not mechanically enforced. Gate B2 authorization
must explicitly accept that limitation; if enforced endpoint control is required,
stop before installation for a separately reviewed egress-gateway design.

## 8. Worst-case transfer and disk usage

- Known transfer components: 1,630,620,014 bytes before the small source archive and
  protocol overhead.
- Exact authorized transfer ceiling: 2,147,483,648 bytes (2 GiB), with zero
  agent-level command retry allowance; runtime-internal retransmission consumes the
  same reservation.
- Exact incremental disk ceiling: 12,884,901,888 bytes (12 GiB), including app, VM,
  image layers, final image, context, and evidence.
- Exact aggregate automated materialization wall ceiling: 3,600 monotonic seconds,
  mechanically shared by all 51 plan actions. Per-action maxima include 600 seconds
  for the DMG, 600 for the image pull, 300 for source fetch, 120 for the uv wheel,
  and 900 for build; the supervisor always uses the smaller aggregate remainder.
- Exact materialization command/output caps: 51 shell-free child calls, one attempt
  per action, zero retry, and 16,777,216 aggregate stdout/stderr bytes. Streaming
  enforcement kills the action process group before accepting byte 16,777,217.
- No image push is authorized.

The direct file downloads mechanically enforce their individual byte/wall maxima and
are followed by exact size/SHA-256 verifiers. Docker
Desktop does not expose a reliable per-pull/build network-byte meter through these CLI
commands, so the 2-GiB ceiling is enforced as an immutable-content reservation: one
digest-pull command, one frozen-build command, no agent retry, and immediate stop on
observable digest, lock, or size drift. It is not represented as observed transfer
telemetry. If Gate B2
requires a live byte-meter rather than this reservation contract, authorization must
stop for a separate metering design.

## 9. Storage floors

The superseded plan checked the internal startup disk and must not be used:

```text
/usr/bin/python3 -c 'import shutil,sys; value=shutil.disk_usage("/Users/joseph").free; print(value); raise SystemExit(0 if value >= 173946175488 else 1)'
```

D-017 instead binds the external APFS container with total capacity
1,000,240,963,584 bytes. Its exact post-build floor is the greater of 150 GiB and 20%
of capacity: **200,048,192,717 bytes**. Including the 12,884,901,888-byte incremental
disk reservation, a replacement plan must require at least **212,933,094,605 free
bytes** before materialization and recheck the 200,048,192,717-byte floor after every
artifact-producing stage and probe.

Read-only inspection at `2026-08-09T11:27:04Z` identified the intended external,
read-write Thunderbolt APFS data volume at `/Volumes/Macintosh HD - Data`, UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, with **854,038,687,744 free bytes**. That
observation clears the raw capacity floor by 641,105,593,139 bytes but does not clear
authorization: a replacement control plane must verify the volume UUID, external and
read-write state, resolved artifact-root device, and Docker VM disk-image location.

## 10. Exact synthetic resource limits

| Probe | CPU | Memory/swap | PIDs | Workload wall | Output: payload/log/evidence | shm | each tmpfs | TERM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Containment | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B: 8,388,608 / 2,097,152 / 6,291,456 | 67,108,864 B | 67,108,864 B | 1 s |
| Dummy secret | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B: 8,388,608 / 2,097,152 / 6,291,456 | 67,108,864 B | 67,108,864 B | 1 s |
| Browser only | 2.000 | 2,147,483,648 B | 256 | 60 s | 33,554,432 B: 16,777,216 / 4,194,304 / 12,582,912 | 1,073,741,824 B | 134,217,728 B | 2 s |

Aggregate probe caps: USD 0 API cost, 0 model tokens, 0 model/API calls, 3 container
attempts, 120 workload seconds, 1 local browser action, 1 screenshot evidence capture,
67,108,864 retained bytes, and at most 96 Docker lifecycle CLI operations through
fixed state machines. Each operation has a 10-second client timeout except stop, which
adds only the declared 1- or 2-second TERM grace. Screenshot capture is evidence, not
a second browser navigation/action. Installation/build uses the separate 3,600-second
ceiling above.

Per-probe API cost, model tokens, and model/API calls are all exactly zero. Browser
actions are 0 containment, 0 dummy-secret, and 1 browser-only. The per-probe Docker
lifecycle ceiling is 32 operations.

## 11. Exact no-network containment command

Fixed UUID: `b2000000000000000000000000000001`.

```text
/bin/test ! -e /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts
/bin/mkdir -m 0700 /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts
PYTHONPATH=/Users/joseph/.codex/worktrees/84b1/gic-lab/src /opt/homebrew/Cellar/uv/0.11.7/bin/uv run --no-sync python -m giclab.harness.sira_container execute-fixture --repository-root /Users/joseph/.codex/worktrees/84b1/gic-lab --runtime /Applications/Docker.app/Contents/Resources/bin/docker --image-identity /Users/joseph/.local/share/gic-lab/t07-gate-b2/image-identity.json --owned-base /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts --repository-commit 4be81e4a13fd06b77e36db21c4ad57165f7c115f --attempt-uuid b2000000000000000000000000000001 --authorization-reference AUTH-T07-GATE-B2-2026-08-08 --fixture adversarial-containment
```

The wrapper renders `--network none`, omits Docker's invalid `--pid private` spelling
so the runtime creates its default private PID namespace, renders
`--cgroupns private`, and inspect-verifies both fields before start. Stop/kill use only
the immutable container ID. Reused attempt or container identities are rejected.

## 12. Exact no-network browser-only command

Fixed UUID: `b2000000000000000000000000000002`.

```text
PYTHONPATH=/Users/joseph/.codex/worktrees/84b1/gic-lab/src /opt/homebrew/Cellar/uv/0.11.7/bin/uv run --no-sync python -m giclab.harness.sira_container execute-fixture --repository-root /Users/joseph/.codex/worktrees/84b1/gic-lab --runtime /Applications/Docker.app/Contents/Resources/bin/docker --image-identity /Users/joseph/.local/share/gic-lab/t07-gate-b2/image-identity.json --owned-base /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts --repository-commit 4be81e4a13fd06b77e36db21c4ad57165f7c115f --attempt-uuid b2000000000000000000000000000002 --authorization-reference AUTH-T07-GATE-B2-2026-08-08 --fixture browser-preflight
```

It performs exactly one navigation action to bundled
`file:///opt/giclab/fixtures/static.html`, takes one screenshot as evidence, and closes
the browser. It contains no SiRA condition or model client. After this probe succeeds,
the complete image-provenance record is assembled exactly once:

```text
PYTHONPATH=/Users/joseph/.codex/worktrees/84b1/gic-lab/src /opt/homebrew/Cellar/uv/0.11.7/bin/uv run --no-sync python -m giclab.harness.sira_container assemble-image-provenance --repository-root /Users/joseph/.codex/worktrees/84b1/gic-lab --image-identity /Users/joseph/.local/share/gic-lab/t07-gate-b2/image-identity.json --browser-attempt-uuid b2000000000000000000000000000002 --browser-record /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts/browser-preflight-b2000000000000000000000000000002/browser-preflight.json --browser-pre-removal-evidence /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts/browser-preflight-b2000000000000000000000000000002/container-evidence-before-removal.json --browser-cleanup-seal /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts/browser-preflight-b2000000000000000000000000000002/container-cleanup-seal.json --output /Users/joseph/.local/share/gic-lab/t07-gate-b2/image-provenance.json
```

That assembler equality-matches the raw browser record to the fixture record retained
before removal, requires the same attempt's successful sealed cleanup evidence, proves
both inspect snapshots and the cleanup seal name the exact immutable image/attempt,
and retains SHA-256 hashes of all three inputs. The resulting record combines those
bindings with the base index/platform digests, Containerfile/source/patch/runtime-
adaptation/build-assets/lock hashes, installed package manifest hash, Playwright/
Chromium identity, Chromium executable hash, final image ID, repo-digest status, and
platform. Missing, stale, failed, or contradictory evidence stops Gate B2.

## 13. Dummy-secret contract

The canary is public test data, not a credential:
`T07_GATE_B2_DUMMY_CANARY_PUBLIC_NOT_A_CREDENTIAL`. Fixed UUID:
`b2000000000000000000000000000003`.

```text
/bin/test ! -e /Users/joseph/.local/share/gic-lab/t07-gate-b2/secrets
/bin/mkdir -m 0700 /Users/joseph/.local/share/gic-lab/t07-gate-b2/secrets
PYTHONPATH=/Users/joseph/.codex/worktrees/84b1/gic-lab/src /opt/homebrew/Cellar/uv/0.11.7/bin/uv run --no-sync python -m giclab.harness.sira_container write-dummy-secret --output /Users/joseph/.local/share/gic-lab/t07-gate-b2/secrets/dummy-sira-api-key
PYTHONPATH=/Users/joseph/.codex/worktrees/84b1/gic-lab/src /opt/homebrew/Cellar/uv/0.11.7/bin/uv run --no-sync python -m giclab.harness.sira_container execute-fixture --repository-root /Users/joseph/.codex/worktrees/84b1/gic-lab --runtime /Applications/Docker.app/Contents/Resources/bin/docker --image-identity /Users/joseph/.local/share/gic-lab/t07-gate-b2/image-identity.json --owned-base /Users/joseph/.local/share/gic-lab/t07-gate-b2/attempts --repository-commit 4be81e4a13fd06b77e36db21c4ad57165f7c115f --attempt-uuid b2000000000000000000000000000003 --authorization-reference AUTH-T07-GATE-B2-2026-08-08 --fixture dummy-secret-preflight --secret-file /Users/joseph/.local/share/gic-lab/t07-gate-b2/secrets/dummy-sira-api-key
```

The host-user-owned mode-0600 file and mode-0700 attempt root are accessed by the
exact host numeric UID:GID `501:20` inside the container. The file is mounted read-only
only at `/run/secrets/sira_api_key`. The entrypoint exports `SIRA_API_KEY` only to
`secret_probe.py`. Rendered argv, labels, inspect, logs, and every retained file are
scanned for the exact canary.
`OPENAI_API_KEY` is rejected. The real secret is neither needed nor permitted.

## 14. Cleanup and removal contract

For every created fixture, including failures:

1. Capture exact ID, name, labels, image ID, policy inspect, and pre-stop process table.
2. Bound workload/output; stop for the declared grace and KILL the complete container
   boundary if stop fails or terminal state is absent.
3. Require terminal state and matching wait/inspect exit code. Capture bounded logs and
   final inspect, scan the dummy canary where applicable, and fsync pre-removal evidence.
4. Remove only that terminal, label-validated immutable container ID.
5. Query all running/stopped containers plus networks and volumes by the attempt UUID;
   require every result empty.
6. Seal exact retained bytes. Truncation, incomplete evidence, a failed residual query,
   or a failed failure-cleanup proof invalidates the probe and blocks progression.
7. On any post-create exception, repeat label-bound inspect/top/stop/kill/evidence/
   remove/residual verification. Never substitute a container found only by name.
8. Remove the public dummy file only after scanning. Retain attempt, runtime, image,
   build, and failure evidence plus the final local image. Attempt roots are immutable
   and are not deleted or reused; Docker is not automatically uninstalled.
9. No host PID cleanup, cloud/provider cleanup, broad Docker prune, evidence deletion,
   or unrelated-resource mutation is authorized.

Exact canary cleanup proposed:

```text
/bin/unlink /Users/joseph/.local/share/gic-lab/t07-gate-b2/secrets/dummy-sira-api-key
```

## 15. Tests and checks run

```text
git status --short
git rev-parse HEAD
git merge-base --is-ancestor 38e27ef20637471325ec15be216b4274bed5be49 HEAD
PYTHONPATH=src uv run --no-sync pytest -q tests/test_sira_gate_a.py tests/test_sira_adapter.py tests/test_harness_executor.py tests/test_harness_budget.py tests/test_harness_policy.py
PYTHONPATH=src uv run --no-sync pytest -q tests/test_sira_container.py tests/test_harness_schemas.py
uv run --no-sync ruff check src/giclab/harness/sira_container.py containers/sira-smoke/fixtures containers/sira-smoke/container_entrypoint.py tests/test_sira_container.py tests/test_harness_schemas.py src/giclab/validation.py
uv run --no-sync mypy src/giclab/harness/sira_container.py
/usr/bin/patch --dry-run --silent -d <fresh-directory-containing-pinned-source> -p1 < containers/sira-smoke/sira-immutable-model-routing.patch
make validate
make check QUARTO=/private/tmp/giclab-t07-quarto.nT1Msu/bin/quarto
git diff --check
```

Observed: pre-edit Gate A passed 133 tests. The final Gate B1/schema suite passes 84;
the combined Gate A+B1 focused collection is 217. Patch application passed against
the exact pinned upstream file fetched read-only. Ruff, strict mypy, repository/schema
validation, and `git diff --check` pass. The initial independent review failed with
eleven findings; successive rereview exposed and repaired mount allowlisting,
deadline/endpoint truthfulness, provenance binding, executable/digest validation,
and materialization cap/tree-binding defects. Final independent spec-conformance
rereview is clean. The post-repair full check passes 389 tests plus the real Quarto
render and site validation.

No test called a model API, launched a browser/container, pulled/built an image,
installed a runtime/dependency/browser, or read a real secret.

## 16. Remaining blockers

1. **Authorization-stopping storage-target blocker:** the attached volume has adequate
   observed capacity, but the hashed plan still targets the internal disk and does not
   verify external volume UUID `8478609D-FA37-4ED5-875D-47AE912B9151`.
2. Docker Desktop is absent and its license/installation is unauthorized; its exact
   VM disk-image relocation and verification actions are not yet rendered.
3. The materialization plan, commands, cleanup paths, packet hash, and authorization
   block require reviewed external-volume rebinding.
4. Runtime/cgroup identity, final image ID, package hash, Chromium executable hash,
   and empirical containment remain unknown until Gate B2.
5. Mock tests do not prove kernel containment; the adversarial probe must pass.
6. Gate B2 is no-network probe authorization only. Live SiRA still requires a reviewed
   isolated-egress network policy, full post-build provenance, condition command
   materialization, current model/price verification, and new current-turn authority.
7. The historical implementation and plan hashes remain evidence, not executable
   authorization under D-017.

## 17. Gate B2 authorization status

There is no ready-to-copy Gate B2 authorization block. The prior block is withdrawn
because it names internal-disk paths and an unverified Docker data location. A new
packet must bind the exact external volume UUID and artifact root, verify Docker's VM
disk location there, rerender every materialization/probe/cleanup path, recompute the
plan SHA-256, rerun validation and independent review, and only then present a new
authorization block. Gate B2 and live T07 remain unauthorized.
