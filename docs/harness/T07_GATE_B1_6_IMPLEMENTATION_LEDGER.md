# T07 Gate B1.6 implementation ledger

Status: **Gate B1.6 packet complete; Gate B2a installation authority blocked**

Source contract: `T07_GATE_B1_6_DOCKER_STORAGE_QUALIFICATION.md`, SHA-256
`52d05ce39998f1a0ff81c7bbc23d936d1a61e1d709c0adafdfd07b7fb0279e60`.

Baseline: clean `phase-1/sira-smoke` commit
`e224e781e752869041c78a3e93687aaa5d8c6430`.

## Definition of done

| ID | Required outcome | Status | Evidence |
|---|---|---|---|
| T07-B16-01 | Preserve branch ancestry, Gate A/B1/B1.5 evidence, locked science, and superseded records. | met | Starting checks and locked-file hash regression. |
| T07-B16-02 | Perform no prohibited Docker, browser, network, API, secret, SiRA, cloud, or cleanup action. | met | Local source inspection, read-only host inspection, mocks, and bounded temporary fixtures only. |
| T07-B16-03 | Enforce the external max(150 GiB, 20%) floor before and after storage-producing actions. | partial | Typed exact arithmetic and boundary tests implemented; no action executed. |
| T07-B16-04 | Derive and approve a source-backed numeric Mac mini operational floor. | blocked | Only DMG and retained evidence-cap terms are exact; six required terms remain unknown. |
| T07-B16-05 | Bind exact dedicated external paths and an internal active-attempt root. | met | Typed path roles and exact constants under new `/Volumes/Macintosh HD - Data/GIC-Lab`. |
| T07-B16-06 | Verify APFS, writable/unlocked state, both UUIDs, UTDM transport, and exact mount. | partial | Structural diskutil/APFS-list parser and mismatch tests exist; live B2a qualification was not run. |
| T07-B16-07 | Reject symlinks, path escape, internal placement, missing/renamed storage, stale guards, and fallback. | partial | No-follow traversal, exact roles, single-use tokens, and negative tests exist; diskutil identity is not yet linked to a held mount descriptor at guard consumption. |
| T07-B16-08 | Record and bound the `noowners` residual risk without changing volume ownership settings. | met | Qualification decision records the bounded nonsecret use and residual risk; no ownership mutation. |
| T07-B16-09 | Bind currently reverified official Docker 4.85.0 build 235549 metadata. | blocked | Retained 2026-08-09 official observation only; current-turn network verification prohibited. |
| T07-B16-10 | Install only the selected build without update/version substitution. | blocked | Version-specific supported first-start/update controls are not retained locally; no install occurred. |
| T07-B16-11 | Separate user-only terms, GUI, privilege, and reconnect actions. | partial | Distinct plan actors and required user-only action validation exist; version-specific privilege/GUI evidence semantics remain unresolved. |
| T07-B16-12 | Prove external disk placement and default internal inactivity mechanically. | partial | Typed minimized settings/file/device/engine evidence exists; version-specific sources, commands, and supervisor semantic validation remain blocked. |
| T07-B16-13 | Enforce bounded stop/disconnect/remount/reopen lifecycle ordering. | partial | State ordering and identity mismatch tests exist; machine stop/open-file proof and fresh restart-time guard linkage are not wired. |
| T07-B16-14 | Keep bounded active evidence only on the Mac mini. | partial | Exact internal root and 67,108,864-byte cap are designed and supervisor-checked; no live attempt was created. |
| T07-B16-15 | Close, fsync, hash, manifest, and make attempt sources immutable. | partial | Supervisor-minted single-use close capability plus bounded local seal/immutability tests exist; the authorized writer probe/driver is not implemented. |
| T07-B16-16 | Copy sealed evidence one-way, verify every destination hash, and retain source. | partial | Local fixtures cover fresh staging, exclusive writes, fsync, atomic rename, all-file hashes, immutable source, safe copy records, and no deletion; no live cross-volume copy ran. |
| T07-B16-17 | Produce a fresh B2a plan with arrays, caps, zero retry, commit and SHA binding. | partial | Blocked V1 plan SHA `7ccd43e413ec8c4a21a4af043bef2477ede14b5bd40885c979cdeb7e48081eb1` binds implementation `321136b2a23158a7618e1489a4d2005d7f7ba1cd`; null system caps and typed rollback/driver blockers prevent execution. |
| T07-B16-18 | Reject stale combined B2 authority and separate B2a from B2b. | met | Dedicated strict plan loader/schema, fixed superseded ID/SHA, disabled stale CLI surfaces, and negative tests. |
| T07-B16-19 | Produce a requirements-only B2b stub without executable authority. | met | `docs/harness/T07_GATE_B2B_REQUIREMENTS_STUB.md` plus negative contract test. |
| T07-B16-20 | Pass focused tests, validation, full check, independent review, repairs, and post-review check. | partial | Independent review failed and drove repairs; final rereview is clean. Full site rendering remains dependent on locally absent Quarto. |
| T07-B16-21 | Update all required documents, active plan, and storage policy without overstating suitability. | met | Five required B1.6/B2a/B2b documents, preauthorization packet, active plan, and storage policy. |
| T07-B16-22 | Commit reviewed work with a non-circular binding and leave a clean branch. | met | Implementation commit `321136b2a23158a7618e1489a4d2005d7f7ba1cd` is immutable; this packet-binding descendant is committed and its exact SHA plus clean-tree proof are reported at handoff. |

## Pre-edit gates

- Branch: `phase-1/sira-smoke`.
- HEAD: `e224e781e752869041c78a3e93687aaa5d8c6430`.
- Worktree: clean.
- Ancestry: the B1.5 commit is the exact starting HEAD.
- Focused Gate A/B1 regression:
  `PYTHONPATH=src uv run --no-sync pytest -q tests/test_sira_container.py tests/test_harness_schemas.py`
  — 84 passed.
- `make validate` — passed.

## Closeout evidence

- Bound implementation commit:
  `321136b2a23158a7618e1489a4d2005d7f7ba1cd`.
- Blocked plan: `PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1` at
  `containers/sira-smoke/gate-b2a-install-storage-binding-plan.json`, SHA-256
  `7ccd43e413ec8c4a21a4af043bef2477ede14b5bd40885c979cdeb7e48081eb1`.
  It has 75 steps (66 automatable, 9 user-only), 24 adjacent guards, and
  `authorized=false`.
- Exact step sums: 6,240 seconds, 7,839,744 output bytes, and 577,786,748
  download bytes. Exact aggregate caps: 7,200 seconds, 16,777,216 output bytes,
  and 577,786,748 download bytes.
- Focused storage/container/schema suite: 131 passed.
- Repository validation: passed.
- Pre-review and post-repair `make check` reached the same result: formatting, lint,
  strict type-check, 436 tests,
  repository validation, and site-data generation passed; the command then failed
  only because the local `quarto` executable is absent.
- Independent spec-conformance review initially failed and drove repairs. Final
  independent rereview found no actionable conformance issue and confirmed the plan
  inventory, caps, fail-closed state, implementation binding, and locked-science Git
  binding.
- `git diff --check`, the implementation-tree check, and the five-file locked-science
  check passed against the bound implementation commit.
- No network, Docker, image, container, browser, provider/API, secret, SiRA
  dependency/condition, cloud, scientific-field, or user-file cleanup action occurred.

Gate B2a, Gate B2b, Gate C, and live T07 remain unauthorized. The clean packet commit
SHA is intentionally reported at handoff because a Git document cannot embed its own
commit SHA without changing it.
