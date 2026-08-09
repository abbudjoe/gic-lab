# T07 Gate B1 containment decision

Status: **control plane implemented; empirical Gate B2 proof not run**

Prepared: 2026-08-08

## Decision

T07 condition attempts must run in a fresh ephemeral Linux OCI container. The
authoritative descendant-containment handle is the immutable container ID returned by
the runtime. Host process groups, `setsid`, `killpg`, `pkill -P`, PID polling, and host
descendant enumeration are not an acceptable fallback or proof boundary.

The chosen target is **native `linux/arm64`** on the M4 Mac. The candidate image is:

```text
mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c
```

The index digest above resolves to the `linux/arm64` platform manifest
`sha256:f8fca31a4730afa691e73ed99b4a6ebf28b2a9bd65a7038bb6da4bd223bb237b`.
The selected platform is not a claim that containment works on this host: that kernel
claim remains untested until Gate B2 installs a supported runtime, builds the image,
and passes the adversarial probe.

## Starting state and runtime inventory

- Branch: `phase-1/sira-smoke`.
- Gate B1 baseline: `38e27ef20637471325ec15be216b4274bed5be49`.
- Baseline worktree: clean.
- Host: Apple M4 / `arm64`, macOS 26.5.1 build 25F80.
- Runtime inspection found no Docker CLI or Docker Desktop application, no Podman,
  Colima/Lima, Rancher Desktop, OrbStack, Finch, nerdctl, or compatible daemon.
- Client version: unavailable because no client is installed.
- Server version and architecture: unavailable because no daemon is installed or
  running.
- No runtime was installed, updated, started, or configured in Gate B1.

The absent runtime is an installation-authorization item, not evidence against the
design. Docker Desktop 4.85.0 build 235549 for Apple silicon is the exact proposed
runtime. Its observed official appcast metadata and checksum are recorded in
`docs/harness/T07_GATE_B1_INSTALL_AUTHORIZATION_PACKET.md`.

## Compatibility matrix

Public metadata was inspected without pulling an image or executing a container.

| Field | Native `linux/arm64` | Emulated `linux/amd64` |
|---|---|---|
| Runtime path on M4 | Docker Desktop Linux VM, native arm64 guest workloads | Docker Desktop x86_64/amd64 emulation path; Rosetta/QEMU implementation is runtime-setting dependent |
| Base index digest | `sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c` | same multi-platform index |
| Platform manifest digest | `sha256:f8fca31a4730afa691e73ed99b4a6ebf28b2a9bd65a7038bb6da4bd223bb237b` | `sha256:8f7d4d5ef52dbe4af81db537258ae6d15c71b86c6984dd6030dac8f34c86ebcd` |
| Platform config digest | `sha256:c0e7e7394b4baa0a5b3f735ca11eef3630c6c18d423c3849ee88c104bd9f1d9d` | `sha256:801969079a1e0ae8c657adc45f7acac5abcc7fab846e60cd42c883ee78dded51` |
| Compressed base layers | 719,590,824 bytes (686.26 MiB) | 742,924,281 bytes (708.51 MiB) |
| Python 3.10 | Ubuntu 22.04 base metadata installs system Python; SiRA requires `>=3.10,<3.13`, preferred 3.10 | same image recipe and source requirement |
| `uv sync --frozen --extra eval` | Feasible from the exact lock: compatible arm64 wheels are present for compiled direct/transitive dependencies inspected, including Playwright, greenlet, NumPy, and pandas | Feasible from the exact lock: corresponding x86_64 wheels are present |
| BrowserGym | `browsergym-core==0.3.6.dev0` is a 182,590-byte `py3-none-any` wheel in the lock; compiled dependencies have arm64 candidates | same pure-Python BrowserGym wheel; compiled dependencies have x86_64 candidates |
| Playwright Python | 1.39.0 arm64 wheel SHA-256 `654bb3ae0dc3c69ffddc0c38c127c3b8e93032d8cf3928e2c4f21890cb39514b`, 35,388,063 bytes | 1.39.0 x86_64 wheel SHA-256 `699a8e707ca5f3567aa28223ee1be7e42d2bf25eda7d3d86babda71e36e5f16f`, 35,496,523 bytes |
| Chromium | Playwright 1.39.0 metadata binds Chromium revision 1084 / browser 119.0.6045.9; image version matches the Python package | same revision and version |
| Frozen dependency transfer estimate | Conservative compatible-candidate sum: 313,827,106 bytes (299.29 MiB) | comparable; exact selected-wheel total remains a build observation |
| Browser preflight memory limit | 2,147,483,648 bytes plus 1,073,741,824-byte private shm | same limit would apply, but emulation overhead increases pressure |
| Reproducibility risks | Image was published in 2023; actual frozen resolution, browser executable hash, and container kernel behavior still require the authorized build/probe | all native risks plus emulation implementation/version and translation-cache drift |
| Performance risks | Browser startup/runtime cost remains unmeasured | potentially material CPU/startup overhead and nondeterministic emulation effects |

