# T07 Gate B2a Colima authorization packet

Status: **runtime candidate rejected; packet is non-executable and authorizes nothing**

Prepared: 2026-08-09

## Exact repository and decision identity

- Branch: `phase-1/sira-smoke`.
- Gate B1.7 baseline:
  `87d0a759dce2cfb6a6be964b2cf462ae43a1d9c9`.
- Gate B1.7 clean decision commit: reported at handoff after commit; a Git document
  cannot contain its own commit SHA.
- Decision state: `runtime-candidate-rejected`.
- Candidate record:
  `containers/sira-smoke/colima/candidate-decision.json`.
- Candidate-record SHA-256:
  `45632a34ac609b321facc14393336c3455caab646dd3ecf716e989e90046f4e0`.
- Source-observation record:
  `containers/sira-smoke/colima/source-observations.json`, SHA-256
  `cbf9d975eccf86b90993206e50f483d04f1a0aa8357a42a59a826ed6965f2e75`.
- Executable replacement plan ID: **none**.
- Executable replacement plan path: **none**.
- Executable replacement plan SHA-256: **none**.
- Authorization reference/block: **none**.

No command array, install action, call allowance, or authorization can be inferred
from the audited artifact list below.

## Current host/runtime observation

Read-only observation completed at `2026-08-09T19:05:39Z` found:

```text
Host: Mac mini, Apple M4, arm64
macOS: 26.5.1 build 25F80
RAM: 17179869184 bytes
Colima: absent
limactl: absent
Docker CLI: absent
Buildx: absent
QEMU: absent
Homebrew: 6.0.12
```

No client/server version or runtime architecture exists because no runtime is
installed or running.

## Audited, not-authorized artifacts

| Component | Exact source identity | Exact distribution identity | Download bytes | Installed bytes |
|---|---|---|---:|---:|
| Colima | v0.10.3 / `00f6c297e92a82c04a4ab507db0a61435650d7e8` | Homebrew bottle SHA-256 `a9dfd1fa0a4aee62fef75974f39f174e4da774f7ba495c43dd0bcc23633381b8` | 4,152,160 | 10,579,823 |
| Lima | v2.2.0 / `de0816ea4bdc5267b428ab21025889b8dd785526` | Homebrew bottle SHA-256 `9dfb60d4c7d0c6721eee679ab188d8b502ad61d1063c9914b830b66ce795b4a4` | 37,584,563 | 80,920,034 |
| Docker CLI | v29.7.2 / `a7dcaa6fdb6ed04aacbfdc76357fdae01605609e` | Homebrew bottle SHA-256 `b061dbca62960f6bbf16b983b156cb960bf810e678e14c6bd366b58506eb4f1a` | 9,348,621 | 28,118,742 |
| Buildx, B2b only | v0.36.1 / `1d8dde89b8aba914e05e45366770736fea1fd690` | Homebrew bottle SHA-256 `df6823aae7eb4f2b9b70e2282f24c5b37f204483b6c2cb2f75c3485b7e4decbb` | 21,141,264 | 63,164,585 |
| Colima Docker VM image | colima-core v0.10.4 / `078088ada3cce8835b8c42710ab44d17a935b195` | SHA-256 `1fc0354f4f99734ce3886628cc7af8b0437c1a1d391b126bd09cba0df35ee53f`; SHA-512 `32242674b046b5057e60c4aba334b51e3665f05412cda89ed081cc2de153ae5c41f6b105b5c442cbe48d78e2cc21e9ba1950e406b6fb4fc2fd1dd2259240abbd` | 332,354,401 | unpublished raw/allocated peak |

B2a bottle totals excluding Buildx are 51,085,344 downloaded and 119,618,599
installed bytes. Exact bottle extraction to one isolated versioned prefix would be
stronger than either the unhashable upstream Docker CLI archive or a shared-state
`brew install`. This comparative result is not an installation selection or
authorization.

