# T07 Gate B1.7 implementation ledger

Status: **runtime-candidate-rejected; Gate B1.7 complete; no Gate B2a authority**

Source contract: current-turn user instruction, “T07 Gate B1.7 — Replace the blocked
Docker Desktop path with a simpler Colima/Lima runtime,” received 2026-08-09. The
instruction is authoritative conversation state and has no repository-local source
file to hash.

Baseline: clean `phase-1/sira-smoke` commit
`87d0a759dce2cfb6a6be964b2cf462ae43a1d9c9`.

## Definition of done

| ID | Required outcome | Status | Evidence |
|---|---|---|---|
| T07-B17-01 | Preserve the required branch ancestry, prior Gate A/B1/B1.5/B1.6 evidence, and all locked scientific fields. | met | Started from exact clean commit; prior artifacts remain; five locked inputs are byte-identical with expected hashes. |
| T07-B17-02 | Perform no prohibited installation, download, VM/container/browser/API/secret/SiRA/cloud/scientific mutation. | met | Only small official metadata/source reads, host inspection, local code/tests, and notebook rendering occurred. |
| T07-B17-03 | Record every authoritative input at the exact repository path actually present. | met | Runtime decision contains the complete exact-path table and names the readiness equivalent. |
| T07-B17-04 | Audit exact Colima, Lima, Docker CLI/plugin/helper, VM-image, and in-VM runtime release identities from first-party sources. | met | Versions, tags/commits, URLs, bytes, digests, licenses, compatibility, helpers, VM image, and Engine 29.5.2 recorded. |
| T07-B17-05 | Compare exact release assets with hash-locked Homebrew bottles and choose only if immutable, rollback-complete, and numerically bounded. | met | Direct Docker archive lacks a digest; exact isolated bottle extraction is stronger than `brew install`, but no method is selected because the runtime is rejected. |
| T07-B17-06 | Prove or reject complete `COLIMA_HOME`/`LIMA_HOME`/cache relocation, including internal-home and temporary state. | met | Source proves silent missing-home fallback, separate cache/context/temp state, hard-coded Lima cache, and required private key under external `LIMA_HOME`; candidate rejected. |
| T07-B17-07 | Prove or reject the UTDM APFS volume as Lima-local storage without generalizing beyond the observed topology. | met | Fresh APFS/UTDM/UUID/read-write observation is structurally local/non-NFS, but `noowners` contradicts the required Lima credential and storage policy. |
| T07-B17-08 | Enumerate every future install/first-start endpoint and artifact, and reject any silently mutable VM/runtime input. | met | Exact release/bottle endpoints recorded; outbound first-start endpoint set and mutable post-start updater remain blockers. |
| T07-B17-09 | Recompute the external retained-free floor and derive a non-null, source/host-grounded Mac mini system floor. | blocked | External floor is exactly 200,048,192,717 bytes; internal known subtotal is 306,346,062 bytes, but extraction peaks and justified host headroom remain unknown. State 2 forbids inventing a floor. |
| T07-B17-10 | Define numeric incremental caps for install, VM creation/disk, pull, build, probe evidence, and sealed copy. | blocked | Artifact/download and existing fixture terms are exact; raw expansion, VM/runtime disks, and host peaks are unknown. Null caps are explicit rejection blockers, not unlimited values. |
| T07-B17-11 | Bind exact external identity/path roles, reject symlinks/internal fallback, and freshly re-observe identity through a held descriptor before sensitive actions. | blocked | The primitive explicitly transfers authentic no-follow mount/path descriptors, requires execution within one second, and reobserves/revalidates before and after the action; seal/copy binds exact source/archive paths. No executable Colima action or exact root map exists in State 2, so live Colima-root enforcement is deliberately unclaimed. |
| T07-B17-12 | Design the minimal no-workload B2a VM create/stop/remount/restart qualification with exact identity and cleanup evidence. | blocked | Requirements sequence is documented, but the terminal State 2 rule prohibits argv/plan rendering for the rejected runtime. |
| T07-B17-13 | Keep B2b separate and preserve the full future workload-containment contract without creating B2b authority. | met | `T07_GATE_B2B_REQUIREMENTS.md` has fixed fixture limits and policies but no plan/argv/identity/hash/authorization. |
| T07-B17-14 | Implement a typed, exact-resource rollback executor with fail states and no broad prune/evidence deletion. | met | Single-use zero-retry executor accepts only issuer-bound receipts minted by exclusive creation of exact runtime/cache/profile roots, plus attempt/device/inode identity, hash-bound executable, and an allowlisted exact stop argv; `/`, sealed/historical roots, forged freshness, arbitrary commands, stale identity, and evidence deletion fail closed. |
| T07-B17-15 | Implement an authorized in-process writer-probe/seal/copy driver that retains the local source and verifies both sides. | met | Real macOS newline/NUL and exit-1 stdout/stderr all-no-use fixtures, exact-source/descendant diagnostic validation, explicit held-descriptor transfer, one-second start bound, pre/post checks, concrete issuer/path binding, and supervisor-only seal/copy; no live cross-volume claim. |
| T07-B17-16 | Preserve EXP-0001, plan/order/model/interpretation and execution/pilot/cloud/training prohibitions. | met | Locked hashes remain protocol `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c`, config `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d`, profile `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425`, reactive `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018`, simulative `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436`; permissions remain false. |
| T07-B17-17 | Apply the binary decision rule: executable replacement only if every immutable identity, cap, floor, pin, rollback, seal, and material source fact is resolved; otherwise reject the candidate. | met | Machine-readable State 2 record SHA-256 `45632a34ac609b321facc14393336c3455caab646dd3ecf716e989e90046f4e0`; executable binding is null. |
| T07-B17-18 | Mark Docker Desktop V1 plan and packet as superseded blocked provenance without deleting or rewriting historical evidence. | met | The old plan is byte-unchanged; the packet has only an additive successor notice. Old plan hash remains unchanged. |
| T07-B17-19 | Produce all four required documents and the Colima directory; create an executable plan only in State 1. | met | All required outputs exist; Colima directory contains only README, rejected candidate record, and non-executable source-observation record. |
| T07-B17-20 | Run focused source/parser, storage/guard, plan/schema, rollback/seal, repository validation, format/lint/strict typing, and a real full check using portable Quarto 1.9.38. | met | Post-repair focused 69-test gate and expanded 107-test gate pass; final full gate passes formatting, lint, strict typing, 450 tests, repository validation, 16-page Quarto render, and site validation. |
| T07-B17-21 | Obtain independent spec-conformance review, repair findings, and repeat the full post-review gate. | met | Review findings covered lease ownership/freshness, real `lsof` framing/status streams, forged/broad rollback ownership, structural-fake lease, ready-schema, source binding, bottle records, arithmetic, ledger, decision log, and active plan. All were repaired; independent rereview is clean and post-review full gate passes. |
| T07-B17-22 | Commit the reviewed decision on `phase-1/sira-smoke` and leave the worktree clean. | met | This ledger is included in the Gate B1.7 commit on the required branch; the exact commit SHA and post-commit clean-tree proof are reported at handoff because a commit cannot embed its own identity. |