The evidence is sufficient to choose arm64 because the exact base platform manifest
exists, the locked Python requirements and architecture-specific wheels are compatible,
the Playwright image/package versions agree, and no emulation layer is needed. If the
authorized frozen build cannot resolve entirely from the locked arm64 artifacts, it
must stop; it must not switch to amd64 implicitly.

## Sources inspected

- Docker image manifest API:
  <https://mcr.microsoft.com/v2/playwright/python/manifests/v1.39.0-jammy>
- Pinned SiRA lock:
  <https://raw.githubusercontent.com/sailing-lab/sira/93fb8d72de71f9a4a13419670adeb34d93cf7acd/uv.lock>
- Pinned SiRA Python requirement:
  <https://raw.githubusercontent.com/sailing-lab/sira/93fb8d72de71f9a4a13419670adeb34d93cf7acd/pyproject.toml>
- Playwright 1.39.0 browser registry:
  <https://raw.githubusercontent.com/microsoft/playwright/v1.39.0/packages/playwright-core/browsers.json>
- Playwright container guidance:
  <https://playwright.dev/python/docs/docker>
- Docker namespaces/cgroups and daemon-socket security:
  <https://docs.docker.com/engine/security/>
- Docker Desktop Apple-silicon installation and emulation prerequisites:
  <https://docs.docker.com/desktop/setup/install/mac-install/>

## Authoritative runtime policy

`src/giclab/harness/sira_container.py` rejects a planned attempt unless all of the
following are true:

- the image is a registry digest or an observed local `sha256:` image ID;
- the platform is explicit;
- Docker's valid private-PID representation is used by omitting `--pid`; inspect must
  report an empty `PidMode`. `--cgroupns private` is explicit and inspect-verified;
  IPC is private;
- networking is `none` for every Gate B2 fixture;
- privileged mode, host PID/IPC/network, capability additions, runtime sockets, root
  execution, and implicit pulls are absent;
- all capabilities are dropped, `no-new-privileges` and init are enabled, the root
  filesystem is read-only, and restart policy is exactly `no`;
- memory, memory+swap, CPU, PID, wall-time, output, shm, tmpfs, and TERM grace limits
  are finite;
- only one harness-owned attempt root is writable; immutable source is baked into the
  read-only image, while every runtime source/configuration bind must be an exact
  regular file under the repository, appear in an external typed allowlist that
  exactly equals the mounted input set, and be read-only; directory inputs such as
  `/private/etc` and `/private/var` are rejected;
- the attempt executes as exact host numeric UID:GID `501:20`, matching the mode-0700
  attempt root and mode-0600 secret file; `/tmp` and `/run/secrets` are bounded tmpfs
  mounts owned by that identity;
- a SiRA or dummy-secret child receives exactly one secret file at
  `/run/secrets/sira_api_key`; no credential is placed in argv, labels, or the
  container configuration environment list; and
- labels bind experiment, parent profile, condition/probe, attempt, attempt UUID,
  repository commit, source commit, image digest, and authorization reference.

The exact lifecycle is create → inspect identity/policy → start → bounded
readiness/wall/output monitoring → capture `docker top` process evidence → stop → kill
when needed → verify
terminal state → capture logs and final inspect → persist pre-removal evidence → remove
→ prove no labeled container/network/volume remains → seal cleanup evidence. Every
post-create exception enters label-validated emergency cleanup. The wall clock begins
before attempt-root allocation and container create; control-command timeouts use the
exact positive remainder without rounding past the workload deadline. Retained output is split into
fixed payload/log/evidence allocations, Docker local logs are size-bounded, success
requires complete untruncated evidence, and even failure cleanup must fit the total
cap. No host PID list is used as the ownership handle. A fixed state machine limits
each probe to at most 32 Docker lifecycle operations.

Mock/fake tests validate this control plane and command order only. They do not prove
Linux namespace or cgroup behavior. Gate B2 must supply that empirical evidence.

## Build-context and image-provenance decision

The pinned upstream checkout stays detached, clean, and outside this repository.
`git archive` reads the exact commit into a fresh external build context; it does not
patch the checkout. The image build applies this separately tracked artifact:

```text
containers/sira-smoke/sira-immutable-model-routing.patch
SHA-256 4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed
```

The Containerfile is:

```text
containers/sira-smoke/Containerfile
SHA-256 b46f680c40aea0c65191896fc1674a6b4e00eca73b61f9b48ecbfdde13fb16b1
```

The canonical hash of all repository-owned staged build assets (Containerfile,
`.dockerignore`, patch, Gate A adaptation, entrypoint, fixtures, and static page) is
`d364c2356a4e73bc847f7aabdb272908e006eca0753bd1f74b3984ea1719b79a`.

Materialization is represented by the repository-owned
`containers/sira-smoke/materialization-plan.json`. Its control plane accepts only the
packet-authorized plan SHA-256, uses one monotonic 3,600-second deadline across its 51
single-attempt actions, caps streamed child output at 16,777,216 bytes, and records a
fresh hashed ledger. Before any download it requires the reviewed implementation to
be an ancestor, a clean worktree, and an exact four-file packet-only tree delta.
Before build it fail-closes on artifact size/digests, the pinned clean source HEAD,
staged-source equality, every mode-0444 repository input, uv.lock, build-context
allowlist, patch applicability, and the authorized context-evidence digest.

It verifies the upstream `uv.lock` hash, applies and checks the model-routing patch,
runs exactly `uv sync --frozen --extra eval --python 3.10` with HTTP retries and
managed-Python downloads disabled, and records the installed package manifest. The
build also carries the repository-owned Gate A runtime
adaptation SHA-256
`894783a47c19efc5e141a90a4dd63920b9440e1ef231aad5b2738b1f524bbbcd`.
The exact Playwright v1.39.0 upstream Dockerfile installs `git`, so patch application
does not depend on an unrecorded package-install step.

Post-build provenance is invalid until it equality-matches the raw browser record to
the fixture record retained before removal and requires the same attempt's successful
sealed cleanup record, both inspect snapshots, attempt UUID, and exact immutable image.
It records SHA-256 hashes of the browser record, pre-removal evidence, and cleanup seal,
in addition to the base index and platform digests,
Containerfile hash, source commit, patch hash, lock hash, installed-package-manifest
hash, Playwright version, Chromium revision and executable hash, target platform,
final image ID, and any observed repo digest. A local-only image normally has no repo
digest; the schema then requires the explicit status
`unavailable-local-build-not-pushed`. Execution still uses the immutable final image
ID, never the local tag.

## Gate B2 fixtures and limits

| Probe | CPU | Memory | PIDs | Workload wall | Output: payload/log/evidence | Private shm | each tmpfs | TERM |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Adversarial containment | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B: 8,388,608 / 2,097,152 / 6,291,456 | 67,108,864 B | 67,108,864 B | 1 s |
| Dummy-secret preflight | 1.000 | 536,870,912 B | 64 | 30 s | 16,777,216 B: 8,388,608 / 2,097,152 / 6,291,456 | 67,108,864 B | 67,108,864 B | 1 s |
| Browser-only local preflight | 2.000 | 2,147,483,648 B | 256 | 60 s | 33,554,432 B: 16,777,216 / 4,194,304 / 12,582,912 | 1,073,741,824 B | 134,217,728 B | 2 s |

The adversarial fixture forks children and grandchildren, creates a new session,
double-forks/reparents, ignores TERM, and spawns until the finite PID limit blocks it.
The browser fixture performs exactly one local navigation action to a bundled `file://`
page and one screenshot evidence capture, closes Playwright, and runs with
`--network none`. Neither fixture contains a provider client or a SiRA condition
command.

## Remaining Gate B2 blockers

1. No supported runtime is installed; installation needs explicit user authorization.
2. Only 12,029,374,464 bytes were free at `2026-08-09T04:45:07Z`. Repository
   storage policy requires at least 161,061,273,600 bytes (150 GiB) remain free. With
   a 12,884,901,888-byte (12 GiB) Gate B2 disk-growth cap, the pre-install floor is
   173,946,175,488 bytes (162 GiB). The current host fails that preflight.
3. Final image, package, Chromium executable, runtime client/server, and kernel
   containment identities are necessarily unknown until the authorized Gate B2 work.
4. The container control plane is ready for the three no-network probes. Live SiRA
   integration still requires a separately reviewed, non-host network policy and
   post-B2 authorization materialization; Gate B2 does not authorize a live request.

Gate B2 must not be authorized or started until blocker 2 is cleared. No runtime,
image, dependency, browser, container, or model action occurred in Gate B1.