The exact bottle endpoints would be the four digest-addressed `ghcr.io/v2/homebrew`
blob URLs recorded in the candidate JSON. GitHub release assets redirect from
`github.com` to `release-assets.githubusercontent.com`. `ghcr.io/token` is required
for bottle authentication. The standalone Docker method would contact
`download.docker.com` but is rejected because no official digest is published.

## Candidate topology and rejected roots

```text
profile: giclab-t07
instance: colima-giclab-t07
runtime: docker
vm type: vz
architecture: host -> arm64
CPU: 2
memory: unresolved; null
disk: unresolved; null
COLIMA_HOME: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home
COLIMA_CACHE_HOME: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-cache
LIMA_HOME: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home/_lima
Lima private key: /Volumes/Macintosh HD - Data/GIC-Lab/t07/colima-home/_lima/_config/user
```

These roots are reviewed candidates, not approved writable roots. They must not be
created by this packet.

The source-complete no-mount configuration would additionally require Kubernetes,
network-address, auto-activate, SSH-config mutation, template inheritance, binfmt,
Rosetta, and force-disk-image all disabled; port forwarder `none`; and exact CLI
`--mount none`. A plain empty YAML mount list is not equivalent.

## Storage floors and numeric-cap result

Current read-only observations:

| Volume | Capacity | Free | Required retained floor |
|---|---:|---:|---:|
| MacBook Pro APFS over UTDM | 1,000,240,963,584 | 783,116,140,544 | 200,048,192,717 |
| Mac mini Data | 245,107,195,904 | 54,452,396,032 | unresolved operational floor |

Stable external inputs to reverify are exact mount
`/Volumes/Macintosh HD - Data`, APFS Data UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, external UTDM classification,
read-write/unlocked state, and no symlink traversal. No internal fallback is allowed.

Known Mac mini installed-binary, exact rollback-copy, and active-evidence terms total
306,346,062 bytes. The total is not a floor. Exact extraction/temp peaks and a
separately justified host-operational headroom term are missing. External compressed
B2a artifacts total 383,439,745 bytes, but raw-image expansion, root/runtime disk
allocation, and failure staging are unmeasured.

Therefore every proposed executable aggregate remains null:

| Required B2a cap | Value |
|---|---:|
| Runtime-install internal/external incremental bytes | null |
| VM-creation working bytes | null |
| VM root disk bytes | null |
| Container-runtime data disk bytes | null |
| Aggregate download bytes | null |
| Aggregate Mac mini disk bytes | null |
| Aggregate external disk bytes | null |
| Aggregate wall seconds | null |
| Aggregate child/tool calls | null |
| Aggregate output bytes | null |
| Automatic retries | 0, but no calls are authorized |

A null is a blocker, never an unlimited value.

## Secret and state blocker

Gate B2a would need no `SIRA_API_KEY`. Nevertheless, Lima itself creates a private SSH
identity at `${LIMA_HOME}/_config/user`. The required external home places that
credential on a volume whose current mount has ownership disabled. Existing approved
policy permits sealed nonsecret retention there and explicitly rejects mutable
secret-bearing cache state. This conflict cannot be fixed with mode bits, because
ownership is non-authoritative on the reviewed mount.

Additional state not captured by `COLIMA_HOME` alone is:

- separate `COLIMA_CACHE_HOME`;
- Docker context under separate `DOCKER_CONFIG`, even with auto-activation false;
- Colima's initial YAML under `os.TempDir()`;
- Lima's hard-coded macOS cache under `~/Library/Caches/lima`;
- optional `~/.ssh/config` mutation unless `sshConfig: false`.

Colima also ignores a missing `COLIMA_HOME` value and silently falls back. A future
guard would have to precreate it, hold its verified mount identity, reject internal
cache/context/temp growth, and reobserve before and after each sensitive action.

## Runtime provenance blocker