## Pre-edit gates

- Branch: `phase-1/sira-smoke`.
- HEAD: `87d0a759dce2cfb6a6be964b2cf462ae43a1d9c9`.
- Required ancestor: exact HEAD.
- Worktree: clean.
- Portable Quarto: `/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`,
  version `1.9.38`.
- No runtime, VM, container, image, browser, provider API, secret, SiRA condition,
  scientific-field, cloud, or paid-compute action occurred before editing.

## Review and closeout evidence

- Candidate decision: `runtime-candidate-rejected`, SHA-256
  `45632a34ac609b321facc14393336c3455caab646dd3ecf716e989e90046f4e0`;
  no executable plan binding.
- Commit-qualified source observation record: SHA-256
  `cbf9d975eccf86b90993206e50f483d04f1a0aa8357a42a59a826ed6965f2e75`.
- Current host inspection: arm64 Apple M4, macOS 26.5.1 build 25F80; Colima,
  limactl, Docker, Buildx, and QEMU absent; external UUIDs and `noowners` reconfirmed.
- Focused source/parser/storage/guard/rollback/seal/schema suite after review repairs:
  69 passed.
- `make validate` and `git diff --check`: passed.
- Pre-review full gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — passed; formatting and lint clean, strict typing clean across 25 source files, 446
  tests passed, repository validation passed, Quarto 1.9.38 rendered 16 pages, and
  rendered-site validation passed. Quarto emitted its existing output-path warnings but
  returned success and site validation passed.
- Independent review found and drove the repairs summarized in T07-B17-21. The final
  rereview is clean: real macOS writer-probe count zero, focused 69 and full pytest 450
  passed, repository validation/diff hygiene passed, scientific inputs and historical
  Docker plan remained byte-identical, and the terminal control planes aligned.
- Post-review full gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — passed; formatting and lint clean, strict typing clean across 25 source files, 450
  tests passed, repository validation passed, Quarto 1.9.38 rendered 16 pages, and
  rendered-site validation passed. Existing Quarto output-path warnings remained
  nonfatal. Exact commit identity and post-commit clean-tree proof are reported at
  handoff because this Git document cannot contain its own commit SHA.
