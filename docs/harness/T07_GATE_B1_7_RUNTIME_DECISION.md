# T07 Gate B1.7 runtime decision

Status: **runtime-candidate-rejected; no executable Gate B2a plan**

Prepared: 2026-08-09

Baseline: clean `phase-1/sira-smoke` commit
`87d0a759dce2cfb6a6be964b2cf462ae43a1d9c9`.

## Decision

The reviewed Colima v0.10.3 + Lima v2.2.0 topology does **not** replace Docker
Desktop. The terminal Gate B1.7 state is `runtime-candidate-rejected`.

The decisive storage conflict is source-proven at Lima commit
`de0816ea4bdc5267b428ab21025889b8dd785526`: `LIMA_HOME` is joined with `_config`,
the internal private-key filename is `user`, and the missing key is created with
`ssh-keygen -t ed25519 -N ""`. The exact immutable file/line bindings are retained in
`containers/sira-smoke/colima/source-observations.json`, SHA-256
`cbf9d975eccf86b90993206e50f483d04f1a0aa8357a42a59a826ed6965f2e75`.
Under the required topology the resulting `${LIMA_HOME}/_config/user` resolves to:

```text
/Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home/_lima/_config/user
```

The current approved UTDM APFS volume is mounted with `noowners`, and prior reviewed
storage policy says that it is not a confidentiality or exclusive-ownership boundary
and that no mutable secret-bearing cache may be placed there. A plaintext VM access
credential is not a sealed nonsecret artifact. No first-party source establishes a
supported way to move only Lima's required private identity to the Mac mini while
keeping the VM instance and disks under the required external `LIMA_HOME`; a symlink
split would also violate the no-symlink and complete-state binding contracts.

There are independent runtime-provenance blockers. Colima v0.10.3 supports exactly
one embedded arm64 Docker VM image, colima-core v0.10.4. Its bytes are strongly pinned,
but its build requests Docker Engine 29.5.2. On the 2026-08-09 observation date the
latest signed official Engine release was 29.7.2; exact signed releases 29.6.1
(2026-06-26), 29.6.2 (2026-07-16), and 29.7.0 (2026-07-30) each identify security
fixes. Their signed tag objects, peeled commits, dates, and release URLs are retained
in the source-observation record above. Colima's supported runtime updater runs a
versionless in-guest package update after startup. That cannot satisfy a current,
exact, pre-start runtime pin. The published VM image also lacks a resolved
installed-package manifest and executable hashes for Docker, containerd, runc, and
BuildKit.

Because these are material source and governance conflicts, this turn does not choose
CPU memory, VM disk, install, working-peak, or Mac mini operational-headroom values by
inference. It creates no executable replacement plan, plan ID, plan path, plan hash,
or authorization block.

The machine-readable decision is
`containers/sira-smoke/colima/candidate-decision.json`, SHA-256
`45632a34ac609b321facc14393336c3455caab646dd3ecf716e989e90046f4e0`.

## Exact authoritative inputs present