The exact VM-image bytes can be pinned before startup with `forceDiskImage=false`.
Their Docker Engine request is 29.5.2, not current 29.7.2, and the current line contains
intervening security fixes. Colima's supported updater performs a mutable,
versionless, post-start package update. The release publishes neither the exact
installed package manifest nor Docker/containerd/runc/BuildKit executable hashes.
Using an unrecognized custom image requires unsupported force mode or a separately
reviewed Colima rebuild.

First startup is not a closed network contract either: a local disk image removes the
intended image download, but `network_address: false` does not disable outbound guest
NAT and source inspection does not establish an exact zero-or-allowlisted endpoint
set.

## Implemented rollback, guard, seal, and cleanup control plane

Gate B1.7 added deterministic primitives but did not execute them:

- a sensitive action consumes a single-use five-second guard only after fresh volume
  observation, explicitly transfers its no-follow mount/path descriptors, and must
  begin within one second; it reobserves/revalidates before and after success or
  failure, and neither the guard nor a failed operation can reuse/close the lease;
- typed rollback requires private-issuer receipts minted only by exclusive creation
  of the exact dedicated runtime/cache/profile roots, plus attempt/device/inode
  identity, a hash-bound Colima executable, and the exact stop template; it executes
  each action once, stops on first failure, records zero retries, rejects `/`, sealed
  or historical roots, caller-asserted freshness, and arbitrary commands, and
  prohibits evidence deletion;
- the writer probe is one shell-free, 10-second, 262,144-byte `lsof +w -V -F0`
  operation; zero writers requires a positive all-no-use set containing the source
  and only its descendants, while ambiguous exit-1/error output fails closed;
- the supervisor-only seal driver requires an authorized immutable plan, adjacent plan
  guard, authentic held storage lease for the exact source/archive paths, zero open
  writers, bounded evidence, fsync, source immutability, one-way copy, destination
  re-read/hash verification, copy record, and local-source retention;
- partial installs, partial archives, failed copies, uncertain profiles, and local
  evidence are preserved unless an issuer-bound exclusive-create receipt authorizes
  removal of exactly the dedicated runtime/cache root; profile removal is unsupported;
- no rollback may prune a runtime, enumerate/delete unrelated host descendants, delete
  prior evidence, or redirect to internal storage.

Mocks and local temporary files validate these control-plane properties only. No live
VM, runtime, UTDM reconnect, cross-volume seal, container namespace, or cgroup claim is
made.

## Exact blockers that stop authorization

1. Required external `LIMA_HOME` contains a Lima SSH private key, but the reviewed
   `noowners` volume is not approved for mutable secret-bearing state.
2. The only supported pinned Colima arm64 Docker image contains Engine 29.5.2 rather
   than the current 29.7.2 security line.
3. Colima's supported runtime update is mutable, versionless, and post-start.
4. Exact in-image runtime package and executable identities are unpublished.
5. Lima's hard-coded internal-cache non-use is unproven for this exact pair.
6. The first-start network endpoint set is not closed.
7. No first-party release evidence tests exact Colima v0.10.3 with Lima v2.2.0.
8. Extracted/temporary/VM-disk peaks are unmeasured without a prohibited payload/build
   probe.
9. The Mac mini operational-headroom term remains unjustified, so the system floor is
   null.

## Authorization result

There is no ready-to-copy Gate B2a authorization block. Providing one would violate
the State 2 decision rule. This packet cannot authorize installation, extraction,
download, profile/root creation, VM start, runtime start, disconnect/reconnect,
container/image/browser activity, secret access, API use, either SiRA condition, Gate
B2b, Gate C, the pilot, cloud mutation, training, or paid compute.

The next user decision must select one of these alternatives without automatic
preference:

1. a directly attached local external SSD on the Mac mini;
2. a separately approved Linux execution host;
3. a deliberately less strict containment/storage-confidentiality contract approved
   as a scientific-governance change.

No further B1.x local-runtime design gate is proposed.
