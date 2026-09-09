# T09 local container validation

Status: **partial development validation; final gate not qualified**. The separate
owner-authorized `gic-pr15-ci` Colima runtime now uses native ARM64/VZ with private
homes in an encrypted, ownership-enabled external APFS image. Shared Docker Desktop,
PostgreSQL, other projects' profiles and their disks are outside this task's access.
Do not apply the historical Desktop relocation instructions below as current authority.

The pinned dependency image built and an actual isolated containment smoke passed.
The contained dirty-candidate test now exercises retained source verification and
qualification; the complete joined transaction and final exact-commit parity gate
remain pending. See the existing implementation ledger for exact source/image/input
identities, startup policy failures and remediation, and preserved failure evidence.
The real outer VM/build/container operations are distinct from forbidden experimental
effects. No fixture result establishes historical replay or deployment readiness.

`scripts/ci/local_container.py --endpoint <local-socket> --record-root <fresh-root>`
prints the plan without daemon contact. `--preflight` records one bounded version
request using a fresh empty Docker configuration and the explicit Unix socket. It
does not start/reconfigure a runtime, use sudo, or inspect credentials. The returned
error cannot resolve the older Docker-info incident's unknown daemon contact.

The pinned recipe is `containers/local-ci/Containerfile`. Its Linux arm64 Python
3.11.14 and uv 0.11.7 digests were resolved from official public registries. Quarto
1.9.38 uses its published release size/SHA. These are immutable input pins; the
ledger separately records the observed development build identity. The currently
built image supplies dependencies; focused runs execute the updated runner from
its sealed input archive. It is not the final source-bound CI image.
`image-lock.json` leaves the final local image ID null. Base and current committed
head have the same `uv.lock` SHA. Build backends are separately hash-pinned because
they are not part of the project's dependency lock. No experimental image, SiRA
input, historical archive, source-preservation snapshot, credential, or model belongs
in this preparation context.

The launch argument builder fixes network none, non-root user, read-only root,
dropped capabilities, no-new-privileges, private IPC/default private PID, init,
no restart, disabled cores, and finite CPU/RAM/swap/PID/log/scratch limits. The
exact-ID lifecycle function has fake-channel tests for failure, interruption,
ambiguous creation, and wrong-ID refusal. Fake tests alone do not establish actual
kernel containment or cleanup; the ledger identifies the separate contained smoke. Limits follow the owner's ceilings;
the declared 4 GiB preparation budget is charged to its actual external backing
filesystem. The separate 8 GiB startup-filesystem headroom remains required.
The plan reports budget arithmetic separately from storage admission. The ledger
records measured GIC guest build growth and available storage for the development
build. Full-suite peak storage and final gate viability remain unproven. The
launcher remains partial; socket accessibility alone does not admit a build or
resolve the historical incident. Only explicit current owner authority permits
management of the separate GIC profile.

`guarded_python.py --journal <fresh-directory> -- -m pytest <nodes>` installs
`sitecustomize` before collection. `tests/conftest.py` also installs the same policy
for ordinary local test invocation. Python children inherit it even when their
caller replaces environment variables. Docker/sudo/SSH/acquisition/browser/GPU and
unknown processes are rejected before dispatch; real Python, inspected Git, pipes,
and private Unix IPC remain available. Denials are retained and a caught unexpected
denial causes nonzero process/gate exit. Named negative tests expect one exact denial.
This is an interface guard, not a sandbox for arbitrary native code. Final container
isolation must supply the separate OS boundary.

The host launcher requires the ignored local configuration
`.tools/local-ci-storage.json`; no missing configuration, volume, or destination
falls back internally. `ProjectStorage` reuses retained no-follow path checks and
the existing external free-space retention calculation, with freshly observed
volume/container identity. Historical installation plans are not invoked. Mount
device/root identity is checked at operation boundaries and in guarded Python
writes; a caught mount-loss error cannot yield a successful process exit.