| Contract role | Exact repository path |
|---|---|
| Repository doctrine | `AGENTS.md` |
| Significant-work contract | `docs/PLANS.md` |
| Active Phase 1 execution plan | `docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md` |
| Decision log | `docs/DECISIONS.md` |
| Execution state | `docs/PROJECT_STATE.yaml` |
| Storage policy | `docs/STORAGE_POLICY.md` |
| Reproducibility policy | `docs/REPRODUCIBILITY.md` |
| Phase 1 readiness equivalent | `docs/readiness/PHASE_1_SMOKE_READINESS.md` |
| Gate A ledger | `docs/harness/T07_GATE_A_IMPLEMENTATION_LEDGER.md` |
| Gate B1 containment decision | `docs/harness/T07_GATE_B1_CONTAINMENT_DECISION.md` |
| Gate B1.5 storage decision | `docs/harness/T07_GATE_B1_5_STORAGE_TOPOLOGY_DECISION.md` |
| Gate B1.6 storage qualification | `docs/harness/T07_GATE_B1_6_DOCKER_STORAGE_QUALIFICATION.md` |
| Blocked Docker B2a packet | `docs/harness/T07_GATE_B2A_INSTALL_AUTHORIZATION_PACKET.md` |
| Protocol | `experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml` |
| Scientific configuration | `experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml` |
| Smoke profile | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml` |
| Reactive plan | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml` |
| Simulative plan | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml` |
| SiRA audit | `docs/audits/sira/UPSTREAM_AUDIT.md` |
| SiRA command contract | `docs/audits/sira/COMMAND_CONTRACT.yaml` |
| SiRA adapter | `src/giclab/harness/adapters/sira.py` |
| H2K preservation contract | `docs/H2K_OPTION_PRESERVATION.md` |
| Evidence retention | `experiments/EXP-0001-sira-simulative-vs-reactive/EVIDENCE_RETENTION_APPENDIX.yaml` |
| H2K regulation addendum | `docs/harness/sira/H2K_REGULATION_DECISION_ADDENDUM.yaml` |

The prompt's `docs/harness/PHASE_1_SMOKE_READINESS.md` spelling is absent; the exact
repository equivalent is the readiness path above.

## First-party source and release audit

All observations used small official release/source metadata or headers. No release,
bottle, VM, or container payload was downloaded.

| Component | Exact current candidate identity | arm64 bytes and digest | License/status |
|---|---|---|---|
| Colima | v0.10.3, commit `00f6c297e92a82c04a4ab507db0a61435650d7e8` | 15,656,320; SHA-256 `980ad8bf61a4ca370243f4cb41401a61276dcd2c2502bee7b9b86f9250169f34` | MIT; macOS 13+; Apple silicon supported |
| Lima | v2.2.0, signed tag object `867a7134156d04d59af41207d7a77a8e8c04eb99` to commit `de0816ea4bdc5267b428ab21025889b8dd785526` | 37,586,365; SHA-256 `bbdef91774885a0d05f7b048c4eb89ae2bcf3a0c252ae7ca7934e63df76d93c3` | Apache-2.0; documented VZ functional minimum macOS 13; asset deployment target unpublished |
| Docker CLI static archive | v29.7.2, signed tag object `9f4be4fde650841ec4c85cc48eee513f52c61a1e` to commit `a7dcaa6fdb6ed04aacbfdc76357fdae01605609e` | 18,920,558; no official SHA-256 or stronger digest published | Apache-2.0; direct method fails immutable-artifact rule |
| Docker Buildx | v0.36.1, signed tag object `29f401b496b1531d391cca6cabd8d30b6c478b66` to commit `1d8dde89b8aba914e05e45366770736fea1fd690` | direct arm64 asset 62,541,920; SHA-256 `214cdc36788602862dbc82b523d58648b4585c7b0ff95218b0817c44db5573d7` | Apache-2.0; required only for future B2b build |
| Colima VM image | colima-core v0.10.4, commit `078088ada3cce8835b8c42710ab44d17a935b195` | 332,354,401; SHA-256 `1fc0354f4f99734ce3886628cc7af8b0437c1a1d391b126bd09cba0df35ee53f`; SHA-512 `32242674b046b5057e60c4aba334b51e3665f05412cda89ed081cc2de153ae5c41f6b105b5c442cbe48d78e2cc21e9ba1950e406b6fb4fc2fd1dd2259240abbd` | Ubuntu/package-specific aggregate; builder repository MIT; embeds Docker request 29.5.2 |

Exact release assets:

- `https://github.com/abiosoft/colima/releases/download/v0.10.3/colima-Darwin-arm64`
- `https://github.com/lima-vm/lima/releases/download/v2.2.0/lima-2.2.0-Darwin-arm64.tar.gz`
- `https://download.docker.com/mac/static/stable/aarch64/docker-29.7.2.tgz`
- `https://github.com/docker/buildx/releases/download/v0.36.1/buildx-v0.36.1.darwin-arm64`
- `https://github.com/abiosoft/colima-core/releases/download/v0.10.4/ubuntu-24.04-minimal-cloudimg-arm64-docker.raw.gz`

The native VZ path needs neither QEMU, Rosetta, `socket_vmnet`, Kubernetes, Compose,
credential helpers, nor Lima's non-native additional guest-agent archive. Docker CLI
is required for `runtime: docker`; Buildx is required only in B2b.

Primary sources:

- Colima release: <https://api.github.com/repos/abiosoft/colima/releases/tags/v0.10.3>
- Colima directories/fallback/cache, commit-pinned:
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/config/files.go#L46-L145>
- Colima initial temporary Lima YAML, commit-pinned:
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/environment/vm/lima/lima.go#L92-L118>
- Colima empty-mount behavior and exact `--mount none` conversion, commit-pinned:
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/environment/vm/lima/yaml.go#L380-L405> and
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/cmd/start.go#L245-L300>
- Colima SSH/mount/disk-image defaults, commit-pinned:
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/embedded/defaults/colima.yaml#L217-L251>
- Colima Docker context creation, commit-pinned:
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/environment/container/docker/context.go#L17-L35>
- Colima versionless runtime update, commit-pinned:
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/environment/container/docker/docker.go#L147-L155> and
  <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/util/debutil/debutil.go#L15-L86>
- Colima image lock: <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/embedded/images/images.txt>
- Colima disk validation: <https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/environment/vm/lima/disk.go>
- colima-core release: <https://api.github.com/repos/abiosoft/colima-core/releases/tags/v0.10.4>
- colima-core Docker build: <https://github.com/abiosoft/colima-core/blob/v0.10.4/scripts/image.sh>
- Lima release: <https://api.github.com/repos/lima-vm/lima/releases/tags/v2.2.0>
- Lima `LIMA_HOME`/config resolution, commit-pinned:
  <https://github.com/lima-vm/lima/blob/de0816ea4bdc5267b428ab21025889b8dd785526/pkg/limatype/dirnames/dirnames.go#L18-L48>
- Lima key filename, commit-pinned:
  <https://github.com/lima-vm/lima/blob/de0816ea4bdc5267b428ab21025889b8dd785526/pkg/limatype/filenames/filenames.go#L10-L25>
- Lima key creation/use, commit-pinned:
  <https://github.com/lima-vm/lima/blob/de0816ea4bdc5267b428ab21025889b8dd785526/pkg/sshutil/sshutil.go#L275-L390>
- Lima hard-coded user cache, commit-pinned:
  <https://github.com/lima-vm/lima/blob/de0816ea4bdc5267b428ab21025889b8dd785526/pkg/downloader/downloader.go#L58-L100>
- Lima VZ requirements: <https://lima-vm.io/docs/config/vmtype/vz/>
- Docker Engine signed releases:
  <https://github.com/moby/moby/releases/tag/docker-v29.6.1>,
  <https://github.com/moby/moby/releases/tag/docker-v29.6.2>,
  <https://github.com/moby/moby/releases/tag/docker-v29.7.0>, and
  <https://github.com/moby/moby/releases/tag/docker-v29.7.2>
- Homebrew bottle contract: <https://docs.brew.sh/Bottles>
- Apple Target Disk Mode: <https://support.apple.com/guide/mac-help/transfer-files-mac-computers-target-disk-mode-mchlp1443/mac>
- Apple Virtualization: <https://developer.apple.com/documentation/virtualization>

## Installation-method comparison

| Method | Immutable identity | Numeric footprint | Rollback/isolation | Result |
|---|---|---|---|---|
| Exact upstream release assets in an isolated user-owned prefix | Colima, Lima, VM image, and Buildx have published hashes; Docker CLI does not | Required B2a host archives Colima + Lima total 53,242,685 compressed bytes; B2b Buildx raises that host-archive total to 115,784,605; Docker is another 18,920,558 bytes but unhashable from published metadata; extracted peaks unpublished | An isolated versioned prefix could be atomically selected and removed, but the Docker digest gap prevents a closed lock | Rejected |
| Hash-locked Homebrew bottles from homebrew-core commit `fb44be0e4d23468758c9a1877adaae2511c353ed` | All required B2a bottles have exact blob SHA-256 identities | B2a: 51,085,344 downloaded and 119,618,599 installed; Buildx later adds 21,141,264 downloaded and 63,164,585 installed | Direct extraction to one isolated prefix is stronger than `brew install`; standard `brew install` mutates shared Cellar/link/cache/receipt state | Stronger audited method, but not selected or authorized because the runtime candidate is rejected |

Exact B2a bottle blobs are Colima
`sha256:a9dfd1fa0a4aee62fef75974f39f174e4da774f7ba495c43dd0bcc23633381b8`,
Lima `sha256:9dfb60d4c7d0c6721eee679ab188d8b502ad61d1063c9914b830b66ce795b4a4`,
and Docker CLI
`sha256:b061dbca62960f6bbf16b983b156cb960bf810e678e14c6bd366b58506eb4f1a`.
Buildx is
`sha256:df6823aae7eb4f2b9b70e2282f24c5b37f204483b6c2cb2f75c3485b7e4decbb`.

## State relocation and candidate configuration