For host component tests, invoke `guarded_python.py -- -m pytest <nodes>` with the
existing interpreter and source import path. It selects fresh external scratch,
guard journals, JUnit and pytest cache paths; caller-supplied internal output paths
are rejected. Python children retain the same storage policy even if their caller
replaces the environment. There are no shell-profile or global HOME changes.
Host tests that require exclusive ownership do not run on a noowners mount; they
remain required in the externally backed isolated Linux filesystem.

| Writer | Default destination relative to the bound project root |
|---|---|
| Disposable source/history checkouts | `workspaces/`; sealed inputs/build contexts in `ci/inputs/` |
| Candidate packages/extraction and host Python/pytest scratch | Fresh `tmp/p15-*` roots |
| uv/Python/pip/Deno/XDG/Ruff/mypy caches | Explicit children of `cache/`; fresh virtual environments under the run root |
| Host logs/JUnit/coverage and guard journals | Fresh `ci/results/p15-*` roots |
| Source preservation | Fresh `evidence/pr15/` children; source originals retained |
| Linux tool caches, test checkouts, Quarto rendering scratch/site | Declared `/work` filesystem; logs/export in `/results` |
| Image layers/build cache/container writable layers | GIC encrypted external runtime image; observed guest data disk |

Native Python 3.11.14 and uv 0.11.7 confirmed the selected temporary/cache/install
locations. Quarto was not available on the inspected host tool paths, so Deno/Quarto
cache and rendering behavior remains unexecuted; the container runner has explicit
cache/log paths and performs rendering only from its disposable checkout.

Historical Desktop placement diagnosis (superseded for this separate GIC CI lane):
The then-inspected Docker Desktop version was 4.87.0. The OS denied the narrow settings
read, so the observed default internal disk file is not certified as the active
backing store. The prior proposed owner action was **Settings → Resources → Advanced → Disk image
location** to select the prepared fresh project runtime-data destination and Apply,
after checking the currently displayed source and other workloads. This is the
[supported relocation mechanism](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/macfaqs/);
the worker does not move/symlink a disk, restart the runtime, or overwrite an existing
destination. Afterwards, actual external backing and guest space still need checking.

The inner runner invokes the existing `make ci-check BASE_SHA=... HEAD_SHA=...`;
it does not invoke `make format`. It remains unqualified. Required follow-up before
real execution: complete the sanitized build-context/export wiring, verify the full
Git history input closure, bound and verify result collection, qualify actual mount
permissions/limits and descendant cleanup, and preserve base/head JUnit with separate
revision environments through the existing comparator. Do not treat identical setup
failures as parity, add exclusions, or dispatch hosted CI as a fallback.

The source recipe, fake launcher checks, and host component tests establish no
Linux gate, native AMD64 equivalence, real experimental image import, browser/GPU
qualification, historical replay, scientific result, or deployment readiness. All
R1–R6 requirements and independent exact-head review remain outstanding until their
own evidence passes. See the existing implementation ledger and incident for actual
results and the publication hold's current read-only evidence.

Configuration references: [Docker run](https://docs.docker.com/engine/containers/run/),
[default seccomp](https://docs.docker.com/engine/security/seccomp/), and
[uv frozen sync](https://docs.astral.sh/uv/concepts/projects/sync/).


For the separate Colima lane, `colima_configuration`, `colima_environment` and
`validate_lima_isolation` keep the profile/homes and daemon explicit. The merged
Lima forwarding rules must include the explicit wildcard deny; Colima 0.10.3's
`none` spelling alone is insufficient with Lima 2.2. The supported GIC-only override
and masked bootstrap update services are verified before runtime reuse. No shared
profile, ambient Docker context, host mount, personal-key import or TCP API is used.
Machine paths and unlock material remain outside public configuration.

`GuestVolumes` and the existing exact-ID lifecycle use guest input/work/result
volumes. An owned preparation container seeds verified inputs; tests mount those
inputs read-only and execute non-root with no added capabilities. The preparation
container's narrow CHOWN capability is never added to a test container. The inner
runner supports explicitly labelled dirty snapshots only with named focused nodes;
the final gate requires an actual immutable commit. It creates a copied stdlib venv
interpreter before frozen offline sync so the retained owner check remains real.
These paths are still being qualified; they are not a completed general CI service.