`COLIMA_HOME` relocates the profile, `_store`, Lima instance, root disk, and named
runtime data disk only if the directory already exists. If it does not, Colima
silently falls back to the normal home/XDG location. Separate bindings are required
for `COLIMA_CACHE_HOME`, `LIMA_HOME`, `DOCKER_CONFIG`, and `TMPDIR`. Lima's macOS cache
is hard-coded to `~/Library/Caches/lima`; source says local image inputs are not cached,
but no exact-pair first-start test proves a zero delta. Colima also writes a temporary
Lima YAML through `os.TempDir()`.

`autoActivate: false` prevents Docker context activation but not context creation.
`sshConfig: false` is required to prevent `~/.ssh/config` mutation. `mounts: []` is
unsafe because it can mean a writable host-home mount; exact no-mount behavior is the
CLI value `--mount none`, with `--template=false`. `forceDiskImage` must be false,
`binfmt` false, and Rosetta false.

The evaluated candidate is therefore:

```yaml
status: rejected-nonexecutable
profile: giclab-t07
runtime: docker
vm_type: vz
arch: host  # resolves arm64 on the observed M4
kubernetes: false
network_address: false
port_forwarder: none
auto_activate: false
ssh_config: false
template: false
mounts: none
binfmt: false
rosetta: false
force_disk_image: false
cpu: 2
memory_gib: null  # no source-and-host-qualified bound
disk_gib: null    # no source-and-storage-qualified bound
colima_home: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home
colima_cache_home: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-cache
lima_home: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home/_lima
executable: false
```

The conservative Lima socket-length probe path is 102 bytes, below the documented
exclusive 104-byte macOS limit. Socket length is not a blocker.

## Current storage and host observation

The following read-only observation was completed at `2026-08-09T19:05:39Z` and is
not durable authorization evidence:

| Field | Exact observation |
|---|---|
| Host | Mac mini, Apple M4, arm64, 16 GiB RAM, macOS 26.5.1 build 25F80 |
| Runtime inventory | Colima, limactl, Docker CLI, Buildx, and QEMU absent; Homebrew 6.0.12 present |
| External mount | `/Volumes/Macintosh HD - Data`; APFS; local UTDM block exposure; read-write; unlocked; external; `noowners` |
| Data UUID | `8478609D-FA37-4ED5-875D-47AE912B9151` |
| Physical-store UUID | `7904A6F1-F483-4ED7-9E34-BFECAB31C63E` |
| External capacity/free | 1,000,240,963,584 / 783,116,140,544 bytes |
| Retained-free floor | `max(150 GiB, ceil(20%))` = 200,048,192,717 bytes |
| Current surplus over retained floor | 583,067,947,827 bytes |
| Mac mini Data capacity/free | 245,107,195,904 / 54,452,396,032 bytes |

Known B2a bottle-install, exact rollback-copy, and active-evidence terms total at least
306,346,062 Mac mini bytes. That is not an operational floor: exact extraction/temp
peaks and a separately justified host-operational headroom term remain unresolved.
The B2a bottle plus VM-image compressed downloads total 383,439,745 bytes if staged
externally, but the raw-image expansion, root/runtime disk allocation, and failure
staging peaks are unknown. Consequently:

- Mac mini system floor: `null`;
- runtime-install incremental cap: `null`;
- VM-creation and VM-disk caps: `null`;
- B2b pull/build/probe/archive aggregate disk caps: `null`.

No null value is converted to an authorization.

## Network and first-start boundary

Audited future artifact endpoints are:

- GitHub metadata/releases: `api.github.com`, `github.com`,
  `release-assets.githubusercontent.com`;
- pinned Homebrew blobs: `ghcr.io/token`, `ghcr.io`;
- Homebrew metadata/source only if reverified: `formulae.brew.sh`,
  `github.com/Homebrew/homebrew-core`, `raw.githubusercontent.com`;
- rejected standalone Docker CLI method: `download.docker.com`.

An exact local VM image removes an intended Lima image download. It does not close the
first-start network set: `network_address: false` disables a routable guest address,
not guest outbound NAT, and source inspection does not prove zero unsolicited guest
traffic. No exact first-start endpoint allowlist is therefore available.

## Minimal qualification design and containment boundary

If the candidate had passed the source decision, B2a would have contained only:
install exact isolated binaries; create one externally bound profile; start an empty
VM/runtime; capture VM/runtime/image/profile identities; stop; user disconnect and
reconnect the UTDM volume; freshly rebind both UUIDs and held descriptors; restart the
same profile; prove identical state; stop; seal and verify evidence. It would not pull
Playwright, build SiRA, create a workload container, access a secret, browse, or call
an API.

This is a requirements sequence, not an executable plan. Missing numeric limits,
mutable secret placement, and runtime provenance make rendering argv arrays unsafe.

Any future B2b workload container still requires a private PID namespace and private
cgroup namespace; no privileged/host PID/network/IPC/runtime-socket mode;
`cap-drop=ALL`; no-new-privileges; read-only root; bounded tmpfs; finite CPU, memory,
PID, wall, output, and disk limits; immutable image ID; restart `no`; lifecycle by
immutable container ID; and an exact VM-level last-resort stop. The host process list
is never the authoritative containment handle.

## Implemented control-plane repairs

- `src/giclab/harness/sira_colima.py` implements the strict rejected/ready decision
  loader, fresh observation plus held no-follow mount/path descriptors across one
  sensitive action, explicit descriptor ownership transfer, a one-second consume-to-
  run bound, and mandatory pre/post-action revalidation on success or failure. Its
  typed single-use zero-retry rollback executor accepts only private-issuer receipts
  minted by exclusive creation of exact `colima-runtime`, `colima-cache`, or profile
  roots. It also requires attempt/device/inode identity, a hash-bound Colima
  executable, and one exact stop argv template; `/`, sealed/historical roots,
  caller-asserted freshness, arbitrary commands, stale identities, and evidence
  removal are rejected.
- `src/giclab/harness/sira_storage.py` now renders/parses one bounded NUL-delimited
  macOS `lsof +w -V` writer probe, including newline/NUL field framing and the real
  exit-1 all-no-use diagnostic set on stdout or stderr. Zero writers requires a
  positive set containing the exact source and only source descendants; every
  ambiguous status/diagnostic fails closed. The supervisor-only in-process seal,
  immutable-copy, and accounting driver rejects structural lease fakes and requires
  an authentic lease holding the exact source and archive-parent paths. It has no
  standalone execution surface. Local sources and failed partial archives are
  retained.
- `schemas/runtime-candidate-decision.schema.json` and
  `schemas/runtime-rollback-evidence.schema.json` make the decision and rollback
  evidence machine-readable.

Mocks and local fixtures validate this control plane only. They do not prove VZ,
Linux namespaces, cgroups, Docker cleanup, UTDM reconnect behavior, or kernel
containment.

Typed fail-state behavior is exact and conservative:

| Failure | Required behavior |
|---|---|
| Partial binary installation | Preserve logs; remove only an issuer-bound, exclusively created exact `colima-runtime` or `colima-cache` root; never mutate shared Homebrew state. |
| Failed VM creation/start | Capture exact profile/VM/data-disk identities; stop only the issuer-bound exact profile through the hash-bound Colima executable; preserve profile/disk state for review because this rejected candidate grants no profile-removal operation. |
| Missing or wrong remount | Do not redirect or recreate state internally; reject all storage-sensitive calls and preserve local evidence. |
| Profile drift | Stop, record drift, preserve the profile and evidence; do not delete uncertain state. |
| Residual process/container | Address only an immutable owned VM/container identity; a broad host/runtime cleanup is prohibited. |
| Evidence-copy failure | Retain the sealed Mac mini source and partial destination evidence; never delete the source before independent destination hash verification. |

## Scientific and authority boundary

The following remain unchanged:

```text
EXP-0001
PLAN-EXP0001-SMOKE
SIRA-REACTIVE first
SIRA-SIMULATIVE second
gpt-4o-2024-11-20
interpretation_allowed: false
pilot unauthorized
cloud mutation false
training false
```

No real `SIRA_API_KEY` is needed in B2a. Any future B2b may use only the public dummy
canary. Gate C requires fresh authorization.

## Terminal recommendations

The runtime candidate is rejected. Per the governing decision rule, no further B1.x
design gate is created. The next user decision must select, without automatic
preference, one of:

1. a directly attached local external SSD on the Mac mini;
2. a separately approved Linux execution host;
3. a deliberately less strict containment/storage-confidentiality contract approved
   as a scientific-governance change.

The old Docker Desktop V1 plan and packet remain intact as superseded, blocked
provenance. Gate B2a, Gate B2b, Gate C, both SiRA conditions, the pilot, cloud
mutation, training, and paid compute remain unauthorized.

No installation, download, pull, build, VM/container/browser launch, provider/model
API call, secret access, SiRA execution, scientific-field mutation, or evidence
deletion occurred.
